"""Nightly research run and on-demand compute (spec 2.2, 2.6, 6.5, 9.2).

``run_nightly(D)`` writes ``runs/{run_id}/run.json`` (``contract.RunStatus``)
and, on success, ``runs/{run_id}/items.jsonl`` (one ``contract.RunItem`` per
symbol). Steps:

0. Gap-fill (store only): ``store.ensure_sessions(D)``; a failed older date marks
   the run degraded (``gap_fill_incomplete``). The ^NSEI cache is refreshed.
1. Prices for D: the bhavcopy, else (from the next IST day on) a holiday check
   (no bhavcopy, no index bar -> ``skipped_holiday``), else yfinance fallback rows
   for the universe and extra symbols (``prices_fallback_yfinance``). No prices
   at all fails the run.
2-3. Linking, adjustment and quality run inside the store; PIT membership.
4. fv1 features; ``snapshots/{D}/features.parquet``.
5. Artefact verification, then score, rank_pct, bucket and p.
6-8. Risk, ranges, fundamentals (7-day cache, at most 60 refreshes), assembly.

Items are written to a temporary file and renamed only after every symbol is
assembled, so a failed stage (prices or later) leaves no items.

CLI::

    python -m research.pipeline --as-of 2026-06-23 --source local_csv --data-dir D \
        [--extra-symbols A,B] [--fundamentals {fetch,skip}]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd

from . import config, registry
from .contract import ResearchReport, RunCounts, RunItem, RunStatus, SourceStatus, UniverseQuality
from .features import FEATURES, compute_raw, rank
from .fundamentals import FetchBudget, fetch_fundamentals, pe_ttm, sector
from .marketdata import store, universe
from .models import lgbm
from .report import (
    Context,
    FundamentalsMode,
    HorizonModel,
    as_timestamp,
    assemble_report,
    feature_hash,
    predictions_for,
)

__all__ = [
    "InsufficientHistory",
    "PricesUnavailable",
    "UnknownSymbol",
    "build_context",
    "compute_symbol",
    "run_nightly",
]

log = logging.getLogger("research.pipeline")

PanelSource = Literal["store", "local_csv"]
IST = timezone(timedelta(hours=5, minutes=30))
# Longest lookback a report needs: 5-year drawdown (1,260 sessions) plus slack.
# Features, labels-free scoring and membership are truncation-safe at this depth.
WINDOW_YEARS = 6
MIN_COMPUTE_SESSIONS = 60  # /compute answers 422 below this (9.2)
_SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")


class PricesUnavailable(RuntimeError):
    """No bhavcopy and no fallback rows for the market date: the run fails and writes no items."""


class UnknownSymbol(LookupError):
    """The symbol resolves to no EQ entity (``/compute`` 404 ``UNKNOWN_SYMBOL``)."""


class InsufficientHistory(ValueError):
    """Fewer than 60 sessions of history (``/compute`` 422)."""


# ── small helpers ───────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _write_status(rdir: Path, status: RunStatus) -> None:
    _atomic(rdir / "run.json", (status.model_dump_json(indent=2) + "\n").encode("utf-8"))


def new_run_id(market_date: date) -> str:
    return f"{market_date:%Y%m%d}-{uuid.uuid4().hex[:8]}"


def normalise_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    for suffix in (".NS", ".BO"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def _load_window(as_of: date, source: PanelSource, root: Path) -> pd.DataFrame:
    start = as_of - timedelta(days=round(365.25 * WINDOW_YEARS))
    return store.load_panel(start=start, end=as_of, source=source, data_dir=root)


def _git_sha() -> str | None:
    from .train import git_sha  # local import: train pulls in the validation stack

    sha = git_sha()
    return None if sha == "unknown" else sha


# ── context: membership, features, verified artefacts, scores ───────────────


def _score(h: int, data_dir: Path, raw_day: pd.DataFrame, membership_day: pd.DataFrame,
           scorable: set[str], universe_ids: frozenset[str]) -> HorizonModel:
    """Verify and load the active artefact, then score D (spec 2.2 step 5)."""
    try:
        art = registry.load_active(h, data_dir)
    except Exception as exc:  # missing, tampered or unreadable: outlooks manifest_invalid, no ledger rows
        problems = exc.problems if isinstance(exc, registry.ArtefactError) else [f"{type(exc).__name__}: {exc}"]
        log.warning("artefact h=%d not usable: %s", h, "; ".join(problems))
        return HorizonModel(h, None, list(problems))
    ranked = rank(raw_day, membership_day)
    ids = ranked.index.get_level_values("entity_id")
    nan_share = ranked.isna().to_numpy().mean(axis=1)
    ok = (nan_share <= config.FEATURE_RULES["max_row_nan_share"]) & ids.isin(list(scorable))
    x = ranked.loc[ok]
    cols = ["score", "rank_pct", "bucket", "p_top_half", "feature_hash"]
    if x.empty:
        return HorizonModel(h, art, [], pd.DataFrame(columns=cols, index=pd.Index([], name="entity_id")))
    score = pd.Series(lgbm.predict(art.boosters, x), index=x.index)
    member = pd.Series(x.index.get_level_values("entity_id").isin(list(universe_ids)), index=x.index)
    rp = lgbm.rank_pct(score, member)
    bucket = lgbm.bucket(rp.to_numpy())
    values = x[list(FEATURES)].to_numpy(dtype=float)
    scores = pd.DataFrame(
        {
            "score": score.to_numpy(),
            "rank_pct": rp.to_numpy(),
            "bucket": bucket,
            "p_top_half": art.calibrator.p_array(bucket),
            "feature_hash": [feature_hash(v) for v in values],
        },
        index=pd.Index(x.index.get_level_values("entity_id"), name="entity_id"),
    )
    return HorizonModel(h, art, [], scores)


def build_context(
    panel: pd.DataFrame,
    as_of: date,
    *,
    data_dir: Path,
    index: pd.Series | None,
    sources: Sequence[SourceStatus] = (),
    run_reasons: Sequence[str] = (),
    git_sha: str | None = None,
    computed_at: datetime | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> Context:
    """Membership, fv1 features and scores for market date ``as_of`` (``panel`` holds dates <= as_of)."""
    stage = on_stage or (lambda _s: None)
    day = pd.Timestamp(as_of)
    stage("universe")
    mem = universe.membership(panel)
    quality = cast(UniverseQuality, str(mem.attrs.get("universe_quality", "pit")))
    stage("features")
    raw = compute_raw(panel, mem)
    raw_day = raw.loc[raw.index.get_level_values("date") == day]
    mem_day = mem.loc[pd.DatetimeIndex(mem["date"]) == day].reset_index(drop=True)
    uni = frozenset(str(e) for e in mem_day.loc[mem_day["in_universe"].astype(bool), "entity_id"])
    vol = raw_day["vol_252"].droplevel("date")
    universe_vol = vol.loc[vol.index.isin(list(uni))].to_numpy(dtype=float) * 100.0

    day_rows = panel.loc[panel["date"] == day]
    px_ok = day_rows["px_idx"].to_numpy(dtype=float) > 0
    not_suspect = ~day_rows["quality_flags"].astype(str).str.contains("suspect", regex=False).to_numpy()
    scorable = set(day_rows.loc[px_ok & not_suspect, "entity_id"].astype(str))
    stage("scores")
    models = {h: _score(h, data_dir, raw_day, mem_day, scorable, uni) for h in config.HORIZONS}
    return Context(
        as_of=as_of,
        panel=panel,
        calendar=store.sessions(panel),
        raw_day=raw_day,
        membership_day=mem_day,
        universe=uni,
        universe_vol_pct=universe_vol,
        quality=quality,
        index=None if index is None else index.loc[:day],
        data_sha256=store.data_sha256(panel),
        models=models,
        computed_at=computed_at or _now(),
        git_sha=git_sha,
        sources=list(sources),
        run_reasons=list(run_reasons),
    )


def _latest_symbols(panel: pd.DataFrame) -> pd.Series:
    """entity_id -> the entity's latest symbol (the panel is sorted by entity_id, date)."""
    last = panel.drop_duplicates("entity_id", keep="last")
    return pd.Series(last["symbol"].astype(str).to_numpy(), index=last["entity_id"].astype(str).to_numpy())


