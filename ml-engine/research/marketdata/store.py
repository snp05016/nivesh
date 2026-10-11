"""Market-data store: raw files, gap-fill, entity linking, curated panel (spec 3.3-3.9).

Layout under ``$RESEARCH_DATA_DIR`` (git-ignored; ``/data`` in Docker)::

    raw/bhavcopy/{YYYY}/{YYYYMMDD}.csv.zip     immutable
    raw/yfinance/bars/{YYYYMMDD}-{sha8}.parquet  fallback rows (immutable)
    raw/yfinance/bars/crosscheck.parquet       raw closes for bad-tick candidates
    raw/yfinance/actions/{SYMBOL}.parquet      dividends and splits (weekly)
    raw/yfinance/index/NIFTY50.parquet         ^NSEI closes
    raw/MANIFEST.jsonl                         one line (path, sha256, ...) per raw write
    curated/prices/year={YYYY}/part.parquet    the panel (3.3) plus row_isin, row_symbol
    curated/entities.parquet                   entity episodes

Curation always re-links and re-adjusts the whole history (both are cheap and
deterministic) and rewrites only the year partitions whose content changed.

CLI::

    python -m research.marketdata.store backfill --start 2008-01-01
    python -m research.marketdata.store load --source local_csv
    python -m research.marketdata.store events --kind ca_unverified --since 2024-01-01
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from research import config
from research.marketdata import adjust as adj
from research.marketdata.bhavcopy import BhavcopySchemaError, Downloader, bhavcopy_url, parse_bhavcopy

log = logging.getLogger(__name__)

PANEL_COLUMNS = [
    "date", "entity_id", "isin", "symbol", "open", "high", "low", "close", "prev_close",
    "volume", "turnover_inr", "trades", "px_idx", "event", "quality_flags", "source",
]
ENTITY_COLUMNS = ["entity_id", "isin", "symbol", "valid_from", "valid_to", "link_reason"]
EVENT_KINDS = ("split", "override", "dividend", "ca_unverified")
_EXTRA = ["row_isin", "row_symbol"]  # the identifiers each row carried, for re-linking
_STR = ("entity_id", "isin", "symbol", "event", "quality_flags", "source", "row_isin", "row_symbol")
_FLOAT = ("open", "high", "low", "close", "prev_close", "volume", "turnover_inr", "trades", "px_idx")
_RAW_COLUMNS = [
    "date", "symbol", "isin", "open", "high", "low", "close", "prev_close",
    "volume", "turnover_inr", "trades", "source",
]
_YF_CAP_PER_RUN = 100  # yfinance actions refreshes / cross-check fetches per curation
_ACTIONS_TTL_DAYS = 7
_CROSSCHECK_RETRY_DAYS = 7  # a cross-check miss (empty frame / error) is retried after this
_FALLBACK_MAX_EMPTY_SHARE = 0.2
_FALLBACK_MIN_SAMPLE = 10
_INDEX_TICKERS = {"NIFTY50": "^NSEI"}

Fetch = Callable[[date], "bytes | None"]


# ── paths, raw files, manifest ──────────────────────────────────────────────


def _root(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir else config.DATA_DIR


def _zip_rel(d: date) -> str:
    return f"raw/bhavcopy/{d.year}/{d:%Y%m%d}.csv.zip"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _write_raw(root: Path, rel: str, data: bytes, *, immutable: bool = True, **meta: Any) -> str:
    """Write a raw file and append its sha256 to raw/MANIFEST.jsonl.

    Immutable files are never overwritten; rewriting one with different bytes raises.
    """
    path = root / rel
    sha = _sha(data)
    if path.exists() and immutable:
        if _sha(path.read_bytes()) != sha:
            raise RuntimeError(f"raw file {rel} is immutable and the new bytes differ")
        return sha
    _atomic_write(path, data)
    entry = {
        "path": rel, "sha256": sha, "bytes": len(data),
        "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **meta,
    }
    manifest = root / "raw" / "MANIFEST.jsonl"
    with manifest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return sha


def _parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def read_manifest(data_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _root(data_dir) / "raw" / "MANIFEST.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── normalisation and curated partitions ────────────────────────────────────


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Canonical dtypes and order (entity_id, date)."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).astype("datetime64[ns]")
    for c in _STR:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)
    for c in _FLOAT:
        if c in df.columns:
            df[c] = df[c].astype("float64")
    return df.sort_values(["entity_id", "date"], kind="stable").reset_index(drop=True)


def _partition(root: Path, year: int) -> Path:
    return root / "curated" / "prices" / f"year={year}" / "part.parquet"


def _read_curated(root: Path, years: Iterable[int] | None = None) -> pd.DataFrame:
    base = root / "curated" / "prices"
    paths = sorted(base.glob("year=*/part.parquet")) if base.exists() else []
    if years is not None:
        wanted = {f"year={y}" for y in years}
        paths = [p for p in paths if p.parent.name in wanted]
    if not paths:
        return _normalize(pd.DataFrame(columns=PANEL_COLUMNS + _EXTRA))
    return _normalize(pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True))


def _write_partitions(root: Path, panel: pd.DataFrame) -> list[int]:
    """Rewrite the year partitions whose content changed; return those years."""
    written: list[int] = []
    years = panel["date"].dt.year
    for year in sorted(set(years.tolist())):
        part = _normalize(panel.loc[years == year])
        path = _partition(root, int(year))
        if path.exists() and _normalize(pd.read_parquet(path)).equals(part):
            continue
        _atomic_write(path, _parquet_bytes(part))
        written.append(int(year))
    return written


def _rows_from_curated(cur: pd.DataFrame) -> pd.DataFrame:
    """Back to raw rows (the identifiers each row carried, zero volume as 0)."""
    rows = cur.drop(columns=["isin", "symbol"]).rename(columns={"row_isin": "isin", "row_symbol": "symbol"})
    rows["volume"] = rows["volume"].fillna(0.0)
    return rows.loc[:, _RAW_COLUMNS]


# ── entity linking (3.4) ────────────────────────────────────────────────────


def link_entities(
    rows: pd.DataFrame, lookback: int = config.LINKING["lookback_sessions"]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign ``entity_id`` per session in date order; return (rows, episodes).

    1. a known (ISIN, symbol) pair -> its entity;
    2. a new ISIN whose symbol was held by E in the previous ``lookback`` sessions
       -> E (``isin_change``: face-value split or consolidation);
    3. a new symbol whose ISIN was held by E -> E (``symbol_change``: rename);
    4. otherwise a new entity ``"E" + first ISIN`` (``new_listing``).
    Both changing on the same day, or E already present in the session, starts a
    new entity. Only earlier sessions are consulted, so links are point-in-time.
    """
    df = rows.sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)
    sess: list[int] = df["date"].rank(method="dense").astype("int64").tolist()
    isins: list[str] = df["isin"].fillna("").astype(str).tolist()
    syms: list[str] = df["symbol"].astype(str).tolist()
    pair_entity: dict[tuple[str, str], str] = {}
    reason: dict[tuple[str, str], str] = {}
    seen_sym: dict[str, tuple[str, int]] = {}
    seen_isin: dict[str, tuple[str, int]] = {}
    used: set[str] = set()
    out: list[str] = [""] * len(df)
    bounds = (np.flatnonzero(np.diff(sess)) + 1).tolist()
    for s0, s1 in zip([0, *bounds], [*bounds, len(df)]):
        k = sess[s0] if len(df) else 0
        present: set[str] = set()
        new_rows = []
        for i in range(s0, s1):
            e = pair_entity.get((isins[i], syms[i]))
            if e is None:
                new_rows.append(i)
            else:
                out[i] = e
                present.add(e)
        for i in new_rows:
            isin, sym = isins[i], syms[i]
            hs, hi = seen_sym.get(sym), seen_isin.get(isin) if isin else None
            by_sym = hs[0] if hs and k - hs[1] <= lookback else None
            by_isin = hi[0] if hi and k - hi[1] <= lookback else None
            e, why = None, "new_listing"
            if by_sym and not by_isin and by_sym not in present:
                e, why = by_sym, "isin_change"
            elif by_isin and not by_sym and by_isin not in present:
                e, why = by_isin, "symbol_change"
            if e is None:
                base = "E" + (isin or sym)
                e, n = base, 2
                while e in used:
                    e, n = f"{base}-{n}", n + 1
                used.add(e)
            pair_entity[(isin, sym)] = e
            reason[(isin, sym)] = why
            out[i] = e
            present.add(e)
        for i in range(s0, s1):
            seen_sym[syms[i]] = (out[i], k)
            if isins[i]:
                seen_isin[isins[i]] = (out[i], k)
    df["entity_id"] = out
    df["isin"] = isins
    ep = (
        df.groupby(["entity_id", "isin", "symbol"], sort=False)["date"]
        .agg(valid_from="min", valid_to="max")
        .reset_index()
    )
    ep["link_reason"] = [reason[(i, s)] for i, s in zip(ep["isin"], ep["symbol"])]
    ep = ep.sort_values(["entity_id", "valid_from"], kind="stable").reset_index(drop=True)
    return df, ep.loc[:, ENTITY_COLUMNS]


