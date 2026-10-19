"""
Prediction Calibration Service

Computes calibration metrics, pillar attribution analysis, and model version
analytics for the AnalysisPrediction table. All functions are safe against
empty tables, missing values, and division by zero.
"""

from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, case, cast, Float
from database import get_session
from models.db_models import AnalysisPrediction, StockUniverse


# ---------------------------------------------------------------------------
# Confidence buckets for calibration analysis
# ---------------------------------------------------------------------------

def _safe_hit_rate(hit_col):
    # Lazy: predictions_performance imports CONFIDENCE_BUCKETS from this module, so a
    # top-level import here is a cycle that stops the app from importing at all.
    from services.predictions_performance import _safe_hit_rate as safe_hit_rate

    return safe_hit_rate(hit_col)


CONFIDENCE_BUCKETS: List[Tuple[int, int, str]] = [
    (0, 50, "0-50%"),
    (50, 60, "50-60%"),
    (60, 70, "60-70%"),
    (70, 80, "70-80%"),
    (80, 90, "80-90%"),
    (90, 100, "90-100%"),
]  # half-open [lo, hi) via bucket_filter; the top bucket also takes 100. Shared with predictions_performance.

MIN_BUCKET_N = 10  # matured rows below this: accuracy, overconfidence and CI are suppressed


def bucket_filter(col, lo: int, hi: int) -> list:
    """Filters putting col in the half-open bucket [lo, hi); the top bucket includes 100."""
    return [col >= lo, col <= hi] if hi >= 100 else [col >= lo, col < hi]


def _wilson(hits: int, n: int, z: float = 1.96) -> Tuple[Optional[float], Optional[float]]:
    """95% Wilson score interval for a hit rate of hits/n, or (None, None) if n == 0."""
    if n <= 0:
        return None, None
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def _horizon_cols(horizon: str):
    """(hit, brier) columns for '7d' / '30d' / '90d'."""
    if horizon not in ("7d", "30d", "90d"):
        raise ValueError(f"Unsupported horizon: {horizon!r}")
    return (
        getattr(AnalysisPrediction, f"hit_direction_{horizon}"),
        getattr(AnalysisPrediction, f"brier_score_{horizon}"),
    )

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
    """Convert a SQLAlchemy result to float, returning None for None/NaN.

    Args:
        val: The value to convert.

    Returns:
        Optional[float]: The float representation, or None if invalid.
    """
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_avg(expr):
    """Wrap an aggregate so division by zero returns None.

    Args:
        expr: The SQLAlchemy expression to average.

    Returns:
        SQLAlchemy expression: The wrapped average expression.
    """
    return func.coalesce(func.avg(cast(expr, Float)), None)