def _resolve(symbol: str, latest: pd.Series, as_of: date, entities: pd.DataFrame) -> str | None:
    """entity_id for a symbol (ISIN-aware linking first, then the panel's latest symbols)."""
    sym = normalise_symbol(symbol)
    if not _SYMBOL_RE.fullmatch(sym):
        return None
    eid = store.resolve_entity(symbol=sym, as_of=as_of, entities=entities)
    if eid is not None and eid in latest.index:
        return eid
    hits = [str(e) for e, s in latest.items() if s == sym]
    return hits[-1] if hits else None


def _payloads(symbols: Iterable[str], mode: FundamentalsMode, root: Path,
              budget: FetchBudget | None) -> dict[str, dict[str, Any] | None]:
    """Fundamentals payloads; ``budget`` None means cache only (no network)."""
    out: dict[str, dict[str, Any] | None] = {}
    if mode == "skip":
        return {s: None for s in symbols}
    for s in symbols:
        try:
            out[s] = fetch_fundamentals(s, data_dir=root, budget=budget if budget is not None else FetchBudget(0))
        except (ValueError, OSError) as exc:  # invalid symbol for Yahoo, unreadable cache
            log.warning("fundamentals unavailable for %s: %s", s, exc)
            out[s] = None
    return out


def _peer_pes(symbol: str, payloads: dict[str, dict[str, Any] | None], universe_symbols: set[str]) -> list[float] | None:
    sec = sector(payloads.get(symbol))
    if sec is None:
        return None
    pes = [pe_ttm(p) for s, p in payloads.items() if s != symbol and s in universe_symbols and sector(p) == sec]
    return [pe for pe in pes if pe is not None]