def _latest(episodes: pd.DataFrame, col: str) -> dict[str, str]:
    """entity_id -> latest value of ``col`` (isin or symbol)."""
    last = episodes.sort_values(["entity_id", "valid_to", "valid_from"], kind="stable").drop_duplicates("entity_id", keep="last")
    return dict(zip(last["entity_id"], last[col]))


# ── yfinance (fallback rows, actions, second source, index). Never used in tests.


def _yf_ticker(symbol: str) -> str:
    return symbol if symbol.startswith("^") else f"{symbol}.NS"


def _naive_dates(index: Any) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return pd.DatetimeIndex(idx.to_numpy(dtype="datetime64[D]").astype("datetime64[ns]"))


class YFinance:
    """Thin yfinance wrapper: raw bars (``auto_adjust=False``) and corporate actions."""

    def __init__(self) -> None:
        import yfinance  # lazy: heavy, and network only

        self._yf = yfinance

    def bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Raw daily bars (date, open, high, low, close, volume), start..end inclusive."""
        h = self._yf.Ticker(_yf_ticker(symbol)).history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False, actions=False,
        )
        if h is None or h.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        out = pd.DataFrame({
            "date": _naive_dates(h.index), "open": h["Open"].to_numpy(), "high": h["High"].to_numpy(),
            "low": h["Low"].to_numpy(), "close": h["Close"].to_numpy(), "volume": h["Volume"].to_numpy(),
        })
        return out.astype({c: "float64" for c in ("open", "high", "low", "close", "volume")})

    def actions(self, symbol: str) -> pd.DataFrame:
        """Corporate actions (date, dividend, split); split is yfinance's ratio."""
        a = self._yf.Ticker(_yf_ticker(symbol)).actions
        if a is None or a.empty:
            return pd.DataFrame(columns=["date", "dividend", "split"])
        return pd.DataFrame({
            "date": _naive_dates(a.index),
            "dividend": a.get("Dividends", pd.Series(0.0, index=a.index)).to_numpy(dtype="float64"),
            "split": a.get("Stock Splits", pd.Series(0.0, index=a.index)).to_numpy(dtype="float64"),
        })