def _point_biserial(pillar_values: List[float], hit_values: List[bool]) -> Optional[float]:
    """
    Compute point-biserial correlation between a continuous pillar and boolean hit.

    r = (M1 - M0) / S * sqrt(n1 * n0 / n^2)

    Returns None if stddev is 0, counts are 0, or insufficient data.

    Args:
        pillar_values (List[float]): A list of continuous pillar values.
        hit_values (List[bool]): A list of boolean hit outcomes.

    Returns:
        Optional[float]: The correlation coefficient [-1, 1], or None if invalid.
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
    """Return n equal-width bucket boundaries from min to max of values.

    Args:
        values (List[float]): The values to bucket.
        n_buckets (int, optional): The number of buckets. Defaults to 5.

    Returns:
        List[Tuple[float, float]]: A list of (lower, upper) boundaries for each bucket.
    """
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

def get_calibration_metrics(horizon: str = "30d") -> Dict[str, Any]:
    """
    Compute confidence calibration metrics across buckets, horizons,
    and categorical groupings.

    Bucket, group and error metrics are scored on the given horizon ('7d', '30d'
    or '90d'); the "_30d" key names are kept for response compatibility.

    Returns:
        Dict[str, Any]: A comprehensive set of calibration statistics.
    """
    hit_col, brier_col = _horizon_cols(horizon)
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
        buckets = _build_calibration_buckets(session, horizon)

        # ── Global calibration error metrics ──
        cal_error, ece, mce = _compute_calibration_errors(buckets)

        # ── Hit rate by horizon ──
        hit_by_horizon = _compute_hit_rate_by_horizon(session)

        # ── Group calibrations ──
        by_scan_type = _build_group_calibration(session, AnalysisPrediction.scan_type, hit_col, brier_col)
        by_regime = _build_group_calibration(session, AnalysisPrediction.regime_id, hit_col, brier_col)
        by_sector = _build_sector_calibration(session, hit_col, brier_col)
        by_ml_mode = _build_group_calibration(session, AnalysisPrediction.ml_engine_mode, hit_col, brier_col)
        by_rec = _build_group_calibration(session, AnalysisPrediction.recommendation, hit_col, brier_col)

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


def _build_calibration_buckets(session, horizon: str = "30d") -> List[Dict[str, Any]]:
    """Compute per-bucket calibration stats.

    count, accuracy, average confidence and Brier all come from the same matured
    subset (hit label not null); total_count is every row in the bucket. Buckets
    with fewer than MIN_BUCKET_N matured rows report accuracy, overconfidence and
    the Wilson interval as None and suppressed=True.

    Args:
        session: The SQLAlchemy database session.
        horizon: '7d', '30d' or '90d'.

    Returns:
        List[Dict[str, Any]]: A list of calibration statistics per bucket.
    """
    hit_col, brier_col = _horizon_cols(horizon)
    conf = AnalysisPrediction.confidence_pct
    results = []
    for lo, hi, label in CONFIDENCE_BUCKETS:
        stats = (
            session.query(
                func.count(AnalysisPrediction.id),
                func.count(case((hit_col.isnot(None), 1))),
                func.count(case((hit_col.is_(True), 1))),
                _safe_avg(case((hit_col.isnot(None), brier_col))),
                _safe_avg(case((hit_col.isnot(None), conf))),
            )
            .filter(*bucket_filter(conf, lo, hi))
            .first()
        )
        total_count, count, hits = (stats[0] or 0, stats[1] or 0, stats[2] or 0) if stats else (0, 0, 0)
        avg_brier = _safe_float(stats[3]) if stats else None
        avg_conf = _safe_float(stats[4]) if stats else None

        suppressed = count < MIN_BUCKET_N
        accuracy = overconfidence = ci_low = ci_high = None
        if not suppressed:
            accuracy = round(hits / count, 4)
            ci_low, ci_high = _wilson(hits, count)
            if avg_conf is not None:
                overconfidence = round(avg_conf / 100.0 - accuracy, 4)

        results.append({
            "bucket_label": label,
            "count": count,
            "total_count": total_count,
            "accuracy": accuracy,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "suppressed": suppressed,
            "avg_brier_score_30d": avg_brier,
            "avg_confidence_pct": avg_conf,
            "overconfidence": overconfidence,
        })
    return results


def _compute_calibration_errors(
    buckets: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute weighted calibration error, ECE, and MCE from bucket stats.

    Only buckets with an accuracy (matured and not suppressed) take part, and
    each gap is weighted by its matured count over the sum of those counts, so
    unmatured rows cannot change the result.

    Args:
        buckets (List[Dict[str, Any]]): A list of bucket statistics.

    Returns:
        Tuple[Optional[float], Optional[float], Optional[float]]: A tuple containing
            the weighted calibration error, ECE, and MCE respectively.
    """
    scored = [
        b for b in buckets
        if b.get("accuracy") is not None and b.get("avg_confidence_pct") is not None and b.get("count", 0) > 0
    ]
    n = sum(b["count"] for b in scored)
    if n == 0:
        return None, None, None

    gaps = [(b["count"], abs(b["accuracy"] - b["avg_confidence_pct"] / 100.0)) for b in scored]
    ece = round(sum(c / n * g for c, g in gaps), 4)
    mce = round(max(g for _, g in gaps), 4)
    # The count-weighted mean gap over matured rows is the ECE itself.
    return ece, ece, mce


def _compute_hit_rate_by_horizon(session) -> Dict[str, Dict[str, Any]]:
    """Compute matured count and hit rate for 7d, 30d, 90d horizons.

    Args:
        session: The SQLAlchemy database session.

    Returns:
        Dict[str, Dict[str, Any]]: A mapping of horizon prefixes to hit rate metrics.
    """
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