def _sources(source: PanelSource, panel: pd.DataFrame, as_of: date, index: pd.Series | None,
             fallback: bool) -> list[SourceStatus]:
    """Provenance sources: the price source for D and the Nifty 50 cache."""
    out: list[SourceStatus] = []
    if source == "store":
        bhav = panel.loc[panel["source"] == "nse_bhavcopy", "date"]
        last = as_timestamp(bhav.max()).date() if len(bhav) else None
        status: Literal["ok", "fallback", "failed"] = "ok" if last == as_of else "fallback" if fallback else "failed"
        note = "yfinance fallback prices for the market date" if status == "fallback" else None
        out.append(SourceStatus(id="nse_bhavcopy", last_success=last, status=status, note=note))
    idx_last = as_timestamp(index.dropna().index.max()).date() if index is not None and index.notna().any() else None
    out.append(SourceStatus(
        id="yfinance", last_success=idx_last, status="ok" if idx_last == as_of else "failed",
        note=None if idx_last == as_of else "Nifty 50 index not available for the market date",
    ))
    return out


# ── prices stage (store) ────────────────────────────────────────────────────


def _universe_symbols_before(as_of: date, root: Path) -> list[str]:
    """Latest symbols of the universe on the last stored session before ``as_of``."""
    panel = _load_window(as_of - timedelta(days=1), "store", root)
    if panel.empty:
        return []
    mem = universe.membership(panel)
    last = mem["date"].max()
    ids = sorted(set(mem.loc[(mem["date"] == last) & mem["in_universe"].astype(bool), "entity_id"]))
    syms = panel.loc[panel["entity_id"].isin(ids)].drop_duplicates("entity_id", keep="last")["symbol"]
    return sorted(str(s) for s in syms)


def _store_prices(as_of: date, root: Path, extra: Sequence[str], fetch: store.Fetch | None,
                  yf: Any, now: datetime) -> list[str] | None:
    """Gap-fill and prices for D; returns degraded reasons, or None for a holiday."""
    reasons: list[str] = []
    gap = store.ensure_sessions(as_of, data_dir=root, fetch=fetch, yf=yf)
    if gap.incomplete:
        log.warning("gap-fill incomplete: %s", gap.failed)
        reasons.append("gap_fill_incomplete")
    try:
        store.refresh_index(data_dir=root, yf=yf)
    except Exception as exc:  # the cached index (if any) stays in use
        log.warning("Nifty 50 refresh failed: %s", exc)

    def day_sources() -> pd.Series:
        return cast(pd.Series, store.load_panel(start=as_of, end=as_of, source="store", data_dir=root)["source"])

    src = day_sources()
    if bool(src.eq("nse_bhavcopy").any()):
        return reasons
    if src.empty:
        # A holiday is only declared from the next IST morning (2.6); in the evening the
        # bhavcopy may simply be late, so fallback rows are used instead.
        if now.astimezone(IST).date() > as_of:
            try:
                if store.is_holiday(as_of, data_dir=root, fetch=fetch):
                    return None
            except Exception as exc:
                log.warning("holiday check failed for %s: %s", as_of, exc)
        symbols = [*_universe_symbols_before(as_of, root), *extra]
        store.add_fallback(as_of, symbols, data_dir=root, yf=yf)
        src = day_sources()
    if src.empty:
        raise PricesUnavailable(f"no bhavcopy and no fallback rows for {as_of}")
    reasons.append("prices_fallback_yfinance")
    return reasons