def _actions_path(root: Path, symbol: str) -> Path:
    return root / "raw" / "yfinance" / "actions" / f"{symbol}.parquet"


def _refresh_actions(root: Path, symbols: list[str], yf: Any) -> None:
    fresh_after = time.time() - _ACTIONS_TTL_DAYS * 86400
    stale = [s for s in symbols if not _actions_path(root, s).exists() or _actions_path(root, s).stat().st_mtime < fresh_after]
    for sym in stale[:_YF_CAP_PER_RUN]:
        try:
            frame = yf.actions(sym)
        except Exception as exc:  # network: keep the old cache, classification stays as is
            log.warning("yfinance actions failed for %s: %s", sym, exc)
            continue
        _write_raw(root, f"raw/yfinance/actions/{sym}.parquet", _parquet_bytes(frame), immutable=False, source="yfinance_actions")


def _load_actions(root: Path, symbols: list[str]) -> pd.DataFrame:
    frames = [pd.read_parquet(p).assign(symbol=s) for s in symbols if (p := _actions_path(root, s)).exists()]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "dividend", "split"])
    out = pd.concat(frames, ignore_index=True)
    out["split"] = out["split"].where(out["split"] > 0)
    out["dividend"] = out["dividend"].where(out["dividend"] > 0)
    return out


_CROSSCHECK = "raw/yfinance/bars/crosscheck.parquet"


def _load_second(root: Path) -> pd.DataFrame:
    path = root / _CROSSCHECK
    have = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["symbol", "date", "close"])
    if "fetched_at" not in have.columns:
        have["fetched_at"] = np.nan
    have["date"] = pd.to_datetime(have["date"]).astype("datetime64[ns]")
    return have


