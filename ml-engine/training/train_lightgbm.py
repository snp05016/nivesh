"""
LightGBM baseline training script with walk-forward temporal validation.

Runnable as:
    python -m training.train_lightgbm_baseline [--data-path PATH] [--target direction_20d] [--deploy]

Flow:
    1. Load OHLCV data (CSV or Parquet)
    2. Build Alpha158 + extra feature matrix via feature_builder
    3. Walk-forward temporal validation (no future leakage)
    4. Train final model on all available data
    5. Save versioned artifact to registry
    6. Optionally deploy to production path
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

    run_walk_forward calls:
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)])
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
# CLI argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="train_lightgbm_baseline",
        description="Train LightGBM baseline classifier with walk-forward validation.",
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
    """Extract the ordered list of feature columns (Alpha158 + extra + sector dummies)."""
    from config import FEATURE_LIST
    from training.feature_pipeline import EXTRA_FEATURES

    feature_cols: list[str] = []

    # Alpha158 features
    for col in FEATURE_LIST:
        if col in feature_df.columns:
            feature_cols.append(col)

    # Extra features
    for col in EXTRA_FEATURES:
        if col in feature_df.columns:
            feature_cols.append(col)

    # Sector one-hot columns
    sector_cols = sorted(c for c in feature_df.columns if c.startswith("sector_"))
    feature_cols.extend(sector_cols)

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

    from training.validation import WalkForwardConfig, generate_splits, run_walk_forward

    if args.folds:
        folds = _parse_folds(args.folds)
    else:
        folds = [(2021, 2022), (2022, 2023), (2023, 2024), (2024, 2025)]

    wf_config = WalkForwardConfig(
        folds=folds,
        target_col=target_col,
        min_train_samples=args.min_train_samples,
    )
    logger.info("Walk-forward folds: %s", wf_config.folds)
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
        val_returns = []
        for split in splits:
            # Extract returns aligned with validation dates
            val_mask = pd.to_datetime(feature_df["date"]).dt.year == split.val_year
            val_df = feature_df.loc[val_mask].dropna(subset=[wf_config.target_col])
            if return_col in val_df.columns:
                val_returns.append(val_df[return_col].values.astype(np.float64))
            else:
                val_returns.append(np.zeros(split.y_val.shape[0]))

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

    # -- 6. Train final model on ALL data --
    logger.info("=" * 60)
    logger.info("STEP 6: Training final model on ALL available data")
    logger.info("=" * 60)

    from models.lgb_model import LGBEnsembleModel

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
        generate_markdown_report,
    )

    fold_dicts = [fold_result_to_dict(fr) for fr in fold_results]
    aggregate = aggregate_fold_results(fold_dicts)

    # Compute calibration from all validation predictions pooled together
    all_y_true: list[np.ndarray] = []
    all_y_prob: list[np.ndarray] = []

    for split in splits:
        adapter = model_factory()
        adapter.fit(split.X_train, split.y_train, eval_set=[(split.X_val, split.y_val)])
        y_prob = np.clip(adapter.predict(split.X_val), 0.0, 1.0)
        all_y_true.append(split.y_val.astype(int))
        all_y_prob.append(y_prob)

    if all_y_true:
        pooled_y_true = np.concatenate(all_y_true)
        pooled_y_prob = np.concatenate(all_y_prob)
        calibration = compute_calibration_report(pooled_y_true, pooled_y_prob)
    else:
        calibration = {"buckets": [], "ece": 0.0, "mce": 0.0}

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

    from training.model_registry import save_model_artifact, deploy_to_production

    datestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    model_version = f"lightgbm_baseline_alpha158_v1_{datestamp}"

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
    }

    artifact_dir = save_model_artifact(
        model=final_model,
        feature_list=feature_cols,
        training_metadata=training_metadata,
        validation_metrics=fold_dicts,
        calibration_report=calibration,
        model_version=model_version,
    )
    logger.info("Artifact saved: %s", artifact_dir)

    # -- 9. Deploy if requested --
    if args.deploy:
        logger.info("=" * 60)
        logger.info("STEP 9: Deploying to production")
        logger.info("=" * 60)
        prod_path = deploy_to_production(model_version)
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