# ── nightly run ─────────────────────────────────────────────────────────────


def run_nightly(
    market_date: date | str,
    extra_symbols: Sequence[str] = (),
    source: PanelSource = "store",
    data_dir: str | Path | None = None,
    fundamentals_mode: FundamentalsMode = "fetch",
    *,
    run_id: str | None = None,
    fetch: store.Fetch | None = None,
    yf: Any = None,
    now: datetime | None = None,
) -> RunStatus:
    """One nightly run for market date D (spec 2.2); returns the final RunStatus.

    Never raises for data problems: any failure is recorded in ``run.json``
    (status failed, the stage, the error) and no items are written. ``fetch``
    and ``yf`` replace the bhavcopy downloader and yfinance (tests).
    """
    D = date.fromisoformat(market_date) if isinstance(market_date, str) else market_date
    root = Path(data_dir) if data_dir else config.DATA_DIR
    rid = run_id or new_run_id(D)
    rdir = root / "runs" / rid
    status = RunStatus(run_id=rid, market_date=D, status="running", stage="prices", counts=RunCounts(),
                       error=None, started_at=_now(), finished_at=None)
    _write_status(rdir, status)

    def set_stage(name: str) -> None:
        status.stage = name
        _write_status(rdir, status)

    extra = list(dict.fromkeys(normalise_symbol(s) for s in extra_symbols if s and s.strip()))
    try:
        reasons: list[str] = []
        if source == "store":
            yf = yf if yf is not None else store.YFinance()
            got = _store_prices(D, root, extra, fetch, yf, now or _now())
            if got is None:
                status.status, status.finished_at = "skipped_holiday", _now()
                _write_status(rdir, status)
                return status
            reasons = got
        panel = _load_window(D, source, root)
        if panel.empty or not bool((panel["date"] == pd.Timestamp(D)).any()):
            raise PricesUnavailable(f"no prices for {D} in the {source} panel")
        index = store.load_index("NIFTY50", end=D, data_dir=root)
        fallback = "prices_fallback_yfinance" in reasons
        global_reasons = [r for r in reasons if r == "gap_fill_incomplete"]
        if source == "store" and (index is None or pd.Timestamp(D) not in index.index):
            global_reasons.append("benchmark_unavailable")
        ctx = build_context(
            panel, D, data_dir=root, index=index, sources=_sources(source, panel, D, index, fallback),
            run_reasons=global_reasons, git_sha=_git_sha(), on_stage=set_stage,
        )
        snap = root / "snapshots" / D.isoformat() / "features.parquet"
        snap.parent.mkdir(parents=True, exist_ok=True)
        tmp = snap.with_name(f".features.parquet.tmp{os.getpid()}")
        ctx.raw_day.to_parquet(tmp)
        os.replace(tmp, snap)

        set_stage("fundamentals")
        latest = _latest_symbols(panel)
        entities = store.load_entities(root)
        uni_ids = sorted(ctx.universe, key=lambda e: str(latest.get(e, e)))
        extra_ids = []
        for s in extra:
            eid = _resolve(s, latest, D, entities)
            if eid is None:
                log.info("extra symbol %s does not resolve to an entity; skipped", s)
            elif eid not in ctx.universe and eid not in extra_ids:
                extra_ids.append(eid)
        item_ids = [*uni_ids, *extra_ids]
        symbols = {e: str(latest[e]) for e in item_ids}
        payloads = _payloads(symbols.values(), fundamentals_mode, root, FetchBudget())
        uni_symbols = {symbols[e] for e in uni_ids}

        set_stage("assemble")
        lines: list[str] = []
        counts = RunCounts()
        failed_symbols: list[str] = []
        for e in item_ids:
            sym = symbols[e]
            try:
                report = assemble_report(ctx, e, payload=payloads.get(sym), fundamentals_mode=fundamentals_mode,
                                         peer_pes=_peer_pes(sym, payloads, uni_symbols), origin="nightly")
                preds = predictions_for(ctx, e, report)
                item = RunItem(report=report, predictions=preds)
            except Exception as exc:  # one bad symbol never sinks the run; it is reported
                log.exception("assembly failed for %s: %s", sym, exc)
                failed_symbols.append(sym)
                continue
            lines.append(item.model_dump_json())
            counts.reports += 1
            counts.predictions += len(preds)
            counts.degraded += report.status == "degraded"
            counts.quarantined += "data_quality_flag" in report.degraded_reasons
            reasons.extend(r for r in report.degraded_reasons if r != "stale_prices")
        day = panel.loc[panel["date"] == pd.Timestamp(D)]
        counts.ca_unverified = int((day["event"] == "ca_unverified").sum())
        if failed_symbols:
            reasons.append("assemble_failed:" + ",".join(failed_symbols[:20]))
        _atomic(rdir / "items.jsonl", "".join(line + "\n" for line in lines).encode("utf-8"))
        run_reasons = list(dict.fromkeys(reasons))
        status.counts = counts
        status.status = "degraded" if run_reasons else "ok"
        status.error = ";".join(run_reasons) or None
    except Exception as exc:
        log.exception("research run %s failed at stage %s", rid, status.stage)
        status.status = "failed"
        status.error = f"{type(exc).__name__}: {exc}"[:500]
    status.finished_at = _now()
    _write_status(rdir, status)
    return status


