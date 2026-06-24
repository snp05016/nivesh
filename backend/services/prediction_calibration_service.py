"""
Prediction Calibration Service

Computes calibration metrics, pillar attribution analysis, and model version
analytics for the AnalysisPrediction table. All functions are safe against
empty tables, missing values, and division by zero.
"""

from typing import Any, Dict, List, Optional, Tuple
import math

from sqlalchemy import func, case, cast, Float
from database import get_session
from models.db_models import AnalysisPrediction, StockUniverse


# ---------------------------------------------------------------------------
# Confidence buckets for calibration analysis
# ---------------------------------------------------------------------------

CONFIDENCE_BUCKETS: List[Tuple[int, int, str]] = [
    (0, 50, "0-50%"),
    (50, 60, "50-60%"),
    (60, 70, "60-70%"),
    (70, 80, "70-80%"),
    (80, 90, "80-90%"),
    (90, 100, "90-100%"),
]

PILLAR_COLUMNS = [
    "llm_confidence",
    "quant_confidence",
    "venn_abers_confidence",
    "signal_agreement",
    "ml_confidence",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any) -> Optional[float]:
    """Convert a SQLAlchemy result to float, returning None for None/NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_avg(expr):
    """Wrap an aggregate so division by zero returns None."""
    return func.coalesce(func.avg(cast(expr, Float)), None)


def _safe_hit_rate(hit_col):
    """Compute hit rate as fraction of non-null hit_direction values that are TRUE."""
    total = func.count(case((hit_col.isnot(None), 1)))
    hits = func.count(case((hit_col.is_(True), 1)))
    return func.coalesce(
        case((total > 0, func.round(cast(hits, Float) / cast(total, Float), 4)), else_=None),
        None,
    )


def _point_biserial(pillar_values: List[float], hit_values: List[bool]) -> Optional[float]:
    """
    Compute point-biserial correlation between a continuous pillar and boolean hit.

    r = (M1 - M0) / S * sqrt(n1 * n0 / n^2)

    Returns None if stddev is 0, counts are 0, or insufficient data.
    """
    if len(pillar_values) != len(hit_values) or len(pillar_values) < 2:
        return None

    group_true: List[float] = []
    group_false: List[float] = []

    for pv, hv in zip(pillar_values, hit_values):
        if hv:
            group_true.append(pv)
        else:
            group_false.append(pv)

    n1 = len(group_true)
    n0 = len(group_false)
    n = n1 + n0

    if n1 == 0 or n0 == 0 or n < 2:
        return None

    m1 = sum(group_true) / n1
    m0 = sum(group_false) / n0

    # Overall standard deviation
    mean_all = sum(pillar_values) / n
    variance = sum((x - mean_all) ** 2 for x in pillar_values) / n
    if variance <= 0:
        return None
    s = math.sqrt(variance)

    r = (m1 - m0) / s * math.sqrt(n1 * n0 / (n * n))
    # Clamp to [-1, 1] for floating-point safety
    return max(-1.0, min(1.0, round(r, 4)))


def _bucket_equal_width(values: List[float], n_buckets: int = 5) -> List[Tuple[float, float]]:
    """Return n equal-width bucket boundaries from min to max of values."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if lo == hi:
        return [(lo, hi)]
    step = (hi - lo) / n_buckets
    return [(lo + i * step, lo + (i + 1) * step) for i in range(n_buckets)]


# ---------------------------------------------------------------------------
# 1. get_calibration_metrics
# ---------------------------------------------------------------------------