def _refresh_second(root: Path, cands: pd.DataFrame, yf: Any) -> None:
    """Fetch yfinance closes for bad-tick candidates (3.5 i), at most ``_YF_CAP_PER_RUN`` per run.

    Misses (empty frame or error) are cached as close=NaN with ``fetched_at`` so they
    are not refetched every run; they are retried after ``_CROSSCHECK_RETRY_DAYS``.
    Never-tried candidates go first. ``adjust._lookup`` drops NaN closes, so a miss
    never marks a row suspect.
    """
    have = _load_second(root)
    now = time.time()
    seen = set(zip(have["symbol"], have["date"]))
    done = have["close"].notna() | (have["fetched_at"] > now - _CROSSCHECK_RETRY_DAYS * 86400)
    known = set(zip(have.loc[done, "symbol"], have.loc[done, "date"]))
    todo = [(s, d) for s, d in zip(cands["symbol"], cands["date"]) if (s, d) not in known]
    todo.sort(key=lambda k: k in seen)  # stable: untried first, expired misses after
    got = []
    for sym, ts in todo[:_YF_CAP_PER_RUN]:
        close = np.nan
        try:
            bars = yf.bars(sym, ts.date(), ts.date())
            bars = bars[bars["date"] == ts]
            if not bars.empty:
                close = float(bars["close"].iloc[0])
        except Exception as exc:
            log.warning("yfinance cross-check failed for %s %s: %s", sym, ts.date(), exc)
        got.append({"symbol": sym, "date": ts, "close": close, "fetched_at": now})
    if got:
        out = pd.concat([have, pd.DataFrame(got)], ignore_index=True)
        out = out.drop_duplicates(["symbol", "date"], keep="last").reset_index(drop=True)
        _write_raw(root, _CROSSCHECK, _parquet_bytes(out), immutable=False, source="yfinance_crosscheck")


# ── curation ────────────────────────────────────────────────────────────────


def _curate(root: Path, rows: pd.DataFrame, yf: Any = None) -> pd.DataFrame:
    """Link, adjust and quality-flag the full history; persist changed partitions."""
    linked, episodes = link_entities(rows)
    overrides = adj.load_overrides()
    out = adj.adjust(linked, overrides=overrides)
    event_syms = sorted(set(out.loc[out["event"] != "", "symbol"]))
    cands = out.loc[
        (out["ret"].abs() > config.QUALITY["jump_threshold"]) & out["source"].eq("nse_bhavcopy"),
        ["symbol", "date"],
    ]
    if yf is not None:
        _refresh_actions(root, event_syms, yf)
        _refresh_second(root, cands, yf)
    actions, second = _load_actions(root, event_syms), _load_second(root)
    if not (actions.empty and second.empty):
        out = adj.adjust(linked, overrides=overrides, actions=actions, second_source=second)
    adj.check_drops("curate", len(rows), len(out))
    panel = out.rename(columns={"isin": "row_isin", "symbol": "row_symbol"})
    latest_isin, latest_sym = _latest(episodes, "isin"), _latest(episodes, "symbol")
    panel["isin"] = [latest_isin[e] for e in panel["entity_id"]]
    panel["symbol"] = [latest_sym[e] for e in panel["entity_id"]]
    panel = _normalize(panel.loc[:, PANEL_COLUMNS + _EXTRA])
    if panel.duplicated(["date", "entity_id"]).any():
        raise RuntimeError("curated panel has duplicate (date, entity_id) rows")
    years = _write_partitions(root, panel)
    _atomic_write(root / "curated" / "entities.parquet", _parquet_bytes(episodes))
    log.info("curated %d rows, %d entities; rewrote years %s", len(panel), episodes["entity_id"].nunique(), years)
    return panel


@dataclass
class GapFillResult:
    """Outcome of ``ensure_sessions``. ``incomplete`` -> run degraded (gap_fill_incomplete)."""

    through: date
    added: list[date] = field(default_factory=list)
    replaced_fallback: list[date] = field(default_factory=list)
    no_session: list[date] = field(default_factory=list)
    failed: dict[date, str] = field(default_factory=dict)

    @property
    def incomplete(self) -> bool:
        return any(d < self.through for d in self.failed)


