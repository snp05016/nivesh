"""
Walk-forward evaluation reporting — aggregate fold results, calibration analysis,
and formatted training reports.

No torch or pandas dependency. Uses numpy for numerical aggregation.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np


# ── Calibration Buckets ───────────────────────────────────────────────────────

CALIBRATION_BUCKETS = [
    (0.0, 0.3, "low"),
    (0.3, 0.5, "medium-low"),
    (0.5, 0.7, "medium-high"),
    (0.7, 1.0, "high"),
]


# ── 1. Aggregate Fold Results ─────────────────────────────────────────────────


def aggregate_fold_results(fold_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate metrics across all walk-forward folds.

    Parameters
    ----------
    fold_results : list[dict]
        Each dict is a single fold's output containing keys such as
        hit_rate, precision, recall, roc_auc, brier_score,
        avg_return_when_bullish, avg_return_when_bearish,
        calibration_by_bucket, feature_importance, fold_id, val_year,
        train_samples, val_samples.

    Returns
    -------
    dict with aggregate statistics, per-fold summary, merged calibration,
    and ranked feature importance.
    """
    if not fold_results:
        return {
            "mean_hit_rate": None,
            "std_hit_rate": None,
            "mean_precision": None,
            "mean_recall": None,
            "mean_roc_auc": None,
            "mean_brier_score": None,
            "mean_return_when_bullish": None,
            "mean_return_when_bearish": None,
            "overall_calibration": {},
            "top_features": [],
            "per_fold_summary": [],
            "total_train_samples": 0,
            "total_val_samples": 0,
        }

    # --- scalar metrics ---
    def _safe_mean(key: str) -> float | None:
        vals = [f[key] for f in fold_results if f.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    def _safe_std(key: str) -> float | None:
        vals = [f[key] for f in fold_results if f.get(key) is not None]
        return float(np.std(vals, ddof=1)) if len(vals) >= 2 else None

    mean_hit_rate = _safe_mean("hit_rate")
    std_hit_rate = _safe_std("hit_rate")
    mean_precision = _safe_mean("precision")
    mean_recall = _safe_mean("recall")
    mean_roc_auc = _safe_mean("roc_auc")
    mean_brier_score = _safe_mean("brier_score")
    mean_return_bullish = _safe_mean("avg_return_when_bullish")
    mean_return_bearish = _safe_mean("avg_return_when_bearish")

    # --- sample counts ---
    total_train = sum(f.get("train_samples", 0) for f in fold_results)
    total_val = sum(f.get("val_samples", 0) for f in fold_results)

    # --- per-fold summary ---
    per_fold = []
    for f in fold_results:
        per_fold.append({
            "fold_id": f.get("fold_id"),
            "val_year": f.get("val_year"),
            "hit_rate": f.get("hit_rate"),
            "roc_auc": f.get("roc_auc"),
            "brier_score": f.get("brier_score"),
        })

    # --- merged calibration (weighted by sample count) ---
    overall_calibration = _merge_calibration_buckets(fold_results)

    # --- aggregated feature importance ---
    top_features = _aggregate_feature_importance(fold_results)

    return {
        "mean_hit_rate": mean_hit_rate,
        "std_hit_rate": std_hit_rate,
        "mean_precision": mean_precision,
        "mean_recall": mean_recall,
        "mean_roc_auc": mean_roc_auc,
        "mean_brier_score": mean_brier_score,
        "mean_return_when_bullish": mean_return_bullish,
        "mean_return_when_bearish": mean_return_bearish,
        "overall_calibration": overall_calibration,
        "top_features": top_features,
        "per_fold_summary": per_fold,
        "total_train_samples": total_train,
        "total_val_samples": total_val,
    }


def _merge_calibration_buckets(fold_results: list[dict]) -> dict[str, Any]:
    """Merge calibration_by_bucket across folds, weighted by per-bucket count."""
    merged: dict[str, dict[str, float]] = {}

    for f in fold_results:
        cal = f.get("calibration_by_bucket")
        if not cal:
            continue

        # cal is expected as dict[bucket_label, {count, accuracy, avg_probability}]
        # or list of dicts with a "label" key — handle both.
        items = cal.items() if isinstance(cal, dict) else []
        if isinstance(cal, list):
            items = [(b.get("label", ""), b) for b in cal]

        for label, bucket_data in items:
            if not isinstance(bucket_data, dict):
                continue
            count = bucket_data.get("count", 0)
            if count <= 0:
                continue

            if label not in merged:
                merged[label] = {
                    "total_count": 0,
                    "weighted_accuracy": 0.0,
                    "weighted_avg_prob": 0.0,
                }

            merged[label]["total_count"] += count
            merged[label]["weighted_accuracy"] += (
                bucket_data.get("accuracy", 0.0) * count
            )
            merged[label]["weighted_avg_prob"] += (
                bucket_data.get("avg_probability", 0.0) * count
            )

    result: dict[str, Any] = {}
    for label, m in merged.items():
        tc = m["total_count"]
        acc = m["weighted_accuracy"] / tc if tc > 0 else 0.0
        avg_p = m["weighted_avg_prob"] / tc if tc > 0 else 0.0
        result[label] = {
            "count": tc,
            "accuracy": round(acc, 4),
            "avg_probability": round(avg_p, 4),
            "overconfidence": round(avg_p - acc, 4),
        }

    return result


def _aggregate_feature_importance(
    fold_results: list[dict],
) -> list[dict[str, Any]]:
    """Average feature importance across folds and return ranked list."""
    importance_sums: dict[str, float] = defaultdict(float)
    importance_counts: dict[str, int] = defaultdict(int)

    for f in fold_results:
        fi = f.get("feature_importance")
        if not fi:
            continue

        # fi can be dict[name, importance] or list[{feature, importance}]
        if isinstance(fi, dict):
            items = fi.items()
        elif isinstance(fi, list):
            items = [(e.get("feature", ""), e.get("importance", 0)) for e in fi]
        else:
            continue

        for name, imp in items:
            if name and imp is not None:
                importance_sums[name] += float(imp)
                importance_counts[name] += 1

    if not importance_sums:
        return []

    ranked = []
    for name in importance_sums:
        mean_imp = importance_sums[name] / importance_counts[name]
        ranked.append({
            "feature": name,
            "mean_importance": round(mean_imp, 6),
            "fold_count": importance_counts[name],
        })

    ranked.sort(key=lambda x: x["mean_importance"], reverse=True)

    for rank, entry in enumerate(ranked, start=1):
        entry["rank"] = rank

    return ranked


# ── 2. Calibration Report ────────────────────────────────────────────────────


def compute_calibration_report(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, Any]:
    """Compute calibration metrics across predefined probability buckets.

    Parameters
    ----------
    y_true : np.ndarray
        Binary ground truth labels (0 or 1).
    y_prob : np.ndarray
        Predicted probabilities in [0, 1].

    Returns
    -------
    dict with "buckets" list, "ece" (Expected Calibration Error),
    and "mce" (Maximum Calibration Error).
    """
    if y_true is None or y_prob is None:
        return {"buckets": [], "ece": 0.0, "mce": 0.0}

    y_true = np.asarray(y_true, dtype=float).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()

    if len(y_true) == 0 or len(y_prob) == 0:
        return {"buckets": [], "ece": 0.0, "mce": 0.0}

    n_total = len(y_true)
    buckets: list[dict[str, Any]] = []
    ece = 0.0
    mce = 0.0

    for low, high, label in CALIBRATION_BUCKETS:
        if label == "high":
            # Include upper bound for the last bucket
            mask = (y_prob >= low) & (y_prob <= high)
        else:
            mask = (y_prob >= low) & (y_prob < high)

        count = int(mask.sum())
        if count == 0:
            buckets.append({
                "label": label,
                "range": f"[{low:.1f}, {high:.1f})",
                "count": 0,
                "accuracy": 0.0,
                "avg_probability": 0.0,
                "overconfidence": 0.0,
            })
            continue

        accuracy = float(y_true[mask].mean())
        avg_prob = float(y_prob[mask].mean())
        overconf = avg_prob - accuracy
        gap = abs(overconf)

        ece += (count / n_total) * gap
        mce = max(mce, gap)

        buckets.append({
            "label": label,
            "range": f"[{low:.1f}, {high:.1f})" if label != "high" else f"[{low:.1f}, {high:.1f}]",
            "count": count,
            "accuracy": round(accuracy, 4),
            "avg_probability": round(avg_prob, 4),
            "overconfidence": round(overconf, 4),
        })

    return {
        "buckets": buckets,
        "ece": round(ece, 4),
        "mce": round(mce, 4),
    }


# ── 3. Formatted Training Report ─────────────────────────────────────────────


def generate_training_report(
    aggregate_results: dict[str, Any],
    calibration: dict[str, Any],
    config: dict[str, Any],
    model_version: str,
) -> str:
    """Generate a markdown-formatted training report.

    Parameters
    ----------
    aggregate_results : dict
        Output of ``aggregate_fold_results()``.
    calibration : dict
        Output of ``compute_calibration_report()``.
    config : dict
        Training configuration (hyperparams, feature count, etc.).
    model_version : str
        Semantic version or tag for the model.

    Returns
    -------
    str — full markdown report.
    """
    lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append(f"# Training Report — {model_version}")
    lines.append(f"Generated: {ts}")
    lines.append("")

    # --- Config ---
    lines.append("## Training Configuration")
    lines.append("")
    if config:
        for k, v in config.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("_No configuration provided._")
    lines.append("")

    # --- Sample Counts ---
    total_train = aggregate_results.get("total_train_samples", 0)
    total_val = aggregate_results.get("total_val_samples", 0)
    lines.append("## Dataset Summary")
    lines.append("")
    lines.append(f"- Total training samples: {total_train:,}")
    lines.append(f"- Total validation samples: {total_val:,}")
    lines.append("")

    # --- Per-Fold Table ---
    per_fold = aggregate_results.get("per_fold_summary", [])
    if per_fold:
        lines.append("## Per-Fold Results")
        lines.append("")
        lines.append("| Fold | Val Year | Hit Rate | ROC AUC | Brier Score |")
        lines.append("|------|----------|----------|---------|-------------|")
        for pf in per_fold:
            fold_id = pf.get("fold_id", "?")
            val_year = pf.get("val_year", "?")
            hr = _fmt(pf.get("hit_rate"), pct=True)
            auc = _fmt(pf.get("roc_auc"))
            bs = _fmt(pf.get("brier_score"))
            lines.append(f"| {fold_id} | {val_year} | {hr} | {auc} | {bs} |")
        lines.append("")

    # --- Aggregate Metrics ---
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append(f"- **Mean Hit Rate**: {_fmt(aggregate_results.get('mean_hit_rate'), pct=True)} "
                 f"(std: {_fmt(aggregate_results.get('std_hit_rate'), pct=True)})")
    lines.append(f"- **Mean Precision**: {_fmt(aggregate_results.get('mean_precision'), pct=True)}")
    lines.append(f"- **Mean Recall**: {_fmt(aggregate_results.get('mean_recall'), pct=True)}")
    lines.append(f"- **Mean ROC AUC**: {_fmt(aggregate_results.get('mean_roc_auc'))}")
    lines.append(f"- **Mean Brier Score**: {_fmt(aggregate_results.get('mean_brier_score'))}")
    lines.append(f"- **Mean Return (Bullish)**: {_fmt(aggregate_results.get('mean_return_when_bullish'), pct=True)}")
    lines.append(f"- **Mean Return (Bearish)**: {_fmt(aggregate_results.get('mean_return_when_bearish'), pct=True)}")
    lines.append("")

    # --- Calibration ---
    lines.append("## Calibration Analysis")
    lines.append("")
    buckets = calibration.get("buckets", [])
    if buckets:
        lines.append("| Bucket | Count | Accuracy | Avg Prob | Overconfidence |")
        lines.append("|--------|-------|----------|----------|----------------|")
        for b in buckets:
            label = b.get("label", "?")
            count = b.get("count", 0)
            acc = _fmt(b.get("accuracy"), pct=True)
            avg_p = _fmt(b.get("avg_probability"), pct=True)
            oc = _fmt_signed(b.get("overconfidence"))
            lines.append(f"| {label} | {count:,} | {acc} | {avg_p} | {oc} |")
        lines.append("")

    ece = calibration.get("ece", 0.0)
    mce = calibration.get("mce", 0.0)
    lines.append(f"- **ECE** (Expected Calibration Error): {_fmt(ece)}")
    lines.append(f"- **MCE** (Maximum Calibration Error): {_fmt(mce)}")
    lines.append("")

    # --- Merged Calibration (from folds) ---
    overall_cal = aggregate_results.get("overall_calibration", {})
    if overall_cal:
        lines.append("### Merged Calibration Across Folds")
        lines.append("")
        lines.append("| Bucket | Count | Accuracy | Avg Prob | Overconfidence |")
        lines.append("|--------|-------|----------|----------|----------------|")
        for label, data in overall_cal.items():
            count = data.get("count", 0)
            acc = _fmt(data.get("accuracy"), pct=True)
            avg_p = _fmt(data.get("avg_probability"), pct=True)
            oc = _fmt_signed(data.get("overconfidence"))
            lines.append(f"| {label} | {count:,} | {acc} | {avg_p} | {oc} |")
        lines.append("")

    # --- Top Features ---
    top_features = aggregate_results.get("top_features", [])
    if top_features:
        lines.append("## Top 20 Features")
        lines.append("")
        lines.append("| Rank | Feature | Mean Importance | Folds |")
        lines.append("|------|---------|-----------------|-------|")
        for feat in top_features[:20]:
            rank = feat.get("rank", "?")
            name = feat.get("feature", "?")
            imp = feat.get("mean_importance", 0.0)
            folds = feat.get("fold_count", 0)
            lines.append(f"| {rank} | {name} | {imp:.6f} | {folds} |")
        lines.append("")

    # --- Recommendations ---
    lines.append("## Recommendations")
    lines.append("")
    lines.extend(_generate_recommendations(aggregate_results, calibration))
    lines.append("")

    return "\n".join(lines)


def _fmt(value: float | None, pct: bool = False) -> str:
    """Format a numeric value for display."""
    if value is None:
        return "N/A"
    if pct:
        return f"{value * 100:.2f}%"
    return f"{value:.4f}"


def _fmt_signed(value: float | None) -> str:
    """Format a signed value (overconfidence)."""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}pp"


