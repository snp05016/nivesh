"""
Walk-forward temporal validation for LightGBM direction prediction.

NO random train/test split. Every fold uses strictly past data for training
and a single future year for validation, preserving temporal causality.

Leakage controls (ML-06):
  * Purge/embargo: training rows stop ``embargo_days`` trading days before the
    validation start, so no training label window (t, t+20] reaches into it.
  * Nested early stopping: the stopping set is the last ``INNER_VAL_FRAC`` of
    the *training* dates (with the same embargo), never the reported fold.
  * Holdout: ``holdout_year`` rows appear in no fold; use
    :func:`generate_holdout_split` once, for reporting only.
"""

from __future__ import annotations

import inspect
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
    # Trading days purged between train end and validation start; must be at
    # least the label horizon (direction_20d looks 20 trading days ahead).
    embargo_days: int = 20
    # Final holdout year: excluded from every fold, never used for selection.
    holdout_year: int | None = None


# Share of the training dates (the latest ones) used for early stopping.
INNER_VAL_FRAC = 0.1


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
    train_base_rate: float = float("nan")
    embargo_days: int = 0
    # df index labels of the validation rows (to join dates, symbols, returns).
    val_index: np.ndarray | None = None


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
    # Out-of-fold predictions, aligned with the split's validation rows.
    y_true: np.ndarray | None = field(default=None, repr=False)
    y_prob: np.ndarray | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Split generation
# ---------------------------------------------------------------------------


def _embargo_cutoff(unique_dates: np.ndarray, start: Any, embargo_days: int) -> Any:
    """Last trading date whose (t, t+embargo_days] label window ends before *start*.

    ``unique_dates`` is the sorted array of trading dates. Returns None when
    there is no such date.
    """
    pos = int(np.searchsorted(unique_dates, np.datetime64(start), side="left"))
    cut = pos - embargo_days - 1
    # ponytail: trading days are the panel's union of dates; a symbol with
    # missing days can have a label reaching a few days further. Raise
    # embargo_days if the panel is ragged.
    return unique_dates[cut] if cut >= 0 else None


def _check_columns(df: pd.DataFrame, config: WalkForwardConfig, feature_cols: list[str]) -> None:
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


def _make_split(
    df: pd.DataFrame,
    train_mask: pd.Series,
    val_mask: pd.Series,
    fold_id: int,
    train_end_year: int,
    val_year: int,
    config: WalkForwardConfig,
    feature_cols: list[str],
) -> WalkForwardSplit | None:
    """Materialise one split; None when either side is below min_train_samples."""
    # Drop rows with NaN targets
    train_df = df.loc[train_mask].dropna(subset=[config.target_col])
    val_df = df.loc[val_mask].dropna(subset=[config.target_col])

    for side, n in (("train", len(train_df)), ("val", len(val_df))):
        if n < config.min_train_samples:
            logger.warning(
                "Fold %d (train<=%.0f, val=%.0f): skipped — only %d %s samples "
                "(need %d)",
                fold_id, train_end_year, val_year, n, side, config.min_train_samples,
            )
            return None

    y_train = train_df[config.target_col].values.astype(np.float32)
    return WalkForwardSplit(
        fold_id=fold_id,
        train_end_year=train_end_year,
        val_year=val_year,
        X_train=train_df[feature_cols].values.astype(np.float32),
        y_train=y_train,
        X_val=val_df[feature_cols].values.astype(np.float32),
        y_val=val_df[config.target_col].values.astype(np.float32),
        train_dates=pd.to_datetime(train_df["date"]).values,
        val_dates=pd.to_datetime(val_df["date"]).values,
        feature_names=list(feature_cols),
        train_base_rate=float(np.mean(y_train)),
        embargo_days=config.embargo_days,
        val_index=val_df.index.to_numpy(),
    )