def ensure_sessions(
    through: date,
    *,
    data_dir: str | Path | None = None,
    fetch: Fetch | None = None,
    yf: Any = None,
    min_eq_rows: int = config.QUALITY["min_bhavcopy_eq_rows"],
) -> GapFillResult:
    """Gap-fill: ingest every missing bhavcopy in the 15 calendar days ending ``through``.

    Weekends are included (special sessions); a 404 means no session. A bhavcopy
    replaces any yfinance fallback rows of that date. Affected partitions are
    rewritten. A bad file (bad zip, HTML, fewer than ``min_eq_rows`` EQ rows) or a
    network error is recorded in ``failed``; a schema change
    (``BhavcopySchemaError``) or a row-accounting breach raises (fail closed).
    """
    root = _root(data_dir)
    result = GapFillResult(through)
    cur = _read_curated(root)
    have = set(cur.loc[cur["source"] == "nse_bhavcopy", "date"].dt.date)
    window = [through - timedelta(days=i) for i in range(config.GAP_FILL["max_calendar_days"] - 1, -1, -1)]
    new_frames = []
    for d in (d for d in window if d not in have):
        path = root / _zip_rel(d)
        try:
            if path.exists():
                data: bytes | None = path.read_bytes()
            else:
                if fetch is None:
                    fetch = Downloader().fetch
                data = fetch(d)
            if data is None:
                result.no_session.append(d)
                continue
            parsed = parse_bhavcopy(data)
            if not bool(parsed["date"].eq(pd.Timestamp(d)).all()):
                raise BhavcopySchemaError(f"bhavcopy for {d} carries other dates")
            if len(parsed) < min_eq_rows:
                raise ValueError(f"only {len(parsed)} EQ rows (< {min_eq_rows})")
        except BhavcopySchemaError:
            raise
        except Exception as exc:  # 2.6: bad file / network error -> not ingested, reported
            result.failed[d] = f"{type(exc).__name__}: {exc}"
            log.warning("gap-fill %s failed: %s", d, result.failed[d])
            continue
        kept, _ = adj.quality_filter(parsed.assign(source="nse_bhavcopy").loc[:, _RAW_COLUMNS])
        adj.check_drops(f"bhavcopy {d}", len(parsed), len(kept))
        _write_raw(root, _zip_rel(d), data, source="nse_bhavcopy", session=d.isoformat(), url=bhavcopy_url(d))
        new_frames.append(kept)
        result.added.append(d)
    if new_frames:
        added = pd.to_datetime(pd.Series(result.added)).astype("datetime64[ns]")
        replaced = cur["date"].isin(added)
        result.replaced_fallback = sorted(set(cur.loc[replaced, "date"].dt.date))
        rows = pd.concat([_rows_from_curated(cur.loc[~replaced]), *new_frames], ignore_index=True)
        _curate(root, rows, yf=yf)
    return result


def add_fallback(
    session: date, symbols: Iterable[str], *, data_dir: str | Path | None = None, yf: Any = None
) -> list[str]:
    """yfinance fallback rows (raw, ``prev_close`` NaN, source yfinance) for ``session``.

    Only for symbols the store already knows and that have no row that day. Stops
    once more than 20% of the attempted symbols return empty frames (throttled);
    those symbols stay stale. Returns the symbols added.
    """
    root = _root(data_dir)
    cur = _read_curated(root)
    ts = pd.Timestamp(session)
    if bool(cur.loc[cur["date"] == ts, "source"].eq("nse_bhavcopy").any()):
        return []
    have = set(cur.loc[cur["date"] == ts, "row_symbol"])
    episodes = load_entities(root)
    sym_isin = episodes.sort_values(["valid_to", "valid_from"]).groupby("symbol")["isin"].last().to_dict()
    yf = yf or YFinance()
    rows, tried, empty = [], 0, 0
    for sym in dict.fromkeys(_norm_symbol(s) for s in symbols):
        if sym in have or sym not in sym_isin:
            continue
        if tried >= _FALLBACK_MIN_SAMPLE and empty / tried > _FALLBACK_MAX_EMPTY_SHARE:
            log.warning("yfinance fallback stopped: %d of %d frames empty", empty, tried)
            break
        tried += 1
        try:
            bars = yf.bars(sym, session, session)
        except Exception as exc:
            log.warning("yfinance fallback failed for %s: %s", sym, exc)
            bars = pd.DataFrame(columns=["date"])
        bar = bars[bars["date"] == ts]
        if bar.empty:
            empty += 1
            continue
        b = bar.iloc[0]
        rows.append({
            "date": ts, "symbol": sym, "isin": sym_isin[sym], "open": b["open"], "high": b["high"],
            "low": b["low"], "close": b["close"], "prev_close": np.nan, "volume": b["volume"],
            "turnover_inr": b["close"] * b["volume"], "trades": np.nan, "source": "yfinance",
        })
    if not rows:
        return []
    frame = pd.DataFrame(rows).loc[:, _RAW_COLUMNS]
    kept, _ = adj.quality_filter(frame)
    adj.check_drops(f"fallback {session}", len(frame), len(kept))
    data = _parquet_bytes(kept)
    _write_raw(root, f"raw/yfinance/bars/{session:%Y%m%d}-{_sha(data)[:8]}.parquet", data,
               source="yfinance_fallback", session=session.isoformat())
    _curate(root, pd.concat([_rows_from_curated(cur), kept], ignore_index=True))
    return kept["symbol"].tolist()


