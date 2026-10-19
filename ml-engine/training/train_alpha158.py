"""
LightGBM Alpha158-only training script with walk-forward temporal validation and calibration selection.

Runnable as:
    python -m training.train_alpha158 [--data-path PATH] [--target direction_20d] [--deploy]

Flow:
    1. Load OHLCV data (CSV or Parquet)
    2. Build feature matrix but isolate ONLY Alpha158 features
    3. Walk-forward temporal validation: embargo of the label horizon before
       each validation year, early stopping on an inner slice of the training
       dates, and a final holdout year that no fold sees
    4. Cross-fitted calibration: fold k is calibrated by Isotonic/Platt fitted
       on folds < k; method chosen on the middle folds, reported on the last
    5. Train final model on all non-holdout data; score it once on the holdout
    6. Save versioned artifact (with out-of-fold predictions) to registry
    7. Optionally deploy to production path
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Ensure ml-engine root is on sys.path so that imports like
# `from models.lgb_model import ...` resolve when running as `python -m training.train_lightgbm_baseline`
_ML_ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(_ML_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ML_ENGINE_ROOT))

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LightGBM availability check
# ---------------------------------------------------------------------------

try:
    import lightgbm as lgb  # noqa: F401

    _HAS_LGB = True
except ImportError:
    _HAS_LGB = False

# ---------------------------------------------------------------------------
# Internal imports (deferred to allow helpful error messages)
# ---------------------------------------------------------------------------

_ML_ENGINE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DATA_PATH = _ML_ENGINE_DIR / "data" / "ohlcv.parquet"

EXPECTED_SCHEMA = (
    "Expected OHLCV schema:\n"
    "  symbol  | date       | open   | high   | low    | close  | volume    | [sector]\n"
    "  RELIANCE| 2021-01-04 | 1987.0 | 2010.5 | 1980.0 | 2005.3 | 12345678  | Energy\n"
    "\n"
    "Accepted formats: .csv, .parquet\n"
    "Provide via: --data-path /path/to/ohlcv.parquet"
)

# Classification-specific LightGBM overrides (merged on top of LIGHTGBM_PARAMS)
_CLASSIFICATION_OVERRIDES: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "num_boost_round": 2000,
    "early_stopping_rounds": 100,
}


# ---------------------------------------------------------------------------
# Adapter: make LGBEnsembleModel compatible with run_walk_forward interface
# ---------------------------------------------------------------------------

class _WalkForwardModelAdapter:
    """Wraps LGBEnsembleModel to match the interface run_walk_forward expects.

    run_walk_forward calls (eval_set is the inner early-stopping slice of
    the training dates, never the reported fold):
        model.fit(X_inner_train, y_inner_train, eval_set=[(X_inner_val, y_inner_val)])
        model.predict_proba(X)  or  model.predict(X)
        model.feature_importances_
        model.best_iteration_

    LGBEnsembleModel exposes:
        model.fit(X_train, y_train, X_val, y_val)
        model.predict(X)
        model.feature_importance  (property)
        model.best_iteration      (property)
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        eval_set: list[tuple[np.ndarray, np.ndarray]] | None = None,
        **kwargs: Any,
    ) -> None:
        X_val, y_val = None, None
        if eval_set:
            X_val, y_val = eval_set[0]
        self._inner.fit(X_train, y_train, X_val, y_val)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """For binary objective, LightGBM Booster.predict returns probabilities."""
        return self._inner.predict(X)

    @property
    def feature_importances_(self) -> np.ndarray | None:
        return self._inner.feature_importance

    @property
    def best_iteration_(self) -> int | None:
        return self._inner.best_iteration


# ---------------------------------------------------------------------------
# FoldResult -> dict conversion for metrics.aggregate_fold_results
# ---------------------------------------------------------------------------