def read_items(data_dir: str | Path | None, run_id: str) -> list[RunItem]:
    """All items of a finished run (empty when the run wrote none)."""
    path = (Path(data_dir) if data_dir else config.DATA_DIR) / "runs" / run_id / "items.jsonl"
    if not path.exists():
        return []
    return [RunItem.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# ── on-demand compute ───────────────────────────────────────────────────────


def compute_symbol(
    symbol: str,
    *,
    as_of: date | None = None,
    source: PanelSource = "store",
    data_dir: str | Path | None = None,
    fundamentals_mode: FundamentalsMode = "fetch",
) -> ResearchReport:
    """On-demand report (origin ``on_demand``, no ledger rows) for one symbol (spec 2.3, D23).

    ``as_of`` defaults to the latest stored session. Raises UnknownSymbol when the
    symbol resolves to no entity, InsufficientHistory under 60 sessions.
    """
    root = Path(data_dir) if data_dir else config.DATA_DIR
    end = as_of or datetime.now(IST).date()
    panel = _load_window(end, source, root)
    if panel.empty:
        raise UnknownSymbol(symbol)
    D = as_timestamp(panel["date"].max()).date()
    latest = _latest_symbols(panel)
    eid = _resolve(symbol, latest, D, store.load_entities(root))
    if eid is None:
        raise UnknownSymbol(symbol)
    rows = panel.loc[panel["entity_id"] == eid]
    if int(rows["px_idx"].notna().sum()) < MIN_COMPUTE_SESSIONS:
        raise InsufficientHistory(f"{symbol}: fewer than {MIN_COMPUTE_SESSIONS} sessions of history")
    index = store.load_index("NIFTY50", end=D, data_dir=root)
    ctx = build_context(panel, D, data_dir=root, index=index, sources=_sources(source, panel, D, index, False),
                        git_sha=_git_sha())
    sym = str(latest[eid])
    uni_symbols = {str(latest[e]) for e in ctx.universe}
    payloads = _payloads(sorted(uni_symbols - {sym}), fundamentals_mode, root, None)  # peers: cache only
    payloads.update(_payloads([sym], fundamentals_mode, root, FetchBudget(1)))  # one refresh at most
    return assemble_report(ctx, eid, payload=payloads.get(sym), fundamentals_mode=fundamentals_mode,
                           peer_pes=_peer_pes(sym, payloads, uni_symbols), origin="on_demand")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m research.pipeline", description="Nightly research run")
    ap.add_argument("--as-of", type=date.fromisoformat, required=True, help="market date D (YYYY-MM-DD)")
    ap.add_argument("--source", choices=("store", "local_csv"), default="store")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--extra-symbols", default="", help="comma-separated NSE symbols outside the universe")
    ap.add_argument("--fundamentals", choices=("fetch", "skip"), default="fetch")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    status = run_nightly(
        args.as_of, [s for s in args.extra_symbols.split(",") if s.strip()], args.source,
        args.data_dir, args.fundamentals,
    )
    print(json.dumps(json.loads(status.model_dump_json()), sort_keys=True))
    return 1 if status.status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