def rebuild(data_dir: str | Path | None = None, yf: Any = None) -> pd.DataFrame:
    """Re-curate everything from the raw files (after a backfill)."""
    root = _root(data_dir)
    frames, bhav_days = [], set()
    for p in sorted((root / "raw" / "bhavcopy").glob("*/*.csv.zip")):
        frames.append(parse_bhavcopy(p.read_bytes()).assign(source="nse_bhavcopy").loc[:, _RAW_COLUMNS])
        bhav_days.add(p.name[:8])
    for p in sorted((root / "raw" / "yfinance" / "bars").glob("[0-9]*-*.parquet")):
        if p.name[:8] not in bhav_days:
            frames.append(pd.read_parquet(p).loc[:, _RAW_COLUMNS])
    if not frames:
        raise RuntimeError(f"no raw files under {root / 'raw'}")
    rows = pd.concat(frames, ignore_index=True)
    kept, _ = adj.quality_filter(rows)
    adj.check_drops("rebuild", len(rows), len(kept))
    return _curate(root, kept, yf=yf)


def backfill(
    start: date, end: date | None = None, *, data_dir: str | Path | None = None, fetch: Fetch | None = None
) -> pd.DataFrame:
    """Download every weekday bhavcopy from ``start`` (resumable), then rebuild.

    Network errors and bad files (corrupt zip, HTML page; spec 2.6) are logged,
    skipped and listed in ``attrs["backfill_failed"]`` ({date: reason}); re-run to
    retry them. A schema change (``BhavcopySchemaError``) raises (fail closed).
    Saturday special sessions are left to gap-fill.
    """
    root = _root(data_dir)
    fetch = fetch or Downloader().fetch
    d, end = start, end or date.today()
    failed: dict[date, str] = {}
    while d <= end:
        if d.weekday() < 5 and not (root / _zip_rel(d)).exists():
            try:
                data = fetch(d)
                if data is not None:
                    parse_bhavcopy(data)  # validate before the immutable write
            except BhavcopySchemaError:
                raise
            except Exception as exc:  # network error or BadBhavcopyFile -> skipped, reported
                failed[d] = f"{type(exc).__name__}: {exc}"
                log.warning("backfill %s failed: %s", d, failed[d])
                data = None
            if data is not None:
                _write_raw(root, _zip_rel(d), data, source="nse_bhavcopy", session=d.isoformat(), url=bhavcopy_url(d))
        d += timedelta(days=1)
    panel = rebuild(root)
    panel.attrs["backfill_failed"] = failed
    return panel


# ── readers (the frozen interface, 3.3) ─────────────────────────────────────