def fold_result_to_dict(res: Any) -> dict[str, Any]:
    """Convert a validation.FoldResult dataclass to the dict format
    that metrics.aggregate_fold_results expects."""
    d = asdict(res)
    # Per-row predictions go to oof_predictions.csv, not the metrics JSON.
    d.pop("y_true", None)
    d.pop("y_prob", None)
    # aggregate_fold_results expects 'train_samples' / 'val_samples'
    d["train_samples"] = d.pop("n_train", 0)
    d["val_samples"] = d.pop("n_val", 0)
    # Convert feature_importance from list[tuple[str, float]] to
    # list[dict] format expected by _aggregate_feature_importance
    fi = d.get("feature_importance")
    if fi and isinstance(fi, list) and fi and isinstance(fi[0], (list, tuple)):
        d["feature_importance"] = [
            {"feature": name, "importance": imp} for name, imp in fi
        ]
    return d


# ---------------------------------------------------------------------------
# Cross-fitted calibration
# ---------------------------------------------------------------------------

def cross_fit_calibration(
    y_probs: list[np.ndarray],
    y_trues: list[np.ndarray],
) -> tuple[dict[str, Any], list[np.ndarray | None], Any]:
    """Calibrate each fold with calibrators fitted on earlier folds only.

    Fold k (k >= 1) is calibrated by Isotonic and Platt fitted on the
    out-of-fold predictions of folds < k. The method is chosen by Brier on
    folds 1..K-2 and its ECE/Brier are reported on fold K-1 alone, so no
    reported number comes from data the calibrator or the choice saw. The first fold
    stays uncalibrated.

    Returns (report, calibrated probabilities per fold with None for fold 0,
    the chosen calibrator refitted on every fold for deployment).
    """
    from sklearn.metrics import brier_score_loss

    from training.calibration import (
        IsotonicCalibration,
        PlattScalingCalibration,
        compute_calibration_report,
    )

    calibrators: dict[str, Any] = {"isotonic": IsotonicCalibration, "platt": PlattScalingCalibration}
    k_folds = len(y_probs)
    if k_folds < 3:  # callers guarantee >= 1 fold
        report: dict[str, Any] = compute_calibration_report(y_trues[-1], y_probs[-1])
        report.update(
            best_method="none",
            brier_score=round(float(brier_score_loss(y_trues[-1], y_probs[-1])), 4),
            protocol=f"uncalibrated: cross-fitting needs >= 3 folds, got {k_folds}",
        )
        return report, [None] * k_folds, None

    def _fit(name: str, upto: int) -> Any:
        cal = calibrators[name]()
        cal.fit(np.concatenate(y_probs[:upto]), np.concatenate(y_trues[:upto]))
        return cal

    preds: dict[str, list[np.ndarray | None]] = {
        name: [_fit(name, k).predict_proba(y_probs[k]) if k else None for k in range(k_folds)]
        for name in calibrators
    }
    sel_true = np.concatenate(y_trues[1:-1])
    sel_brier = {
        name: float(brier_score_loss(sel_true, np.concatenate([p for p in fold_preds[1:-1] if p is not None])))
        for name, fold_preds in preds.items()
    }
    best = min(sel_brier, key=lambda name: sel_brier[name])  # ties -> isotonic (first)
    last_pred = preds[best][-1]
    assert last_pred is not None

    report = compute_calibration_report(y_trues[-1], last_pred)
    report.update(
        best_method=best,
        brier_score=round(float(brier_score_loss(y_trues[-1], last_pred)), 4),
        raw_brier_score=round(float(brier_score_loss(y_trues[-1], y_probs[-1])), 4),
        selection_brier={name: round(b, 4) for name, b in sel_brier.items()},
        protocol=(
            "cross-fitted: fold k calibrated on folds < k; method chosen on folds "
            f"1..{k_folds - 2}; ece/mce/brier_score measured on fold {k_folds - 1} only"
        ),
    )
    logger.info(
        "Calibration (cross-fitted): selection Brier %s -> %s; reporting fold Brier raw=%.4f, %s=%.4f",
        sel_brier, best, report["raw_brier_score"], best, report["brier_score"],
    )
    return report, preds[best], _fit(best, k_folds)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="train_alpha158_candidate",
        description="Train LightGBM Alpha158-only classifier with walk-forward validation and calibration.",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Path to OHLCV CSV or Parquet file.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="direction_20d",
        help="Target column name (default: direction_20d).",
    )
    parser.add_argument(
        "--folds",
        type=str,
        default=None,
        help=(
            "Walk-forward folds as comma-separated train_end:val_year pairs. "
            'Example: "2021:2022,2022:2023,2023:2024"'
        ),
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        default=False,
        help="Deploy trained model to production path after training.",
    )
    parser.add_argument(
        "--holdout-year",
        type=int,
        default=None,
        help=(
            "Final holdout year, never used for selection (default: the last year "
            "in the data when it is after every fold's validation year)."
        ),
    )
    parser.add_argument(
        "--min-train-samples",
        type=int,
        default=500,
        help="Minimum training samples per fold (default: 500).",
    )
    return parser.parse_args(argv)


