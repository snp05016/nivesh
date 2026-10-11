"""
Prediction Outcome Tracker

Nightly job to calculate actual returns for past predictions and compute
hit rates and Brier scores for the ML feedback loop.

Entry and exit prices both come from one auto-adjusted daily series, so splits
and bonuses between the prediction and the run date cancel out (the raw stored
entry_price is never mixed with adjusted history). Labels come from
services.outcome_labels. No DB session is held across network calls.
"""

from datetime import datetime, timezone
import logging
import pandas as pd
from database import get_session
from models.db_models import AnalysisPrediction
from services.outcome_labels import (
    UNRESOLVABLE_AGE_DAYS,
    close_on_or_before,
    direction_hit,
    fetch_adjusted_history,
    signal_direction,
    window_return,
)

_LOG = logging.getLogger(__name__)

HORIZONS = ((7, "7d"), (30, "30d"), (90, "90d"))
BENCHMARK_SYMBOL = "^NSEI"


def _label(p, ret, prefix: str, updates: dict) -> None:
    """Write return, hit (None = abstain) and Brier (only when scored) for one horizon."""
    hit = direction_hit(p.recommendation, ret)
    updates[f"actual_return_{prefix}"] = ret
    updates[f"hit_direction_{prefix}"] = hit
    if hit is not None:
        updates[f"brier_score_{prefix}"] = (p.confidence_pct / 100.0 - (1.0 if hit else 0.0)) ** 2


def _outcome_updates(p, hist, bench, today) -> dict:
    """Column updates for one prediction row (a plain result row, not an ORM object)."""
    anchor = pd.Timestamp(p.input_asof_date or p.created_at.date())
    age_days = (today - anchor).days
    updates = {}

    # No series, or one that does not reach back to the prediction (delisted / renamed).
    # Only age makes it terminal: yfinance returns empty frames during outages too.
    if hist is None or close_on_or_before(hist, anchor) is None:
        updates["outcome_attempts"] = (p.outcome_attempts or 0) + 1
        if age_days > UNRESOLVABLE_AGE_DAYS:
            updates["outcome_status"] = "unresolvable"
        return updates

    filled = {}
    for days, prefix in HORIZONS:
        current = getattr(p, f"actual_return_{prefix}")
        if current is not None:
            filled[prefix] = current
            continue
        if age_days < days:
            continue
        ret = window_return(hist, anchor, anchor + pd.Timedelta(days=days))
        if ret is None:
            continue
        filled[prefix] = ret
        _label(p, ret, prefix, updates)

    # The model's own label horizon (horizon_days trading days, logged as target_date).
    if p.target_date is not None and p.actual_return_target is None and today >= pd.Timestamp(p.target_date):
        ret = window_return(hist, anchor, p.target_date)
        if ret is not None:
            _label(p, ret, "target", updates)

    if "30d" in filled and p.benchmark_return_30d is None:
        bench30 = window_return(bench, anchor, anchor + pd.Timedelta(days=30))
        if bench30 is not None:
            updates["benchmark_return_30d"] = bench30
            updates["hit_vs_benchmark_30d"] = direction_hit(p.recommendation, filled["30d"] - bench30)

    if signal_direction(p.recommendation) == 0:
        if filled:
            updates["outcome_status"] = "abstain"
    elif "90d" in filled:
        updates["outcome_status"] = "scored"
    return updates


def update_prediction_outcomes(dry_run: bool = False) -> dict:
    """Calculates actual returns for predictions where the horizon has passed.

    Args:
        dry_run (bool): If True, rolls back the transaction instead of committing.

    Returns:
        dict: A summary containing counts of eligible predictions, updates for
            different time horizons, missing data, and processed symbols.
    """
    _LOG.info(f"Starting prediction outcome tracking (dry_run={dry_run})...")
    today = pd.Timestamp(datetime.now(timezone.utc).date())

    summary = {
        "eligible_predictions": 0,
        "updates_7d": 0,
        "updates_30d": 0,
        "updates_90d": 0,
        "missing_price_data": 0,
        "unresolvable": 0,
        "processed_symbols": 0
    }

    AP = AnalysisPrediction
    # (a) one short read; plain rows survive the session closing
    with get_session() as session:
        preds = session.query(
            AP.id, AP.symbol, AP.created_at, AP.input_asof_date, AP.recommendation,
            AP.confidence_pct, AP.actual_return_7d, AP.actual_return_30d,
            AP.actual_return_90d, AP.benchmark_return_30d, AP.outcome_attempts,
            AP.target_date, AP.actual_return_target,
        ).filter(
            AP.outcome_status.in_(("pending", "abstain")),
            AP.actual_return_90d.is_(None),
        ).all()

    summary["eligible_predictions"] = len(preds)

    # Group by symbol to batch yfinance calls
    symbol_map = {}
    for p in preds:
        symbol_map.setdefault(p.symbol, []).append(p)
    summary["processed_symbols"] = len(symbol_map)
    if not symbol_map:
        return summary

    # (b) network calls run with no session open
    try:
        bench = fetch_adjusted_history(BENCHMARK_SYMBOL)
    except Exception as e:
        _LOG.warning(f"Benchmark history unavailable: {e}")
        bench = None

    for symbol, pred_list in symbol_map.items():
        try:
            hist = fetch_adjusted_history(symbol)
        except Exception as e:
            _LOG.error(f"Error fetching history for {symbol}: {e}")
            continue
        if hist is None:
            summary["missing_price_data"] += 1  # _outcome_updates counts the attempt

        rows = [(p.id, _outcome_updates(p, hist, bench, today)) for p in pred_list]
        rows = [(pid, upd) for pid, upd in rows if upd]
        if not rows:
            continue

        # (h) one short write per symbol
        try:
            with get_session() as session:
                for pid, upd in rows:
                    session.query(AP).filter(AP.id == pid).update(upd, synchronize_session=False)
                if dry_run:
                    session.rollback()
                else:
                    session.commit()
        except Exception as e:
            _LOG.error(f"Error saving outcomes for {symbol}: {e}")
            continue

        for _, upd in rows:
            for _, prefix in HORIZONS:
                if f"actual_return_{prefix}" in upd:
                    summary[f"updates_{prefix}"] += 1
            if upd.get("outcome_status") == "unresolvable":
                summary["unresolvable"] += 1

    _LOG.info(f"Finished prediction outcome tracking. Summary: {summary}")
    return summary