def get_calibration_metrics() -> Dict[str, Any]:
    """
    Compute confidence calibration metrics across buckets, horizons,
    and categorical groupings.
    """
    with get_session() as session:
        total = session.query(func.count(AnalysisPrediction.id)).scalar() or 0

        if total == 0:
            return {
                "total_predictions": 0,
                "confidence_buckets": [],
                "calibration_error": None,
                "expected_calibration_error": None,
                "max_calibration_error": None,
                "hit_rate_by_horizon": {},
                "calibration_by_scan_type": [],
                "calibration_by_regime": [],
                "calibration_by_sector": [],
                "calibration_by_ml_engine_mode": [],
                "calibration_by_recommendation": [],
            }

        # ── Confidence buckets ──
        buckets = _build_calibration_buckets(session)

        # ── Global calibration error metrics ──
        cal_error, ece, mce = _compute_calibration_errors(buckets, total)

        # ── Hit rate by horizon ──
        hit_by_horizon = _compute_hit_rate_by_horizon(session)

        # ── Group calibrations ──
        by_scan_type = _build_group_calibration(session, AnalysisPrediction.scan_type)
        by_regime = _build_group_calibration(session, AnalysisPrediction.regime_id)
        by_sector = _build_sector_calibration(session)
        by_ml_mode = _build_group_calibration(session, AnalysisPrediction.ml_engine_mode)
        by_rec = _build_group_calibration(session, AnalysisPrediction.recommendation)

        return {
            "total_predictions": total,
            "confidence_buckets": buckets,
            "calibration_error": cal_error,
            "expected_calibration_error": ece,
            "max_calibration_error": mce,
            "hit_rate_by_horizon": hit_by_horizon,
            "calibration_by_scan_type": by_scan_type,
            "calibration_by_regime": by_regime,
            "calibration_by_sector": by_sector,
            "calibration_by_ml_engine_mode": by_ml_mode,
            "calibration_by_recommendation": by_rec,
        }


def _build_calibration_buckets(session) -> List[Dict[str, Any]]:
    """Compute per-bucket calibration stats."""
    results = []
    for lo, hi, label in CONFIDENCE_BUCKETS:
        base_filter = [
            AnalysisPrediction.confidence_pct >= lo,
            AnalysisPrediction.confidence_pct <= hi,
        ]

        count_val = (
            session.query(func.count(AnalysisPrediction.id))
            .filter(*base_filter)
            .scalar()
        ) or 0

        stats = (
            session.query(
                _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
                _safe_avg(AnalysisPrediction.brier_score_30d),
                _safe_avg(AnalysisPrediction.confidence_pct),
            )
            .filter(*base_filter)
            .first()
        )

        accuracy = _safe_float(stats[0]) if stats else None
        avg_brier = _safe_float(stats[1]) if stats else None
        avg_conf = _safe_float(stats[2]) if stats else None

        overconfidence = None
        if avg_conf is not None and accuracy is not None:
            overconfidence = round(avg_conf / 100.0 - accuracy, 4)

        results.append({
            "bucket_label": label,
            "count": count_val,
            "accuracy": accuracy,
            "avg_brier_score_30d": avg_brier,
            "avg_confidence_pct": avg_conf,
            "overconfidence": overconfidence,
        })
    return results