def _generate_recommendations(
    agg: dict[str, Any],
    cal: dict[str, Any],
) -> list[str]:
    """Produce actionable recommendations based on aggregate metrics."""
    recs: list[str] = []

    mean_hr = agg.get("mean_hit_rate")
    std_hr = agg.get("std_hit_rate")
    mean_auc = agg.get("mean_roc_auc")
    mean_brier = agg.get("mean_brier_score")
    ece = cal.get("ece", 0.0)

    if mean_hr is not None and mean_hr < 0.52:
        recs.append("- Hit rate below 52% — model may not outperform naive baseline. "
                     "Consider feature engineering or longer training windows.")

    if std_hr is not None and std_hr > 0.05:
        recs.append("- High fold variance (std > 5pp) — model stability is poor. "
                     "Consider regularization or more training data per fold.")

    if mean_auc is not None and mean_auc < 0.55:
        recs.append("- ROC AUC below 0.55 — discrimination is weak. "
                     "Review feature selection and target definition.")

    if mean_auc is not None and mean_auc >= 0.65:
        recs.append("- ROC AUC above 0.65 — check for look-ahead bias or data leakage.")

    if mean_brier is not None and mean_brier > 0.25:
        recs.append("- Brier score above 0.25 — probability estimates are poorly calibrated. "
                     "Consider Platt scaling or isotonic regression.")

    if ece is not None and ece > 0.05:
        recs.append(f"- ECE = {ece:.4f} (> 0.05) — apply post-hoc calibration "
                     "(temperature scaling or histogram binning).")

    if ece is not None and ece <= 0.02:
        recs.append(f"- ECE = {ece:.4f} — calibration is excellent.")

    # Check for overconfident high bucket
    for b in cal.get("buckets", []):
        if b.get("label") == "high" and b.get("count", 0) > 0:
            oc = b.get("overconfidence", 0.0)
            if oc > 0.1:
                recs.append(f"- High-confidence bucket is overconfident by {oc * 100:.1f}pp — "
                            "model is too aggressive at upper probability range.")

    mean_ret_bull = agg.get("mean_return_when_bullish")
    mean_ret_bear = agg.get("mean_return_when_bearish")
    if (mean_ret_bull is not None and mean_ret_bear is not None
            and mean_ret_bull < mean_ret_bear):
        recs.append("- Bullish predictions yield lower returns than bearish — "
                     "signal may be inverted. Verify target label encoding.")

    if not recs:
        recs.append("- All metrics within acceptable ranges. No immediate action required.")

    return recs


