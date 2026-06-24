"""
Walk-forward temporal validation for LightGBM direction prediction.

NO random train/test split. Every fold uses strictly past data for training
and a single future year for validation, preserving temporal causality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metrics — prefer sklearn, fall back to simple implementations
# ---------------------------------------------------------------------------

try:
    from sklearn.metrics import (
        brier_score_loss,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

    def precision_score(y_true: np.ndarray, y_pred: np.ndarray, **_: Any) -> float:
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0

    def recall_score(y_true: np.ndarray, y_pred: np.ndarray, **_: Any) -> float:
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0

    def roc_auc_score(y_true: np.ndarray, y_score: np.ndarray, **_: Any) -> float:
        """Mann-Whitney U statistic formulation of AUC."""
        pos = y_score[y_true == 1]
        neg = y_score[y_true == 0]
        if len(pos) == 0 or len(neg) == 0:
            return 0.5
        u_stat = sum(
            int(p > n) + 0.5 * int(p == n) for p in pos for n in neg
        )
        return u_stat / (len(pos) * len(neg))

    def brier_score_loss(y_true: np.ndarray, y_prob: np.ndarray, **_: Any) -> float:
        return float(np.mean((y_prob - y_true) ** 2))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_FOLDS: list[tuple[int, int]] = [
    (2021, 2022),
    (2022, 2023),
    (2023, 2024),
    (2024, 2025),
]

from training.calibration import CALIBRATION_BUCKETS


@dataclass
class WalkForwardConfig:
    """Controls the temporal walk-forward split strategy."""

    folds: list[tuple[int, int]] = field(default_factory=lambda: list(DEFAULT_FOLDS))
    target_col: str = "direction_20d"
    min_train_samples: int = 500


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardSplit:
    """One temporal fold ready for model training."""

    fold_id: int
    train_end_year: int
    val_year: int
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    train_dates: np.ndarray
    val_dates: np.ndarray
    feature_names: list[str]


@dataclass
class FoldResult:
    """Evaluation results for a single walk-forward fold."""

    fold_id: int
    train_end_year: int
    val_year: int
    hit_rate: float
    precision: float
    recall: float
    roc_auc: float | None
    brier_score: float
    avg_return_when_bullish: float
    avg_return_when_bearish: float
    calibration_by_bucket: list[dict[str, Any]]
    feature_importance: list[tuple[str, float]]
    n_train: int
    n_val: int
    best_iteration: int | None


# ---------------------------------------------------------------------------
# Split generation
# ---------------------------------------------------------------------------


def generate_splits(
    df: pd.DataFrame,
    config: WalkForwardConfig,
    feature_cols: list[str],
) -> list[WalkForwardSplit]:
    """Build temporal train/val splits — no future data leaks into training.

    For each fold ``(train_end_year, val_year)``:
      - train = all rows where ``date.dt.year <= train_end_year``
      - val   = all rows where ``date.dt.year == val_year``

    Rows with NaN targets are dropped. Folds with fewer than
    ``config.min_train_samples`` rows in either set are skipped.
    """
    if "date" not in df.columns:
        raise ValueError("DataFrame must contain a 'date' column")
    if config.target_col not in df.columns:
        raise ValueError(f"Target column '{config.target_col}' not found in DataFrame")

    missing_features = [c for c in feature_cols if c not in df.columns]
    if missing_features:
        raise ValueError(
            f"Missing feature columns: {missing_features[:10]}"
            + (" ..." if len(missing_features) > 10 else "")
        )

    dates = pd.to_datetime(df["date"])
    years = dates.dt.year

    splits: list[WalkForwardSplit] = []

    for fold_id, (train_end_year, val_year) in enumerate(config.folds):
        train_mask = years <= train_end_year
        val_mask = years == val_year

        train_df = df.loc[train_mask].copy()
        val_df = df.loc[val_mask].copy()

        # Drop rows with NaN targets
        train_df = train_df.dropna(subset=[config.target_col])
        val_df = val_df.dropna(subset=[config.target_col])

        n_train = len(train_df)
        n_val = len(val_df)

        if n_train < config.min_train_samples:
            logger.warning(
                "Fold %d (train<=%.0f, val=%.0f): skipped — only %d train samples "
                "(need %d)",
                fold_id, train_end_year, val_year, n_train, config.min_train_samples,
            )
            continue

        if n_val < config.min_train_samples:
            logger.warning(
                "Fold %d (train<=%.0f, val=%.0f): skipped — only %d val samples "
                "(need %d)",
                fold_id, train_end_year, val_year, n_val, config.min_train_samples,
            )
            continue

        splits.append(
            WalkForwardSplit(
                fold_id=fold_id,
                train_end_year=train_end_year,
                val_year=val_year,
                X_train=train_df[feature_cols].values.astype(np.float32),
                y_train=train_df[config.target_col].values.astype(np.float32),
                X_val=val_df[feature_cols].values.astype(np.float32),
                y_val=val_df[config.target_col].values.astype(np.float32),
                train_dates=pd.to_datetime(train_df["date"]).values,
                val_dates=pd.to_datetime(val_df["date"]).values,
                feature_names=list(feature_cols),
            )
        )
        logger.info(
            "Fold %d: train<=%.0f (%d rows) | val=%.0f (%d rows)",
            fold_id, train_end_year, n_train, val_year, n_val,
        )

    if not splits:
        logger.warning("No valid walk-forward splits generated")

    return splits


# ---------------------------------------------------------------------------
# Calibration helper
# ---------------------------------------------------------------------------


def _compute_calibration(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    buckets: list[tuple[float, float, str]] = CALIBRATION_BUCKETS,
) -> list[dict[str, Any]]:
    """Compute actual hit rate per predicted-probability bucket."""
    results: list[dict[str, Any]] = []
    for lo, hi, label in buckets:
        if hi < 1.0:
            mask = (y_prob >= lo) & (y_prob < hi)
        else:
            # Include 1.0 in the last bucket
            mask = (y_prob >= lo) & (y_prob <= hi)
        count = int(np.sum(mask))
        if count > 0:
            actual_rate = float(np.mean(y_true[mask]))
            avg_predicted = float(np.mean(y_prob[mask]))
        else:
            actual_rate = 0.0
            avg_predicted = 0.0
        results.append({
            "bucket": f"{lo:.1f}-{hi:.1f}",
            "count": count,
            "actual_hit_rate": round(actual_rate, 4),
            "avg_predicted_prob": round(avg_predicted, 4),
        })
    return results


# ---------------------------------------------------------------------------
# Walk-forward execution
# ---------------------------------------------------------------------------


def run_walk_forward(
    model_factory: Callable[[], Any],
    splits: list[WalkForwardSplit],
    return_col: str = "forward_return_20d",
    val_returns: list[np.ndarray] | None = None,
) -> list[FoldResult]:
    """Train and evaluate one model per temporal fold.

    Parameters
    ----------
    model_factory:
        Callable that returns a fresh, untrained model with a scikit-learn-like
        interface: ``fit(X, y, ...)`` and ``predict_proba(X)`` (or ``predict(X)``
        for models that output probabilities directly).
    splits:
        Output of :func:`generate_splits`.
    return_col:
        Name of the forward-return column used to compute
        ``avg_return_when_bullish`` / ``avg_return_when_bearish``. The actual
        return values must be passed via *val_returns* since the splits only
        carry feature arrays and targets.
    val_returns:
        One array of forward returns per split, aligned with ``X_val`` rows.
        If ``None``, return-based metrics are set to 0.0.
    """
    if val_returns is not None and len(val_returns) != len(splits):
        raise ValueError(
            f"val_returns length ({len(val_returns)}) != splits length ({len(splits)})"
        )

    results: list[FoldResult] = []

    for idx, split in enumerate(splits):
        logger.info(
            "Fold %d: training on %d samples, validating on %d (val year %d) ...",
            split.fold_id, len(split.y_train), len(split.y_val), split.val_year,
        )

        model = model_factory()

        # ── Train ─────────────────────────────────────────────────────────
        best_iteration: int | None = None
        try:
            # LightGBM-style fit with eval_set for early stopping
            model.fit(
                split.X_train,
                split.y_train,
                eval_set=[(split.X_val, split.y_val)],
            )
            if hasattr(model, "best_iteration_"):
                best_iteration = int(model.best_iteration_)
        except TypeError:
            # Fallback: model.fit does not accept eval_set
            model.fit(split.X_train, split.y_train)

        # ── Predict probabilities ─────────────────────────────────────────
        if hasattr(model, "predict_proba"):
            raw_proba = model.predict_proba(split.X_val)
            # predict_proba may return (n, 2) — take class-1 column
            if raw_proba.ndim == 2:
                y_prob = raw_proba[:, 1]
            else:
                y_prob = raw_proba
        else:
            # Some models (e.g. raw LightGBM Booster) output scores directly
            y_prob = np.asarray(model.predict(split.X_val), dtype=np.float64)

        y_prob = np.clip(y_prob, 0.0, 1.0)
        y_pred = (y_prob >= 0.5).astype(int)
        y_true = split.y_val.astype(int)

        # ── Metrics ───────────────────────────────────────────────────────
        hit_rate = float(np.mean(y_pred == y_true))

        prec = float(precision_score(y_true, y_pred, zero_division=0))
        rec = float(recall_score(y_true, y_pred, zero_division=0))

        # ROC AUC requires both classes present
        try:
            if len(np.unique(y_true)) > 1:
                auc = float(roc_auc_score(y_true, y_prob))
            else:
                auc = None
        except Exception:
            auc = None

        brier = float(brier_score_loss(y_true, y_prob))

        # ── Return-based metrics ──────────────────────────────────────────
        returns = val_returns[idx] if val_returns is not None else None

        if returns is not None and len(returns) == len(y_pred):
            bullish_mask = y_pred == 1
            bearish_mask = y_pred == 0
            avg_ret_bull = float(np.mean(returns[bullish_mask])) if np.any(bullish_mask) else 0.0
            avg_ret_bear = float(np.mean(returns[bearish_mask])) if np.any(bearish_mask) else 0.0
        else:
            avg_ret_bull = 0.0
            avg_ret_bear = 0.0

        # ── Calibration ──────────────────────────────────────────────────
        calibration = _compute_calibration(y_true, y_prob)

        # ── Feature importance ────────────────────────────────────────────
        importance_pairs: list[tuple[str, float]] = []
        if hasattr(model, "feature_importances_"):
            raw_imp = model.feature_importances_
            for fname, imp in zip(split.feature_names, raw_imp):
                importance_pairs.append((fname, float(imp)))
            # Sort descending by importance
            importance_pairs.sort(key=lambda x: x[1], reverse=True)

        fold_result = FoldResult(
            fold_id=split.fold_id,
            train_end_year=split.train_end_year,
            val_year=split.val_year,
            hit_rate=round(hit_rate, 4),
            precision=round(prec, 4),
            recall=round(rec, 4),
            roc_auc=round(auc, 4) if auc is not None else None,
            brier_score=round(brier, 4),
            avg_return_when_bullish=round(avg_ret_bull, 6),
            avg_return_when_bearish=round(avg_ret_bear, 6),
            calibration_by_bucket=calibration,
            feature_importance=importance_pairs,
            n_train=len(split.y_train),
            n_val=len(split.y_val),
            best_iteration=best_iteration,
        )
        results.append(fold_result)

        logger.info(
            "Fold %d result: hit_rate=%.2f%% | AUC=%s | brier=%.4f | "
            "precision=%.2f%% | recall=%.2f%%",
            split.fold_id,
            hit_rate * 100,
            f"{auc:.4f}" if auc is not None else "N/A",
            brier,
            prec * 100,
            rec * 100,
        )

    return results


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------


def summarize_results(results: list[FoldResult]) -> dict[str, Any]:
    """Aggregate fold results into a single summary dict."""
    if not results:
        return {"n_folds": 0, "error": "no fold results"}

    hit_rates = [r.hit_rate for r in results]
    aucs = [r.roc_auc for r in results if r.roc_auc is not None]
    briers = [r.brier_score for r in results]

    return {
        "n_folds": len(results),
        "folds": [
            f"train<={r.train_end_year} | val={r.val_year}" for r in results
        ],
        "mean_hit_rate": round(float(np.mean(hit_rates)), 4),
        "std_hit_rate": round(float(np.std(hit_rates)), 4),
        "mean_roc_auc": round(float(np.mean(aucs)), 4) if aucs else None,
        "mean_brier_score": round(float(np.mean(briers)), 4),
        "mean_precision": round(float(np.mean([r.precision for r in results])), 4),
        "mean_recall": round(float(np.mean([r.recall for r in results])), 4),
        "total_val_samples": sum(r.n_val for r in results),
        "per_fold": [
            {
                "fold_id": r.fold_id,
                "val_year": r.val_year,
                "hit_rate": r.hit_rate,
                "roc_auc": r.roc_auc,
                "brier_score": r.brier_score,
                "n_val": r.n_val,
            }
            for r in results
        ],
    }
