"""Outcome scoring for ledger predictions, scorer ``os-2`` (spec 8.4; one rule with ``labels.make_labels``).

For a prediction made on session t at horizon h:

- the entity comes from ``resolve_entity(isin, symbol, as_of)``;
- ``pending`` until h true sessions of the panel calendar have passed;
- ``void`` only for ``entry_price_mismatch`` (the stored raw close on t differs
  from ``entry_close`` by more than 0.01%, or no row exists on t) or
  ``suspect_price`` (the close on t is suspect or carries no ``px_idx``; training
  drops the same labels);
- otherwise ``matured``: px_exit is the last valid ``px_idx`` on or before
  session t+h and ``stale_exit`` is set when that row is more than 5 sessions
  before t+h (delisted, suspended, untraded). Delisting is an outcome, not a void.
- ``realized_excess_pp`` and ``realized_top_half`` compare the simple return with
  the median over U_t of the same labels (``make_labels``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from . import config
from .contract import OutcomeRequestItem, OutcomeResult
from .labels import STALE_EXIT_SESSIONS, make_labels
from .marketdata import store
from .report import as_timestamp

__all__ = ["realized_window", "score_outcomes"]

SCORER_VERSION = config.OUTCOMES["scorer_version"]
ENTRY_TOLERANCE = config.OUTCOMES["entry_price_tolerance"]


def _result(item: OutcomeRequestItem, status: str, **kw: Any) -> OutcomeResult:
    base: dict[str, Any] = {
        "prediction_id": item.prediction_id, "outcome_status": status, "void_reason": None,
        "realized_return_pct": None, "realized_excess_pp": None, "realized_top_half": None,
        "nifty50_return_pct": None, "stale_exit": None, "scorer_version": SCORER_VERSION,
    }
    return OutcomeResult.model_validate({**base, **kw})


def _entity(item: OutcomeRequestItem, panel: pd.DataFrame, entities: pd.DataFrame) -> str | None:
    eid = store.resolve_entity(symbol=item.symbol, isin=item.isin, as_of=item.as_of, entities=entities)
    known = panel["entity_id"].astype(str)
    if eid is not None and bool((known == eid).any()):
        return eid
    sym = item.symbol.strip().upper().removesuffix(".NS")
    for col, val in (("isin", item.isin), ("symbol", sym)):
        hits = panel.loc[panel[col].astype(str) == val, "entity_id"] if val else None
        if hits is not None and len(hits):
            return str(hits.iloc[-1])
    return None


def _index_return(index: pd.Series | None, t: pd.Timestamp, end: pd.Timestamp) -> float | None:
    if index is None:
        return None
    s = index.sort_index().dropna()
    a, b = s.loc[:t], s.loc[:end]
    if a.empty or b.empty:
        return None
    return float((b.iloc[-1] / a.iloc[-1] - 1.0) * 100.0)


def realized_window(
    rows: pd.DataFrame,
    index: pd.Series | None,
    t: pd.Timestamp,
    h: int,
    cal: pd.DatetimeIndex,
    entry_close: float | None = None,
) -> dict[str, Any]:
    """The per-item rule of ``score_outcomes`` for one entity, start session ``t`` and horizon ``h``.

    ``rows`` are the entity's panel rows (any order; may be empty), ``cal`` the session
    calendar. Returns ``status`` (pending | void | matured) and ``void_reason``; a matured
    window adds ``ret`` (simple px_idx return), ``end`` (the h-th true session),
    ``exit_date``, ``stale_exit`` and ``nifty50_return_pct``. ``entry_close`` None skips the
    stored-close check (series callers have no recorded entry price).
    """
    k = int(cal.get_indexer([t])[0])
    if k < 0 or k + h > len(cal) - 1:
        return {"status": "pending", "void_reason": None}
    rows = rows.sort_values("date")
    entry = rows.loc[rows["date"] == t]
    if entry.empty:
        return {"status": "void", "void_reason": "entry_price_mismatch"}
    if entry_close is not None:
        close_t = float(entry["close"].iloc[0])
        if abs(entry_close - close_t) / entry_close > ENTRY_TOLERANCE:
            return {"status": "void", "void_reason": "entry_price_mismatch"}
    px_t = float(entry["px_idx"].iloc[0])
    if "suspect" in str(entry["quality_flags"].iloc[0]) or not np.isfinite(px_t) or px_t <= 0:
        return {"status": "void", "void_reason": "suspect_price"}
    end = as_timestamp(cal[k + h])
    later = rows.loc[(rows["date"] >= t) & (rows["date"] <= end)]
    later = later.loc[later["px_idx"].to_numpy(dtype=float) > 0]
    later = later.loc[~later["quality_flags"].astype(str).str.contains("suspect", regex=False)]
    exit_date = as_timestamp(later["date"].iloc[-1])
    return {
        "status": "matured", "void_reason": None,
        "ret": float(later["px_idx"].iloc[-1]) / px_t - 1.0,
        "end": end, "exit_date": exit_date,
        "stale_exit": bool(k + h - int(cal.get_loc(exit_date)) > STALE_EXIT_SESSIONS),
        "nifty50_return_pct": _index_return(index, t, end),
    }


def score_outcomes(
    items: Iterable[OutcomeRequestItem | Mapping[str, Any]],
    panel: pd.DataFrame,
    membership: pd.DataFrame,
    index: pd.Series | None,
    *,
    data_dir: str | Path | None = None,
) -> list[OutcomeResult]:
    """One OutcomeResult per item, in input order.

    ``panel`` (3.3) must reach back to the earliest ``as_of``; ``membership`` is
    ``universe.membership(panel)``; ``index`` is the NIFTY50_PR close series (or None).
    """
    reqs = [i if isinstance(i, OutcomeRequestItem) else OutcomeRequestItem.model_validate(i) for i in items]
    if not reqs:
        return []
    cal = store.sessions(panel)
    horizons = tuple(sorted({r.horizon_days for r in reqs}))
    first = as_timestamp(min(r.as_of for r in reqs))
    # Labels from the earliest as-of on (the exit lies on or after t, so nothing earlier matters).
    window = panel.loc[panel["date"] >= first]
    mem_window = membership.loc[pd.to_datetime(membership["date"]) >= first]
    labels = make_labels(window, mem_window, horizons=horizons) if len(window) else None
    medians: dict[int, pd.Series] = {}
    if labels is not None:
        for h in horizons:
            ret = cast(pd.Series, labels[f"ret_{h}"]).dropna()
            medians[h] = cast(pd.Series, ret.groupby(level="date").median())

    by_entity = {str(k): v for k, v in panel.groupby("entity_id", sort=False).indices.items()}
    entities = store.load_entities(data_dir)
    out: list[OutcomeResult] = []
    for item in reqs:
        h = item.horizon_days
        t = as_timestamp(item.as_of)
        eid = _entity(item, panel, entities)
        rows = panel.iloc[by_entity[eid]] if eid in by_entity else panel.iloc[0:0]
        win = realized_window(rows, index, t, h, cal, entry_close=item.entry_close)
        if win["status"] == "pending":
            out.append(_result(item, "pending"))
            continue
        if win["status"] == "void":
            out.append(_result(item, "void", void_reason=win["void_reason"]))
            continue
        ret = win["ret"]
        med = medians.get(h, pd.Series(dtype=float)).get(t)
        out.append(_result(
            item, "matured",
            realized_return_pct=ret * 100.0,
            realized_excess_pp=None if med is None or not np.isfinite(med) else (ret - float(med)) * 100.0,
            realized_top_half=None if med is None or not np.isfinite(med) else bool(ret > float(med)),
            nifty50_return_pct=win["nifty50_return_pct"],
            stale_exit=win["stale_exit"],
        ))
    return out