# ── 4. Pretty-Print Fold Summary ─────────────────────────────────────────────


def print_fold_summary(fold_result: dict[str, Any] | None) -> None:
    """Pretty-print a single fold's results to stdout.

    Parameters
    ----------
    fold_result : dict or None
        A single fold result dict. If None or empty, prints a warning.
    """
    if not fold_result:
        print("[evaluation] No fold result to display.")
        return

    fold_id = fold_result.get("fold_id", "?")
    val_year = fold_result.get("val_year", "?")
    train_n = fold_result.get("train_samples", "?")
    val_n = fold_result.get("val_samples", "?")

    print(f"\n{'=' * 60}")
    print(f"  Fold {fold_id}  |  Val Year: {val_year}")
    print(f"  Train: {train_n}  |  Val: {val_n}")
    print(f"{'=' * 60}")

    hr = fold_result.get("hit_rate")
    prec = fold_result.get("precision")
    rec = fold_result.get("recall")
    auc = fold_result.get("roc_auc")
    brier = fold_result.get("brier_score")

    print(f"  Hit Rate:     {_fmt(hr, pct=True)}")
    print(f"  Precision:    {_fmt(prec, pct=True)}")
    print(f"  Recall:       {_fmt(rec, pct=True)}")
    print(f"  ROC AUC:      {_fmt(auc)}")
    print(f"  Brier Score:  {_fmt(brier)}")

    ret_bull = fold_result.get("avg_return_when_bullish")
    ret_bear = fold_result.get("avg_return_when_bearish")
    if ret_bull is not None or ret_bear is not None:
        print(f"  Avg Return (Bullish):  {_fmt(ret_bull, pct=True)}")
        print(f"  Avg Return (Bearish):  {_fmt(ret_bear, pct=True)}")

    # Top 5 features for this fold
    fi = fold_result.get("feature_importance")
    if fi:
        if isinstance(fi, dict):
            sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:5]
        elif isinstance(fi, list):
            sorted_fi = sorted(fi, key=lambda x: x.get("importance", 0), reverse=True)[:5]
            sorted_fi = [(e.get("feature", "?"), e.get("importance", 0)) for e in sorted_fi]
        else:
            sorted_fi = []

        if sorted_fi:
            print(f"\n  Top 5 Features:")
            for i, (name, imp) in enumerate(sorted_fi, 1):
                print(f"    {i}. {name}: {imp:.6f}")

    print(f"{'─' * 60}\n")