def _build_group_calibration(session, column, hit_col, brier_col) -> List[Dict[str, Any]]:
    """Generic GROUP BY calibration for a categorical column.

    count is every row in the group; accuracy, Brier and average confidence come
    from the matured rows (hit label not null) only.

    Args:
        session: The SQLAlchemy database session.
        column: The categorical column to group by.
        hit_col / brier_col: the horizon's hit and Brier columns.

    Returns:
        List[Dict[str, Any]]: Calibration statistics grouped by the column.
    """
    rows = (
        session.query(
            column,
            func.count(AnalysisPrediction.id),
            _safe_hit_rate(hit_col),
            _safe_avg(case((hit_col.isnot(None), brier_col))),
            _safe_avg(case((hit_col.isnot(None), AnalysisPrediction.confidence_pct))),
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


def _build_sector_calibration(session, hit_col, brier_col) -> List[Dict[str, Any]]:
    """Sector calibration via JOIN with StockUniverse (same subsets as groups).

    Args:
        session: The SQLAlchemy database session.
        hit_col / brier_col: the horizon's hit and Brier columns.

    Returns:
        List[Dict[str, Any]]: Calibration statistics grouped by sector.
    """
    rows = (
        session.query(
            StockUniverse.sector,
            func.count(AnalysisPrediction.id),
            _safe_hit_rate(hit_col),
            _safe_avg(case((hit_col.isnot(None), brier_col))),
            _safe_avg(case((hit_col.isnot(None), AnalysisPrediction.confidence_pct))),
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

    Returns:
        Dict[str, Any]: Attribution statistics detailing the usefulness of each pillar.
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
    """Group pillar values into equal-width buckets and compute hit rate per bucket.

    Args:
        pillar_vals (List[float]): A list of continuous pillar values.
        hit_vals (List[bool]): A list of boolean hit outcomes.
        n_buckets (int, optional): The number of equal-width buckets. Defaults to 5.

    Returns:
        List[Dict[str, Any]]: Hit rate statistics broken down by bucket.
    """
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

    Returns:
        Dict[str, Any]: Performance metrics grouped by model version.
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


# ---------------------------------------------------------------------------
# 4. get_calibration_health
# ---------------------------------------------------------------------------

def get_ml_signal_reliability(model_version: str, min_matured: int = 30) -> Dict[str, Any]:
    """30d track record of the ML signal itself for one served model_version (ML-13).

    Scores the ml-engine's own direction and P(up) on matured rows, not the fused
    recommendation that get_model_version_analytics measures. Metrics are None until
    min_matured rows exist; sample_size_30d is always returned.
    """
    with get_session() as session:
        rows = (
            session.query(
                AnalysisPrediction.ml_direction,
                AnalysisPrediction.ml_p_up,
                AnalysisPrediction.actual_return_30d,
            )
            .filter(
                AnalysisPrediction.model_version == model_version,
                AnalysisPrediction.ml_direction.in_((1, -1)),
                AnalysisPrediction.actual_return_30d.isnot(None),
            )
            .all()
        )

    n = len(rows)
    result: Dict[str, Any] = {
        "sample_size_30d": n,
        "hit_rate_30d": None,
        "brier_score_30d": None,
        "calibration_error_30d": None,
    }
    if n < min_matured:
        return result

    hits = sum(1 for d, _p, ret in rows if ret * d > 0)  # sign(return) == ml_direction; flat is a miss
    result["hit_rate_30d"] = round(hits / n, 4)
    probs = [(float(p), 1.0 if ret > 0 else 0.0) for _d, p, ret in rows if p is not None]
    if probs:
        result["brier_score_30d"] = round(sum((p - y) ** 2 for p, y in probs) / len(probs), 4)
        result["calibration_error_30d"] = round(
            abs(sum(p for p, _ in probs) / len(probs) - sum(y for _, y in probs) / len(probs)), 4
        )
    return result


def get_calibration_health() -> Dict[str, Any]:
    """
    Returns counts and readiness flags to determine if there is enough data
    for reliable calibration.

    Returns:
        Dict[str, Any]: Health indicators and warnings regarding data sufficiency.
    """
    with get_session() as session:
        total = session.query(func.count(AnalysisPrediction.id)).scalar() or 0
        latest = session.query(func.max(AnalysisPrediction.created_at)).scalar()
        
        hit_by_horizon = _compute_hit_rate_by_horizon(session)
        
        matured_7d = hit_by_horizon.get("7d", {}).get("matured_count", 0)
        matured_30d = hit_by_horizon.get("30d", {}).get("matured_count", 0)
        matured_90d = hit_by_horizon.get("90d", {}).get("matured_count", 0)
        
        warnings = []
        if matured_30d < 100:
            warnings.append(f"Insufficient 30d matured data for reliable calibration ({matured_30d}/100).")
        if matured_7d < 30:
            warnings.append(f"Low 7d matured data ({matured_7d}/30).")

        # Heartbeat written by harvest_worker._run_prediction_outcomes (ML-03).
        from services import disk_cache
        last_run = disk_cache.get("job_heartbeat", "prediction_outcomes")
        last_ok = (last_run or {}).get("last_success_at")
        if last_ok is None:
            warnings.append("Outcome tracking job has not completed a run.")
        elif datetime.now(timezone.utc) - datetime.fromisoformat(last_ok) > timedelta(hours=36):
            warnings.append(f"Outcome tracking last succeeded at {last_ok} (over 36h ago).")

        return {
            "total_predictions": total,
            "matured_7d": matured_7d,
            "matured_30d": matured_30d,
            "matured_90d": matured_90d,
            "latest_prediction_date": latest.isoformat() if latest else None,
            "is_ready_for_calibration": matured_30d >= 100,
            "warnings": warnings,
            "last_outcome_run": last_run,
        }


# ---------------------------------------------------------------------------
# 5. get_fusion_weight_recommendations
# ---------------------------------------------------------------------------

def _corr_lower_bound(r: Optional[float], n: int, z: float = 1.96) -> Optional[float]:
    """Fisher-z lower bound of the 95% CI for correlation r over n rows (None if n <= 3)."""
    if r is None or n <= 3:
        return None
    r = max(-0.999, min(0.999, float(r)))
    return math.tanh(math.atanh(r) - z / math.sqrt(n - 3))


def get_fusion_weight_recommendations(min_sample: int = 100) -> Dict[str, Any]:
    """
    Generate advisory weights for confidence fusion from the pillars' point-biserial
    correlations with matured 30d outcomes (ML-04).

    A pillar earns weight only when the lower 95% bound of its correlation is > 0.
    is_confident needs every pillar to have at least min_sample matured rows and one
    pillar with such a bound. apply_recommendation additionally needs the manual
    FUSION_DYNAMIC_WEIGHTS_ENABLED opt-in; otherwise fusion keeps its static weights.

    Args:
        min_sample (int, optional): Minimum matured (hit_direction_30d known) rows per
            pillar before historical correlations are trusted. Defaults to 100.

    Returns:
        Dict[str, Any]: Recommended weights, warnings, confidence/apply flags,
            matured_sample and weights_version.
    """
    from services.confidence_fusion import STATIC_WEIGHTS_VERSION, dynamic_weights_enabled

    attr = get_pillar_attribution()
    pillars = attr.get("pillars", {})

    # Base weights if not enough data or fallback needed
    base_weights = {
        "llm_confidence": 0.45,
        "quant_confidence": 0.25,
        "venn_abers_confidence": 0.15,
        "signal_agreement": 0.10,
        "ml_confidence": 0.05,
    }

    matured = [int((pillars.get(p) or {}).get("sample_size") or 0) for p in PILLAR_COLUMNS]
    min_n = min(matured)

    raw_weights: Dict[str, float] = {}
    for p_name in PILLAR_COLUMNS:
        p_info = pillars.get(p_name) or {}
        lo = _corr_lower_bound(p_info.get("correlation_with_hit_30d"), int(p_info.get("sample_size") or 0))
        missing_rate = p_info.get("missing_rate") or 0.0
        raw_weights[p_name] = max(lo, 0.0) * (1.0 - missing_rate) if lo is not None else 0.0

    total_raw = sum(raw_weights.values())
    warnings: List[str] = []
    if min_n < min_sample:
        warnings.append(f"Only {min_n} matured 30d outcomes (need {min_sample}). Using base weights.")
    elif total_raw <= 0:
        warnings.append("No pillar correlation significantly > 0. Using base weights.")

    if warnings:
        return {
            "recommended_weights": base_weights,
            "warnings": warnings,
            "apply_recommendation": False,
            "is_confident": False,
            "matured_sample": min_n,
            "weights_version": STATIC_WEIGHTS_VERSION,
        }

    recommended = {k: round(v / total_raw, 4) for k, v in raw_weights.items()}
    digest = hashlib.sha1(json.dumps(recommended, sort_keys=True).encode()).hexdigest()[:8]
    return {
        "recommended_weights": recommended,
        "warnings": [],
        "apply_recommendation": dynamic_weights_enabled(),
        "is_confident": True,
        "matured_sample": min_n,
        "weights_version": f"dyn-{digest}",
    }