def load_local_csv(path: str | Path | None = None) -> pd.DataFrame:
    """Dev panel from ``RESEARCH_LOCAL_CSV`` (survivorship-biased, already adjusted).

    entity_id = isin = symbol; prev_close = previous close; turnover = close * volume;
    px_idx chained from closes. Row accounting is in ``attrs["row_accounting"]``.
    """
    raw = pd.read_csv(path or config.LOCAL_CSV)
    missing = {"symbol", "date", "open", "high", "low", "close", "volume"} - set(raw.columns)
    if missing:
        raise ValueError(f"local CSV missing columns: {sorted(missing)}")
    raw["date"] = pd.to_datetime(raw["date"]).astype("datetime64[ns]")
    raw["symbol"] = raw["symbol"].astype(str).str.strip()
    raw = raw.sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    raw["volume"] = raw["volume"].astype("float64")
    raw["isin"] = raw["symbol"]
    raw["prev_close"] = raw.groupby("symbol")["close"].shift()
    raw["turnover_inr"] = raw["close"] * raw["volume"]
    raw["trades"] = np.nan
    raw["source"] = "local_csv"
    kept, dropped = adj.quality_filter(raw.loc[:, _RAW_COLUMNS])
    share = adj.check_drops("local_csv", len(raw), len(kept))
    panel = _normalize(adj.adjust(kept.assign(entity_id=kept["symbol"]), apply_factors=False)).loc[:, PANEL_COLUMNS]
    panel.attrs["row_accounting"] = {"rows_in": len(raw), "rows_out": len(panel), "dropped": dropped, "dropped_share": share}
    return panel


def load_panel(
    start: date | str | None = None,
    end: date | str | None = None,
    source: Literal["store", "local_csv"] = "store",
    data_dir: str | Path | None = None,
) -> pd.DataFrame:
    """One row per (date, entity_id), sorted by entity_id then date (spec 3.3)."""
    lo = pd.Timestamp(start) if start is not None else None
    hi = pd.Timestamp(end) if end is not None else None
    if source == "local_csv":
        panel = load_local_csv()
    elif source == "store":
        years = range(int(lo.year), int(hi.year) + 1) if lo is not None and hi is not None else None
        panel = _read_curated(_root(data_dir), years).loc[:, PANEL_COLUMNS]
    else:
        raise ValueError(f"unknown panel source {source!r}")
    attrs = dict(panel.attrs)
    mask = pd.Series(True, index=panel.index)
    if lo is not None:
        mask &= panel["date"] >= lo
    if hi is not None:
        mask &= panel["date"] <= hi
    out = panel.loc[mask].reset_index(drop=True)
    out.attrs = attrs
    return out


def load_entities(data_dir: str | Path | None = None) -> pd.DataFrame:
    """Entity episodes: entity_id, isin, symbol, valid_from, valid_to, link_reason."""
    path = _root(data_dir) / "curated" / "entities.parquet"
    if not path.exists():
        return pd.DataFrame(columns=ENTITY_COLUMNS)
    return pd.read_parquet(path).loc[:, ENTITY_COLUMNS]


def _norm_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    return s[:-3] if s.endswith(".NS") else s


def resolve_entity(
    symbol: str | None = None,
    isin: str | None = None,
    as_of: date | str | None = None,
    data_dir: str | Path | None = None,
) -> str | None:
    """entity_id for an ISIN (tried first) or a symbol, as known on ``as_of``; None if unknown."""
    ep = load_entities(data_dir)
    ts = pd.Timestamp(as_of) if as_of is not None else None
    if ts is not None:
        ep = ep.loc[ep["valid_from"] <= ts]
    for col, val in (("isin", isin.strip() if isin else None), ("symbol", _norm_symbol(symbol) if symbol else None)):
        if not val:
            continue
        hits = ep.loc[ep[col] == val]
        if hits.empty:
            continue
        if ts is not None and bool((hits["valid_to"] >= ts).any()):
            hits = hits.loc[hits["valid_to"] >= ts]
        return str(hits.sort_values(["valid_to", "valid_from"]).iloc[-1]["entity_id"])
    return None


def _index_path(root: Path, name: str) -> Path:
    return root / "raw" / "yfinance" / "index" / f"{name}.parquet"


def load_index(
    name: str = "NIFTY50",
    start: date | str | None = None,
    end: date | str | None = None,
    data_dir: str | Path | None = None,
) -> pd.Series | None:
    """Cached index closes (price index, NIFTY50_PR) as a date-indexed Series; None without a cache."""
    path = _index_path(_root(data_dir), name)
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    s = pd.Series(df["close"].to_numpy(dtype="float64"), index=pd.DatetimeIndex(df["date"]).astype("datetime64[ns]"), name=name)
    s = s.sort_index()
    return s.loc[pd.Timestamp(start) if start else None: pd.Timestamp(end) if end else None]