def generate_splits(
    df: pd.DataFrame,
    config: WalkForwardConfig,
    feature_cols: list[str],
) -> list[WalkForwardSplit]:
    """Build temporal train/val splits — no future data leaks into training.

    For each fold ``(train_end_year, val_year)``:
      - val   = all rows where ``date.dt.year == val_year``
      - train = rows where ``date.dt.year <= train_end_year`` AND the date is at
        least ``embargo_days + 1`` trading days before the first validation
        date (purge/embargo of the label horizon)

    Rows from ``config.holdout_year`` are in no fold. Rows with NaN targets are
    dropped. Folds with fewer than ``config.min_train_samples`` rows in either
    set are skipped.
    """
    _check_columns(df, config, feature_cols)

    dates = pd.to_datetime(df["date"])
    years = dates.dt.year
    not_holdout = pd.Series(True, index=df.index)
    if config.holdout_year is not None:
        not_holdout = years != config.holdout_year
    unique_dates = dates.drop_duplicates().sort_values().to_numpy()

    splits: list[WalkForwardSplit] = []

    for fold_id, (train_end_year, val_year) in enumerate(config.folds):
        if val_year == config.holdout_year:
            logger.warning("Fold %d: val year %d is the holdout year — skipped", fold_id, val_year)
            continue

        val_mask = (years == val_year) & not_holdout
        if not val_mask.any():
            logger.warning("Fold %d: no rows in val year %d — skipped", fold_id, val_year)
            continue
        cutoff = _embargo_cutoff(unique_dates, dates[val_mask].min(), config.embargo_days)
        if cutoff is None:
            logger.warning("Fold %d: no training dates before the embargo — skipped", fold_id)
            continue
        train_mask = (years <= train_end_year) & (dates <= cutoff) & not_holdout

        split = _make_split(
            df, train_mask, val_mask, fold_id, train_end_year, val_year, config, feature_cols,
        )
        if split is None:
            continue
        splits.append(split)
        logger.info(
            "Fold %d: train<=%s (%d rows, embargo %d days) | val=%.0f (%d rows)",
            fold_id, pd.Timestamp(cutoff).date(), len(split.y_train), config.embargo_days,
            val_year, len(split.y_val),
        )

    if not splits:
        logger.warning("No valid walk-forward splits generated")

    return splits


def generate_holdout_split(
    df: pd.DataFrame,
    config: WalkForwardConfig,
    feature_cols: list[str],
) -> WalkForwardSplit | None:
    """Train on every embargoed row before the holdout year; validate on it.

    For the single, report-only evaluation of the final model. Returns None
    when ``config.holdout_year`` is unset or has too few rows.
    """
    if config.holdout_year is None:
        return None
    _check_columns(df, config, feature_cols)

    dates = pd.to_datetime(df["date"])
    years = dates.dt.year
    val_mask = years == config.holdout_year
    if not val_mask.any():
        logger.warning("Holdout year %d has no rows", config.holdout_year)
        return None
    unique_dates = dates.drop_duplicates().sort_values().to_numpy()
    cutoff = _embargo_cutoff(unique_dates, dates[val_mask].min(), config.embargo_days)
    if cutoff is None:
        return None
    train_mask = (years < config.holdout_year) & (dates <= cutoff)
    return _make_split(
        df, train_mask, val_mask, -1, config.holdout_year - 1, config.holdout_year,
        config, feature_cols,
    )


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


def _inner_split(train_dates: np.ndarray, embargo_days: int) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks (inner_train, inner_val) over the training rows.

    inner_val is the latest INNER_VAL_FRAC of the training dates; inner_train
    ends ``embargo_days`` trading days before it.
    """
    unique_dates = np.sort(np.unique(train_dates))
    n_inner = max(1, int(len(unique_dates) * INNER_VAL_FRAC))
    if len(unique_dates) <= n_inner + embargo_days:
        raise ValueError(
            f"Too few training dates ({len(unique_dates)}) for an inner early-stopping "
            f"slice of {n_inner} dates plus a {embargo_days}-day embargo"
        )
    inner_val_start = unique_dates[-n_inner]
    cutoff = _embargo_cutoff(unique_dates, inner_val_start, embargo_days)
    return train_dates <= cutoff, train_dates >= inner_val_start


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
        for models that output probabilities directly). When ``fit`` takes an
        ``eval_set`` it is trained on the inner slice of the training dates and
        stopped on the embargoed latest ``INNER_VAL_FRAC`` of them.
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
        if "eval_set" in inspect.signature(model.fit).parameters:
            # Early stopping on an inner, embargoed slice of the training
            # dates — never on split.X_val, whose metrics are reported.
            inner_train, inner_val = _inner_split(split.train_dates, split.embargo_days)
            model.fit(
                split.X_train[inner_train],
                split.y_train[inner_train],
                eval_set=[(split.X_train[inner_val], split.y_train[inner_val])],
            )
            if getattr(model, "best_iteration_", None) is not None:
                best_iteration = int(model.best_iteration_)
        else:
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
            y_true=y_true,
            y_prob=y_prob,
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