def _compute_calibration_errors(
    buckets: List[Dict[str, Any]], total: int
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute weighted calibration error, ECE, and MCE from bucket stats.
    """
    if total == 0:
        return None, None, None

    weighted_sum = 0.0
    ece_sum = 0.0
    mce_val = 0.0
    total_counted = 0
    has_data = False

    for b in buckets:
        accuracy = b.get("accuracy")
        avg_conf = b.get("avg_confidence_pct")
        count = b.get("count", 0)

        if accuracy is None or avg_conf is None or count == 0:
            continue

        has_data = True
        gap = abs(accuracy - avg_conf / 100.0)
        weighted_sum += count * gap
        total_counted += count
        ece_sum += (count / total) * gap
        mce_val = max(mce_val, gap)

    if not has_data:
        return None, None, None

    cal_error = round(weighted_sum / total_counted, 4) if total_counted > 0 else None
    ece = round(ece_sum, 4)
    mce = round(mce_val, 4)
    return cal_error, ece, mce


def _compute_hit_rate_by_horizon(session) -> Dict[str, Dict[str, Any]]:
    """Compute matured count and hit rate for 7d, 30d, 90d horizons."""
    result = {}
    for prefix in ("7d", "30d", "90d"):
        hit_attr = f"hit_direction_{prefix}"
        if not hasattr(AnalysisPrediction, hit_attr):
            continue

        hit_col = getattr(AnalysisPrediction, hit_attr)
        stats = session.query(
            func.count(case((hit_col.isnot(None), 1))),
            _safe_hit_rate(hit_col),
        ).first()

        result[prefix] = {
            "matured_count": (stats[0] or 0) if stats else 0,
            "hit_rate": _safe_float(stats[1]) if stats else None,
        }
    return result


def _build_group_calibration(session, column) -> List[Dict[str, Any]]:
    """Generic GROUP BY calibration for a categorical column."""
    rows = (
        session.query(
            column,
            func.count(AnalysisPrediction.id),
            _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
            _safe_avg(AnalysisPrediction.brier_score_30d),
            _safe_avg(AnalysisPrediction.confidence_pct),
        )
        .filter(column.isnot(None))
        .group_by(column)
        .order_by(func.count(AnalysisPrediction.id).desc())
        .all()
    )
    results = []
    for r in rows:
        if r[1] == 0:
            continue
        accuracy = _safe_float(r[2])
        avg_conf = _safe_float(r[4])
        cal_err = None
        if accuracy is not None and avg_conf is not None:
            cal_err = round(abs(accuracy - avg_conf / 100.0), 4)

        results.append({
            "group_key": r[0] or "unknown",
            "count": r[1],
            "accuracy": accuracy,
            "avg_brier_score_30d": _safe_float(r[3]),
            "avg_confidence_pct": avg_conf,
            "calibration_error": cal_err,
        })
    return results


def _build_sector_calibration(session) -> List[Dict[str, Any]]:
    """Sector calibration via JOIN with StockUniverse."""
    rows = (
        session.query(
            StockUniverse.sector,
            func.count(AnalysisPrediction.id),
            _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
            _safe_avg(AnalysisPrediction.brier_score_30d),
            _safe_avg(AnalysisPrediction.confidence_pct),
        )
        .join(StockUniverse, AnalysisPrediction.symbol == StockUniverse.ticker, isouter=True)
        .filter(AnalysisPrediction.symbol.isnot(None))
        .group_by(StockUniverse.sector)
        .order_by(func.count(AnalysisPrediction.id).desc())
        .all()
    )
    results = []
    for r in rows:
        if r[1] == 0:
            continue
        accuracy = _safe_float(r[2])
        avg_conf = _safe_float(r[4])
        cal_err = None
        if accuracy is not None and avg_conf is not None:
            cal_err = round(abs(accuracy - avg_conf / 100.0), 4)

        results.append({
            "group_key": r[0] or "unknown",
            "count": r[1],
            "accuracy": accuracy,
            "avg_brier_score_30d": _safe_float(r[3]),
            "avg_confidence_pct": avg_conf,
            "calibration_error": cal_err,
        })
    return results


# ---------------------------------------------------------------------------
# 2. get_pillar_attribution
# ---------------------------------------------------------------------------

def get_pillar_attribution() -> Dict[str, Any]:
    """
    Analyse how each confidence pillar correlates with prediction accuracy.
    Uses point-biserial correlation, bucketed accuracy, and predictive lift.
    """
    with get_session() as session:
        total = session.query(func.count(AnalysisPrediction.id)).scalar() or 0

        if total == 0:
            return {
                "total_predictions": 0,
                "pillars": {},
                "usefulness_ranking": [],
            }

        # Fetch all rows with hit_direction_30d non-null for correlation
        hit_col = AnalysisPrediction.hit_direction_30d
        conf_col = AnalysisPrediction.confidence_pct

        # Load rows needed for correlation calculations
        cols_to_fetch = [hit_col, conf_col] + [
            getattr(AnalysisPrediction, p) for p in PILLAR_COLUMNS
        ]
        raw_rows = (
            session.query(*cols_to_fetch)
            .filter(hit_col.isnot(None))
            .all()
        )

        # Total rows including those without hit data (for missing_rate)
        total_rows_all = total

        # Build per-pillar stats
        # First compute baseline: correlation of confidence_pct with hit_30d
        conf_values = []
        hit_values_for_conf = []
        for row in raw_rows:
            if row[1] is not None:
                conf_values.append(float(row[1]))
                hit_values_for_conf.append(bool(row[0]))

        baseline_corr = _point_biserial(conf_values, hit_values_for_conf)

        # Count nulls per pillar across ALL predictions
        pillar_null_counts = {}
        for i, pillar_name in enumerate(PILLAR_COLUMNS):
            pillar_col = getattr(AnalysisPrediction, pillar_name)
            null_count = (
                session.query(func.count(AnalysisPrediction.id))
                .filter(pillar_col.is_(None))
                .scalar()
            ) or 0
            pillar_null_counts[pillar_name] = null_count

        pillars_result = {}
        correlation_abs = {}

        for i, pillar_name in enumerate(PILLAR_COLUMNS):
            col_index = i + 2  # offset by hit_col and conf_col

            # Extract non-null pairs for this pillar
            pillar_vals = []
            hit_vals = []
            for row in raw_rows:
                pv = row[col_index]
                if pv is not None:
                    pillar_vals.append(float(pv))
                    hit_vals.append(bool(row[0]))

            # Correlation
            corr = _point_biserial(pillar_vals, hit_vals)

            # Bucketed accuracy
            bucketed = _compute_bucketed_accuracy(pillar_vals, hit_vals)

            # Avg brier score for non-null pillar rows
            pillar_col = getattr(AnalysisPrediction, pillar_name)
            avg_brier_row = (
                session.query(_safe_avg(AnalysisPrediction.brier_score_30d))
                .filter(pillar_col.isnot(None))
                .first()
            )
            avg_brier = _safe_float(avg_brier_row[0]) if avg_brier_row else None

            # Predictive lift
            lift = None
            if corr is not None and baseline_corr is not None:
                lift = round(corr - baseline_corr, 4)

            # Missing rate
            null_count = pillar_null_counts[pillar_name]
            missing_rate = round(null_count / total_rows_all, 4) if total_rows_all > 0 else None

            pillars_result[pillar_name] = {
                "correlation_with_hit_30d": corr,
                "bucketed_accuracy": bucketed,
                "avg_brier_score_30d": avg_brier,
                "predictive_lift": lift,
                "missing_rate": missing_rate,
                "sample_size": len(pillar_vals),
            }

            if corr is not None:
                correlation_abs[pillar_name] = abs(corr)

        # Usefulness ranking by abs(correlation)
        ranked = sorted(correlation_abs.items(), key=lambda x: x[1], reverse=True)
        for rank_idx, (pname, _) in enumerate(ranked):
            pillars_result[pname]["usefulness_rank"] = rank_idx + 1

        # Assign None rank to pillars without correlation
        for pname in PILLAR_COLUMNS:
            if "usefulness_rank" not in pillars_result[pname]:
                pillars_result[pname]["usefulness_rank"] = None

        return {
            "total_predictions": total,
            "baseline_confidence_correlation": baseline_corr,
            "pillars": pillars_result,
            "usefulness_ranking": [p[0] for p in ranked],
        }


def _compute_bucketed_accuracy(
    pillar_vals: List[float], hit_vals: List[bool], n_buckets: int = 5
) -> List[Dict[str, Any]]:
    """Group pillar values into equal-width buckets and compute hit rate per bucket."""
    if not pillar_vals:
        return []

    boundaries = _bucket_equal_width(pillar_vals, n_buckets)
    if not boundaries:
        return []

    buckets: List[Dict[str, Any]] = []
    for b_lo, b_hi in boundaries:
        hits = 0
        total = 0
        for pv, hv in zip(pillar_vals, hit_vals):
            # Include lower bound, include upper bound on last bucket
            in_bucket = (pv >= b_lo and pv < b_hi) or (
                b_hi == boundaries[-1][1] and pv == b_hi
            )
            if in_bucket:
                total += 1
                if hv:
                    hits += 1

        hit_rate = round(hits / total, 4) if total > 0 else None
        buckets.append({
            "range": f"{round(b_lo, 3)}-{round(b_hi, 3)}",
            "count": total,
            "hit_rate": hit_rate,
        })
    return buckets


# ---------------------------------------------------------------------------
# 3. get_model_version_analytics
# ---------------------------------------------------------------------------

def get_model_version_analytics() -> Dict[str, Any]:
    """
    Compute per-model-version performance analytics including hit rates,
    returns, Brier scores, and calibration error.
    """
    with get_session() as session:
        total = session.query(func.count(AnalysisPrediction.id)).scalar() or 0

        if total == 0:
            return {
                "total_predictions": 0,
                "model_versions": [],
            }

        # Build subquery for most-common ml_engine_mode per model_version
        # Use a separate query since SQLite lacks window functions in older versions
        rows = (
            session.query(
                AnalysisPrediction.model_version,
                func.count(AnalysisPrediction.id).label("total_preds"),
                _safe_hit_rate(AnalysisPrediction.hit_direction_7d),
                _safe_hit_rate(AnalysisPrediction.hit_direction_30d),
                _safe_hit_rate(AnalysisPrediction.hit_direction_90d),
                _safe_avg(AnalysisPrediction.actual_return_30d),
                _safe_avg(AnalysisPrediction.brier_score_30d),
                _safe_avg(AnalysisPrediction.confidence_pct),
            )
            .filter(AnalysisPrediction.model_version.isnot(None))
            .group_by(AnalysisPrediction.model_version)
            .order_by(func.count(AnalysisPrediction.id).desc())
            .all()
        )

        versions = []
        for r in rows:
            if r[1] == 0:
                continue

            model_ver = r[0]
            total_preds = r[1]
            hr_7d = _safe_float(r[2])
            hr_30d = _safe_float(r[3])
            hr_90d = _safe_float(r[4])
            avg_ret_30d = _safe_float(r[5])
            brier_30d = _safe_float(r[6])
            conf_avg = _safe_float(r[7])

            # Calibration error for 30d
            cal_err = None
            if hr_30d is not None and conf_avg is not None:
                cal_err = round(abs(hr_30d - conf_avg / 100.0), 4)

            # Confidence-realized accuracy gap
            gap = None
            if hr_30d is not None and conf_avg is not None:
                gap = round(conf_avg / 100.0 - hr_30d, 4)

            # Most common ml_engine_mode for this model version
            mode_row = (
                session.query(
                    AnalysisPrediction.ml_engine_mode,
                    func.count(AnalysisPrediction.id).label("cnt"),
                )
                .filter(AnalysisPrediction.model_version == model_ver)
                .filter(AnalysisPrediction.ml_engine_mode.isnot(None))
                .group_by(AnalysisPrediction.ml_engine_mode)
                .order_by(func.count(AnalysisPrediction.id).desc())
                .first()
            )
            ml_mode = mode_row[0] if mode_row else None

            versions.append({
                "model_version": model_ver,
                "ml_engine_mode": ml_mode,
                "total_predictions": total_preds,
                "hit_rate_7d": hr_7d,
                "hit_rate_30d": hr_30d,
                "hit_rate_90d": hr_90d,
                "average_return_30d": avg_ret_30d,
                "brier_score_30d": brier_30d,
                "calibration_error_30d": cal_err,
                "confidence_avg": conf_avg,
                "confidence_realized_accuracy_gap": gap,
            })

        return {
            "total_predictions": total,
            "model_versions": versions,
        }