def refresh_index(name: str = "NIFTY50", *, data_dir: str | Path | None = None, yf: Any = None) -> int:
    """Fetch the full index history from yfinance into the cache; return its row count."""
    yf = yf or YFinance()
    bars = yf.bars(_INDEX_TICKERS[name], config.DATES["prod"]["data_start"], date.today())
    if bars.empty:
        raise RuntimeError(f"yfinance returned no bars for {name}")
    frame = bars[["date", "close"]]
    _write_raw(_root(data_dir), f"raw/yfinance/index/{name}.parquet", _parquet_bytes(frame), immutable=False, source="yfinance_index")
    return len(frame)


def sessions(panel: pd.DataFrame) -> pd.DatetimeIndex:
    """The session calendar: sorted union of panel dates."""
    return pd.DatetimeIndex(np.unique(panel["date"].to_numpy(dtype="datetime64[ns]")))


def data_sha256(panel: pd.DataFrame) -> str:
    """Content hash of the panel (canonical dtypes and order, PANEL_COLUMNS only)."""
    p = _normalize(panel.loc[:, PANEL_COLUMNS])
    h = hashlib.sha256(f"{','.join(PANEL_COLUMNS)}|{len(p)}".encode())
    for c in PANEL_COLUMNS:
        if c == "date":
            h.update(p[c].to_numpy(dtype="datetime64[ns]").view("int64").tobytes())
        elif c in _FLOAT:
            h.update(p[c].to_numpy(dtype="float64").tobytes())
        else:
            h.update("\x1f".join(p[c].tolist()).encode("utf-8"))
    return h.hexdigest()


def is_holiday(d: date, *, data_dir: str | Path | None = None, fetch: Fetch | None = None) -> bool:
    """True when there is no bhavcopy for ``d`` (stored or downloadable) and no index bar.

    Call after ``refresh_index`` (spec 2.6: checked at 07:15 the next morning).
    """
    root = _root(data_dir)
    ts = pd.Timestamp(d)
    if (root / _zip_rel(d)).exists():
        return False
    idx = load_index(data_dir=root)
    if idx is not None and ts in idx.index:
        return False
    return (fetch or Downloader().fetch)(d) is None


def events(kind: str | None = None, since: date | str | None = None, data_dir: str | Path | None = None) -> pd.DataFrame:
    """Rows where a factor applies (optionally one kind, since a date) for OPS review."""
    panel = load_panel(start=since, source="store", data_dir=data_dir)
    rows = panel.loc[panel["event"] != ""] if kind is None else panel.loc[panel["event"] == kind]
    cols = ["date", "entity_id", "symbol", "isin", "event", "close", "prev_close", "quality_flags"]
    return rows.loc[:, cols].sort_values(["date", "symbol"])


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m research.marketdata.store")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backfill", help="download bhavcopies (needs RESEARCH_HTTP_CONTACT), then rebuild")
    b.add_argument("--start", type=date.fromisoformat, required=True)
    b.add_argument("--end", type=date.fromisoformat)
    ld = sub.add_parser("load", help="load the panel and print a summary")
    ld.add_argument("--source", choices=("store", "local_csv"), default="store")
    ld.add_argument("--start", type=date.fromisoformat)
    ld.add_argument("--end", type=date.fromisoformat)
    ev = sub.add_parser("events", help="print corporate-action events for review")
    ev.add_argument("--kind", choices=EVENT_KINDS)
    ev.add_argument("--since", type=date.fromisoformat)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "backfill":
        panel = backfill(args.start, args.end)
        failed = panel.attrs.get("backfill_failed", {})
        print(f"curated rows={len(panel)} entities={panel['entity_id'].nunique()} failed_dates={len(failed)}")
        for d, why in sorted(failed.items()):
            print(f"  failed {d}: {why}")
    elif args.cmd == "load":
        panel = load_panel(args.start, args.end, source=args.source)
        if panel.empty:
            print(f"source={args.source} no rows")
            return 1
        acc = panel.attrs.get("row_accounting")
        drops = f" dropped={acc['dropped']} ({acc['dropped_share']:.2%})" if acc else ""
        print(
            f"source={args.source} symbols={panel['symbol'].nunique()} entities={panel['entity_id'].nunique()} "
            f"range={panel['date'].min():%Y-%m-%d}..{panel['date'].max():%Y-%m-%d} rows={len(panel)}{drops}"
        )
    else:
        rows = events(args.kind, args.since)
        print(rows.to_string(index=False) if not rows.empty else "no events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
