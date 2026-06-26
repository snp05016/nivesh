"""
Prediction Performance Analytics Service

Queries the AnalysisPrediction table to compute hit rates, average returns,
Brier scores, and confidence calibration across multiple dimensions.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from sqlalchemy import func, case, cast, Float
from database import get_session
from models.db_models import AnalysisPrediction, StockUniverse

CONFIDENCE_BUCKETS = [
    (0,  20,  "0–20%"),
    (21, 40,  "21–40%"),
    (41, 60,  "41–60%"),
    (61, 80,  "61–80%"),
    (81, 100, "81–100%"),
]

def _safe_avg(expr):
    """Wrap an aggregate expr so division by zero returns None instead of an error.

    Args:
        expr: The SQLAlchemy expression to average.

    Returns:
        SQLAlchemy expression: The wrapped average expression.
    """
    return func.coalesce(func.avg(cast(expr, Float)), None)

def _safe_hit_rate(hit_col):
    """Compute hit rate as fraction of non-null hit_direction values that are TRUE.

    Args:
        hit_col: The SQLAlchemy column representing hit direction.

    Returns:
        SQLAlchemy expression: The calculated hit rate or None.
    """
    total = func.count(case((hit_col.isnot(None), 1)))
    hits = func.count(case((hit_col.is_(True), 1)))
    return func.coalesce(
        case((total > 0, func.round(cast(hits, Float) / cast(total, Float), 4)), else_=None),
        None,
    )

def _build_bucket_queries(session) -> List[Dict[str, Any]]:
    """Builds calibration buckets based on predefined confidence intervals.

    Args:
        session: The SQLAlchemy database session.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing statistics
            for a specific confidence bucket.
    """
    rows = []
    for lo, hi, label in CONFIDENCE_BUCKETS:
        count_q = (
            session.query(func.count(AnalysisPrediction.id))
            .filter(AnalysisPrediction.confidence_pct >= lo)
            .filter(AnalysisPrediction.confidence_pct <= hi)
        ).scalar() or 0

        stats = (
            session.query(
                _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
                _safe_avg(AnalysisPrediction.actual_return_30d),
                _safe_avg(AnalysisPrediction.brier_score_30d),
            )
            .filter(AnalysisPrediction.confidence_pct >= lo)
            .filter(AnalysisPrediction.confidence_pct <= hi)
            .first()
        )
        rows.append({
            "bucket_label": label,
            "count": count_q,
            "hit_rate_30d": stats[0],
            "avg_return_30d": stats[1],
            "avg_brier_score_30d": stats[2],
        })
    return rows


def _build_group_query(session, column, label_col=None) -> List[Dict[str, Any]]:
    """Generic GROUP BY query for categorical dimensions.

    Args:
        session: The SQLAlchemy database session.
        column: The SQLAlchemy column to group by.
        label_col (optional): The column to use as the label. Defaults to column.

    Returns:
        List[Dict[str, Any]]: A list of grouped statistics.
    """
    if label_col is None:
        label_col = column

    rows = (
        session.query(
            label_col,
            func.count(AnalysisPrediction.id),
            _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
            _safe_avg(AnalysisPrediction.actual_return_30d),
            _safe_avg(AnalysisPrediction.brier_score_30d),
        )
        .filter(column.isnot(None))
        .group_by(label_col)
        .order_by(func.count(AnalysisPrediction.id).desc())
        .all()
    )
    return [
        {
            "group_key": r[0] or "unknown",
            "count": r[1],
            "hit_rate_30d": r[2],
            "avg_return_30d": r[3],
            "avg_brier_score_30d": r[4],
        }
        for r in rows if r[0] is not None and r[1] > 0
    ]


def _build_sector_query(session) -> List[Dict[str, Any]]:
    """Sector breakdown via JOIN with StockUniverse.

    Args:
        session: The SQLAlchemy database session.

    Returns:
        List[Dict[str, Any]]: A list of sector-level performance statistics.
    """
    rows = (
        session.query(
            StockUniverse.sector,
            func.count(AnalysisPrediction.id),
            _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
            _safe_avg(AnalysisPrediction.actual_return_30d),
            _safe_avg(AnalysisPrediction.brier_score_30d),
        )
        .join(StockUniverse, AnalysisPrediction.symbol == StockUniverse.ticker, isouter=True)
        .filter(AnalysisPrediction.symbol.isnot(None))
        .group_by(StockUniverse.sector)
        .order_by(func.count(AnalysisPrediction.id).desc())
        .all()
    )
    return [
        {
            "group_key": r[0] or "unknown",
            "count": r[1],
            "hit_rate_30d": r[2],
            "avg_return_30d": r[3],
            "avg_brier_score_30d": r[4],
        }
        for r in rows if r[1] > 0
    ]


def _available_horizons():
    """Return horizons whose outcome columns actually exist on the model.

    Returns:
        List[Tuple[int, str]]: A list of valid horizons as (days, prefix) tuples.
    """
    horizons = []
    for days, prefix in [(7, "7d"), (30, "30d"), (90, "90d")]:
        hit = f"hit_direction_{prefix}"
        if hasattr(AnalysisPrediction, hit):
            horizons.append((days, prefix))
    return horizons


def get_performance_metrics() -> Dict[str, Any]:
    """Returns a comprehensive performance report for all predictions.

    Returns:
        Dict[str, Any]: A dictionary containing overall performance metrics,
            horizon breakdowns, confidence buckets, and group statistics.
    """
    with get_session() as session:
        total_predictions = session.query(func.count(AnalysisPrediction.id)).scalar() or 0

        # ── Per-horizon stats ──
        by_horizon = {}
        for horizon_days, prefix in _available_horizons():
            hit_col = getattr(AnalysisPrediction, f"hit_direction_{prefix}")
            ret_col = getattr(AnalysisPrediction, f"actual_return_{prefix}")
            brier_col = getattr(AnalysisPrediction, f"brier_score_{prefix}")

            stats = session.query(
                func.count(case((hit_col.isnot(None), 1))),
                _safe_hit_rate(hit_col),
                _safe_avg(ret_col),
                _safe_avg(brier_col),
            ).first()

            by_horizon[prefix] = {
                "matured_count": stats[0] or 0,
                "hit_rate": stats[1],
                "avg_return": stats[2],
                "avg_brier_score": stats[3],
            }

        return {
            "total_predictions": total_predictions,
            "by_horizon": by_horizon,
            "confidence_buckets": _build_bucket_queries(session),
            "by_scan_type": _build_group_query(session, AnalysisPrediction.scan_type),
            "by_sector": _build_sector_query(session),
            "by_regime": _build_group_query(session, AnalysisPrediction.regime_id),
            "by_ml_engine_mode": _build_group_query(session, AnalysisPrediction.ml_engine_mode),
            "by_recommendation": _build_group_query(session, AnalysisPrediction.recommendation),
        }