def _parse_folds(folds_str: str) -> list[tuple[int, int]]:
    """Parse '2021:2022,2022:2023,2023:2024' into [(2021,2022), ...]."""
    folds: list[tuple[int, int]] = []
    for pair in folds_str.split(","):
        pair = pair.strip()
        if ":" not in pair:
            raise ValueError(
                f"Invalid fold format '{pair}'. Expected train_end:val_year, "
                "e.g. '2021:2022'"
            )
        parts = pair.split(":")
        folds.append((int(parts[0]), int(parts[1])))
    return folds


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_ohlcv(data_path: str | None) -> pd.DataFrame:
    """Load OHLCV data from CSV or Parquet. Exits with instructions if missing."""
    if data_path is None:
        if _DEFAULT_DATA_PATH.exists():
            data_path = str(_DEFAULT_DATA_PATH)
            logger.info("Using default data path: %s", data_path)
        else:
            logger.error("No --data-path provided and default not found at %s", _DEFAULT_DATA_PATH)
            print("\n" + EXPECTED_SCHEMA)
            sys.exit(1)

    path = Path(data_path)
    if not path.exists():
        logger.error("Data file not found: %s", path)
        print("\n" + EXPECTED_SCHEMA)
        sys.exit(1)

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        df = pd.read_parquet(path)
    elif suffix == ".csv":
        df = pd.read_csv(path, parse_dates=["date"])
    else:
        logger.error("Unsupported file format '%s'. Use .csv or .parquet.", suffix)
        sys.exit(1)

    # Validate required columns
    required = {"symbol", "date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        logger.error("Missing required columns: %s", missing)
        print("\n" + EXPECTED_SCHEMA)
        sys.exit(1)

    df["date"] = pd.to_datetime(df["date"])
    logger.info(
        "Loaded %d rows, %d symbols, date range %s to %s",
        len(df),
        df["symbol"].nunique(),
        df["date"].min().strftime("%Y-%m-%d"),
        df["date"].max().strftime("%Y-%m-%d"),
    )
    return df


# ---------------------------------------------------------------------------
# Feature column detection
# ---------------------------------------------------------------------------

def _get_feature_columns(feature_df: pd.DataFrame) -> list[str]:
    """Extract the ordered list of feature columns (Alpha158 only)."""
    from config import FEATURE_LIST

    feature_cols: list[str] = []

    # Alpha158 features only
    for col in FEATURE_LIST:
        if col in feature_df.columns:
            feature_cols.append(col)

    return feature_cols


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def _make_model_factory(params: dict[str, Any]) -> Any:
    """Return a callable that creates a fresh adapted LGBEnsembleModel."""
    from models.lgb_model import LGBEnsembleModel

    # Separate boost-round / early-stopping from LightGBM params
    num_boost_round = params.pop("num_boost_round", 2000)
    early_stopping_rounds = params.pop("early_stopping_rounds", 100)

    def factory() -> _WalkForwardModelAdapter:
        model = LGBEnsembleModel(
            num_boost_round=num_boost_round,
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=-1,
            params=params,
        )
        return _WalkForwardModelAdapter(model)

    # Restore keys so the dict remains usable for metadata
    params["num_boost_round"] = num_boost_round
    params["early_stopping_rounds"] = early_stopping_rounds

    return factory


# ---------------------------------------------------------------------------
# Main training pipeline
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # -- Guard: LightGBM availability --
    if not _HAS_LGB:
        logger.error(
            "LightGBM is not installed. Install with:\n"
            "  pip install lightgbm\n"
            "  # or: pip install -r requirements.txt"
        )
        sys.exit(1)

    # -- 1. Load OHLCV data --
    logger.info("=" * 60)
    logger.info("STEP 1: Loading OHLCV data")
    logger.info("=" * 60)
    ohlcv_df = _load_ohlcv(args.data_path)

    # -- 2. Build feature matrix --
    logger.info("=" * 60)
    logger.info("STEP 2: Building feature matrix (Alpha158 + extras)")
    logger.info("=" * 60)

    from training.feature_pipeline import build_feature_matrix

    feature_df = build_feature_matrix(ohlcv_df)
    if feature_df.empty:
        logger.error("Feature matrix is empty. Check data quality and date range.")
        sys.exit(1)

    feature_cols = _get_feature_columns(feature_df)
    logger.info("Feature matrix: %d rows, %d features", len(feature_df), len(feature_cols))

    # Validate target column exists
    target_col = args.target
    if target_col not in feature_df.columns:
        available_targets = [c for c in feature_df.columns if "direction" in c or "return" in c]
        logger.error(
            "Target column '%s' not found. Available targets: %s",
            target_col,
            available_targets,
        )
        sys.exit(1)

    # -- 3. Configure walk-forward --
    logger.info("=" * 60)
    logger.info("STEP 3: Configuring walk-forward validation")
    logger.info("=" * 60)

    from training.validation import (
        WalkForwardConfig,
        generate_holdout_split,
        generate_splits,
        run_walk_forward,
    )

    if args.folds:
        folds = _parse_folds(args.folds)
    else:
        folds = [(2021, 2022), (2022, 2023), (2023, 2024), (2024, 2025)]

    holdout_year = args.holdout_year
    if holdout_year is None:
        last_year = int(pd.to_datetime(feature_df["date"]).dt.year.max())
        if last_year > max(vy for _, vy in folds):
            holdout_year = last_year

    wf_config = WalkForwardConfig(
        folds=folds,
        target_col=target_col,
        min_train_samples=args.min_train_samples,
        holdout_year=holdout_year,
    )
    logger.info(
        "Walk-forward folds: %s | embargo %d trading days | holdout year %s",
        wf_config.folds, wf_config.embargo_days, wf_config.holdout_year,
    )
    logger.info("Target: %s | Min train samples: %d", target_col, wf_config.min_train_samples)

    # -- 4. Generate splits --
    logger.info("=" * 60)
    logger.info("STEP 4: Generating temporal splits")
    logger.info("=" * 60)

    splits = generate_splits(feature_df, wf_config, feature_cols)
    if not splits:
        logger.error(
            "No valid walk-forward splits. Check that data covers the fold years: %s",
            folds,
        )
        sys.exit(1)

    logger.info("Generated %d valid splits", len(splits))

    # -- 5. Run walk-forward validation --
    logger.info("=" * 60)
    logger.info("STEP 5: Running walk-forward validation")
    logger.info("=" * 60)

    from config import LIGHTGBM_PARAMS

    # Merge LIGHTGBM_PARAMS with classification overrides
    train_params = {**LIGHTGBM_PARAMS, **_CLASSIFICATION_OVERRIDES}
    model_factory = _make_model_factory(dict(train_params))

    # Prepare forward-return arrays for return-based metrics
    return_col = "forward_return_20d" if "20d" in target_col else "forward_return_60d"
    val_returns: list[np.ndarray] | None = None
    if return_col in feature_df.columns:
        val_returns = [
            feature_df.loc[split.val_index, return_col].to_numpy(dtype=np.float64)
            for split in splits
        ]

    fold_results = run_walk_forward(
        model_factory=model_factory,
        splits=splits,
        return_col=return_col,
        val_returns=val_returns,
    )

    if not fold_results:
        logger.error("All folds failed. Cannot proceed with training.")
        sys.exit(1)

    logger.info("Walk-forward complete: %d folds evaluated", len(fold_results))

    # -- 6. Train final model on all non-holdout data --
    logger.info("=" * 60)
    logger.info("STEP 6: Training final model on all non-holdout data")
    logger.info("=" * 60)

    from models.lgb_model import LGBEnsembleModel

    holdout_split = generate_holdout_split(feature_df, wf_config, feature_cols)
    if holdout_split is not None:
        # Every row before the holdout year, embargoed like a fold.
        X_all, y_all = holdout_split.X_train, holdout_split.y_train
    else:
        final_df = feature_df.dropna(subset=[target_col])
        X_all = final_df[feature_cols].values.astype(np.float32)
        y_all = final_df[target_col].values.astype(np.float32)

    logger.info("Final training set: %d samples, %d features", X_all.shape[0], X_all.shape[1])

    # For the final model, use same params but no early stopping (no val set)
    final_params = {k: v for k, v in train_params.items()
                    if k not in ("num_boost_round", "early_stopping_rounds")}
    # Use the best iteration from walk-forward as num_boost_round
    best_iters = [fr.best_iteration for fr in fold_results if fr.best_iteration is not None]
    if best_iters:
        final_num_rounds = int(np.median(best_iters))
        logger.info(
            "Using median best iteration from folds: %d (range: %d-%d)",
            final_num_rounds,
            min(best_iters),
            max(best_iters),
        )
    else:
        final_num_rounds = train_params.get("num_boost_round", 2000)
        logger.info("No early-stopping info; using configured num_boost_round: %d", final_num_rounds)

    final_model = LGBEnsembleModel(
        num_boost_round=final_num_rounds,
        early_stopping_rounds=0,  # no early stopping for final model
        verbose_eval=-1,
        params=final_params,
    )
    final_model.fit(X_all, y_all)

    logger.info("Final model trained: %d trees", final_model._model.num_trees())

    # -- 7. Compute aggregate results and calibration --
    logger.info("=" * 60)
    logger.info("STEP 7: Computing aggregate metrics and calibration")
    logger.info("=" * 60)

    from training.metrics import (
        aggregate_fold_results,
        generate_training_report,
    )

    fold_dicts = [fold_result_to_dict(fr) for fr in fold_results]
    aggregate = aggregate_fold_results(fold_dicts)

    # Out-of-fold predictions straight from the walk-forward (no refit).
    y_probs = [np.asarray(fr.y_prob, dtype=np.float64) for fr in fold_results]
    y_trues = [np.asarray(fr.y_true, dtype=int) for fr in fold_results]
    calibration, calibrated, best_calibrator = cross_fit_calibration(y_probs, y_trues)

    extra_cols = [c for c in (return_col, "momentum_20d") if c in feature_df.columns]

    def _prediction_frame(sp: Any, kind: str, p_up: Any, p_raw: np.ndarray) -> pd.DataFrame:
        frame = feature_df.loc[sp.val_index, ["date", "symbol", *extra_cols]].reset_index(drop=True)
        frame.insert(2, "fold", sp.fold_id)
        frame.insert(3, "split", kind)
        frame["p_up"] = p_up
        frame["p_raw"] = p_raw
        frame["y"] = sp.y_val.astype(int)
        frame["train_base_rate"] = sp.train_base_rate
        return frame

    split_by_fold = {sp.fold_id: sp for sp in splits}
    oof_frames = [
        # the first fold has no earlier fold to calibrate on: p_up is NaN there
        _prediction_frame(split_by_fold[fr.fold_id], "oof", np.nan if p_cal is None else p_cal, p_raw)
        for fr, p_raw, p_cal in zip(fold_results, y_probs, calibrated)
    ]

    # -- Holdout: scored once, for the report only (never used for selection) --
    if holdout_split is not None:
        from sklearn.metrics import brier_score_loss, roc_auc_score

        from training.calibration import compute_calibration_report

        h_raw = np.clip(final_model.predict(holdout_split.X_val), 0.0, 1.0)
        h_p = best_calibrator.predict_proba(h_raw) if best_calibrator is not None else h_raw
        h_true = holdout_split.y_val.astype(int)
        holdout_report = compute_calibration_report(h_true, h_p)
        holdout_report.update(
            year=holdout_split.val_year,
            n=int(len(h_true)),
            brier_score=round(float(brier_score_loss(h_true, h_p)), 4),
            roc_auc=round(float(roc_auc_score(h_true, h_p)), 4) if len(np.unique(h_true)) > 1 else None,
        )
        calibration["holdout"] = holdout_report
        logger.info("Holdout %d: %s", holdout_split.val_year, {
            k: holdout_report[k] for k in ("n", "roc_auc", "brier_score", "ece")
        })

        oof_frames.append(_prediction_frame(holdout_split, "holdout", h_p, h_raw))

    oof_predictions = pd.concat(oof_frames, ignore_index=True).rename(
        columns={return_col: "fwd_ret_20d" if "20d" in return_col else "fwd_ret_60d"}
    )

    logger.info(
        "Aggregate: mean_hit_rate=%.2f%%, mean_auc=%s, ece=%.4f",
        (aggregate.get("mean_hit_rate") or 0) * 100,
        f"{aggregate.get('mean_roc_auc'):.4f}" if aggregate.get("mean_roc_auc") else "N/A",
        calibration.get("ece", 0.0),
    )

    # -- 8. Save model artifact --
    logger.info("=" * 60)
    logger.info("STEP 8: Saving model artifact")
    logger.info("=" * 60)

    from training.dataset_builder import SURVIVORSHIP_NOTE
    from training.model_registry import deploy_to_production, save_model_artifact
    from training.provenance import dataframe_sha256, git_sha
    from training.validation import INNER_VAL_FRAC

    # Date + commit: a same-day rerun of the same code raises FileExistsError
    # in save_model_artifact instead of overwriting the artifact.
    datestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    model_version = f"lightgbm_alpha158_{datestamp}_{(git_sha() or 'nogit')[:7]}"

    training_metadata = {
        "target": target_col,
        "folds": [f"{te}:{vy}" for te, vy in wf_config.folds],
        "n_folds_completed": len(fold_results),
        "n_features": len(feature_cols),
        "n_total_samples": int(X_all.shape[0]),
        "final_num_boost_round": final_num_rounds,
        "lightgbm_params": {k: v for k, v in train_params.items()},
        "data_date_range": {
            "min": feature_df["date"].min().strftime("%Y-%m-%d"),
            "max": feature_df["date"].max().strftime("%Y-%m-%d"),
        },
        "n_symbols": int(feature_df["symbol"].nunique()),
        "universe": SURVIVORSHIP_NOTE,
        "embargo_days": wf_config.embargo_days,
        "early_stopping": f"inner slice: last {INNER_VAL_FRAC:.0%} of each fold's training dates",
        "holdout_year": holdout_split.val_year if holdout_split is not None else None,
        "data_sha256": dataframe_sha256(feature_df),
    }

    artifact_dir = save_model_artifact(
        model=final_model,
        feature_list=feature_cols,
        training_metadata=training_metadata,
        validation_metrics=fold_dicts,
        calibration_report=calibration,
        model_version=model_version,
        calibrator=best_calibrator,
        oof_predictions=oof_predictions,
    )
    logger.info("Artifact saved: %s", artifact_dir)

    # -- 9. Deploy if requested --
    if args.deploy:
        logger.info("=" * 60)
        logger.info("STEP 9: Deploying to production")
        logger.info("=" * 60)
        # Gated: raises GateFailedError (nothing copied) unless the gate passes.
        prod_path = deploy_to_production(model_version, status="candidate")
        logger.info("Deployed to production: %s", prod_path)
    else:
        logger.info("Skipping deployment (use --deploy flag to deploy)")

    # -- 10. Print training report --
    logger.info("=" * 60)
    logger.info("STEP 10: Training Report")
    logger.info("=" * 60)

    report_config = {
        "target": target_col,
        "objective": "binary",
        "n_features": len(feature_cols),
        "num_boost_round (final)": final_num_rounds,
        "learning_rate": train_params.get("learning_rate"),
        "num_leaves": train_params.get("num_leaves"),
        "feature_fraction": train_params.get("feature_fraction"),
        "bagging_fraction": train_params.get("bagging_fraction"),
    }

    report = generate_training_report(
        aggregate_results=aggregate,
        calibration=calibration,
        config=report_config,
        model_version=model_version,
    )
    print("\n" + report)

    logger.info("Training pipeline complete. Model version: %s", model_version)


if __name__ == "__main__":
    main()
