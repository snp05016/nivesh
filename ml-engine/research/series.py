"""Series routes for the backend's money features (journal scoring, 31-Jan-2018 FMV, crisis replay).

``window_returns`` answers "how did this stock and the Nifty 50 move over h sessions from a
start date" with the same per-item rule as ``/outcomes`` (``outcomes.realized_window``), and
``raw_highs`` returns the raw (unadjusted) high of the last traded session on or before a date.
Nothing here is written to the prediction ledger.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .labels import STALE_EXIT_SESSIONS
from .marketdata import store
from .outcomes import realized_window
from .report import as_timestamp

__all__ = ["raw_highs", "window_returns"]

_IST = timezone(timedelta(hours=5, minutes=30))
_PAD_BEFORE_DAYS = 15
_PAD_AFTER_DAYS = 30
_RAW_LOOKBACK_DAYS = 15
_LAST_SESSION_LOOKBACK_DAYS = 10

Span = tuple[date, date]


def _today() -> date:
    return datetime.now(_IST).date()


def _merge_spans(spans: Iterable[Span]) -> list[Span]:
    """Merge overlapping or touching date spans, so far-apart items load separate small panels."""
    merged: list[list[date]] = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1] + timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(a, b) for a, b in merged]


def _load(spans: Sequence[Span], source: Literal["store", "local_csv"], data_dir: str | Path | None) -> list[tuple[Span, pd.DataFrame]]:
    return [((lo, hi), store.load_panel(start=lo, end=hi, source=source, data_dir=data_dir)) for lo, hi in spans]


def _panel_for(loaded: Sequence[tuple[Span, pd.DataFrame]], lo: date, hi: date) -> pd.DataFrame | None:
    for (a, b), panel in loaded:
        if a <= lo and hi <= b:
            return panel
    return None


def _last_session(source: Literal["store", "local_csv"], data_dir: str | Path | None, today: date) -> str | None:
    panel = store.load_panel(start=today - timedelta(days=_LAST_SESSION_LOOKBACK_DAYS), end=today, source=source, data_dir=data_dir)
    cal = store.sessions(panel)
    return as_timestamp(cal[-1]).date().isoformat() if len(cal) else None


def _entity(entities: pd.DataFrame, item: Mapping[str, Any]) -> str | None:
    return store.resolve_entity(symbol=item.get("symbol"), isin=item.get("isin"), as_of=None, entities=entities)


def _valid(rows: pd.DataFrame) -> pd.DataFrame:
    ok = rows["px_idx"].astype(float) > 0
    return rows.loc[ok & ~rows["quality_flags"].astype(str).str.contains("suspect", regex=False)]


def _blank(item: Mapping[str, Any], status: str) -> dict[str, Any]:
    return {"key": item["key"], "status": status, "start_date": None, "end_date": None,
            "return_pct": None, "nifty_return_pct": None, "stale_exit": None}


def window_returns(
    items: Sequence[Mapping[str, Any]],
    *,
    source: Literal["store", "local_csv"] = "store",
    data_dir: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """``{"results": [...], "last_session"}``, one result per item in input order.

    Each item: ``key``, ``symbol`` or ``isin``, ``start`` (date) and ``sessions`` (h). Status
    ``ok`` (start_date, end_date, return_pct, nifty_return_pct, stale_exit), ``pending`` (fewer
    than h sessions since the start session), ``unknown_symbol`` or ``no_data`` (no valid
    close within 5 sessions on or before the start, or a void start).
    """
    today = today or _today()
    last = _last_session(source, data_dir, today)
    if not items:
        return {"results": [], "last_session": last}
    entities = store.load_entities(data_dir)
    index = store.load_index("NIFTY50", data_dir=data_dir)
    spans: list[Span] = []
    for it in items:
        lo = it["start"] - timedelta(days=_PAD_BEFORE_DAYS)
        hi = min(today, it["start"] + timedelta(days=math.ceil(it["sessions"] * 7 / 5) + _PAD_AFTER_DAYS))
        spans.append((lo, max(lo, hi)))
    loaded = _load(_merge_spans(spans), source, data_dir)
    cache: dict[int, tuple[pd.DatetimeIndex, dict[str, Any]]] = {}

    results: list[dict[str, Any]] = []
    for it, (lo, hi) in zip(items, spans):
        panel = _panel_for(loaded, lo, hi)
        eid = _entity(entities, it)
        if eid is None or panel is None:
            results.append(_blank(it, "unknown_symbol"))
            continue
        if id(panel) not in cache:
            cache[id(panel)] = (store.sessions(panel), {str(k): v for k, v in panel.groupby("entity_id", sort=False).indices.items()})
        cal, by_entity = cache[id(panel)]
        if eid not in by_entity:
            results.append(_blank(it, "no_data"))
            continue
        rows = panel.iloc[by_entity[eid]]
        start = pd.Timestamp(it["start"])
        before = _valid(rows).loc[lambda r: r["date"] <= start]
        if before.empty:
            results.append(_blank(it, "no_data"))
            continue
        t = as_timestamp(before["date"].iloc[-1])
        gap = int(((cal > t) & (cal <= start)).sum())
        if gap > STALE_EXIT_SESSIONS:
            results.append(_blank(it, "no_data"))
            continue
        win = realized_window(rows, index, t, int(it["sessions"]), cal)
        if win["status"] == "pending":
            results.append({**_blank(it, "pending"), "start_date": t.date().isoformat()})
        elif win["status"] == "void":
            results.append(_blank(it, "no_data"))
        else:
            nifty = win["nifty50_return_pct"]
            results.append({
                "key": it["key"], "status": "ok",
                "start_date": t.date().isoformat(), "end_date": win["end"].date().isoformat(),
                "return_pct": win["ret"] * 100.0,
                "nifty_return_pct": None if nifty is None else float(nifty),
                "stale_exit": win["stale_exit"],
            })
    return {"results": results, "last_session": last}


def raw_highs(
    items: Sequence[Mapping[str, Any]],
    *,
    source: Literal["store", "local_csv"] = "store",
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """``{"results": [...]}``: the raw high and close of the last traded, non-suspect session
    in [date - 15 days, date]. Status ``ok`` | ``unknown_symbol`` | ``no_trade``."""
    if not items:
        return {"results": []}
    entities = store.load_entities(data_dir)
    spans = [(it["date"] - timedelta(days=_RAW_LOOKBACK_DAYS), it["date"]) for it in items]
    loaded = _load(_merge_spans(spans), source, data_dir)
    indexed: dict[int, dict[str, Any]] = {}

    results: list[dict[str, Any]] = []
    for it, (lo, hi) in zip(items, spans):
        base = {"key": it["key"], "status": "no_trade", "date_used": None, "high": None, "close": None}
        panel = _panel_for(loaded, lo, hi)
        eid = _entity(entities, it)
        if eid is None or panel is None:
            results.append({**base, "status": "unknown_symbol"})
            continue
        if id(panel) not in indexed:
            indexed[id(panel)] = {str(k): v for k, v in panel.groupby("entity_id", sort=False).indices.items()}
        pos = indexed[id(panel)].get(eid)
        if pos is None:
            results.append(base)
            continue
        rows = panel.iloc[pos]
        rows = rows.loc[(rows["date"] >= pd.Timestamp(lo)) & (rows["date"] <= pd.Timestamp(hi))]
        rows = rows.loc[(rows["volume"].astype(float) > 0) & ~rows["quality_flags"].astype(str).str.contains("suspect", regex=False)]
        rows = rows.loc[rows["high"].notna()].sort_values("date")
        if rows.empty:
            results.append(base)
            continue
        last = rows.iloc[-1]
        results.append({**base, "status": "ok", "date_used": as_timestamp(last["date"]).date().isoformat(),
                        "high": float(last["high"]), "close": float(last["close"])})
    return {"results": results}
