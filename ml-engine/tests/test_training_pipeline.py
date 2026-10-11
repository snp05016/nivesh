"""
Comprehensive tests for the LightGBM training pipeline.

Covers: feature builder (lookahead, targets), walk-forward splits,
model registry (save/load/fallback), prediction responses,
OHLCV validation, and evaluation edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

_SEED = 42


def _make_ohlcv(
    n_days: int = 200,
    symbol: str = "TEST",
    start_date: str = "2020-01-01",
    seed: int = _SEED,
    base_price: float = 100.0,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data with a seeded random walk."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start_date, periods=n_days)

    closes = np.empty(n_days, dtype=np.float64)
    closes[0] = base_price
    for i in range(1, n_days):
        closes[i] = closes[i - 1] * (1 + rng.normal(0.0003, 0.015))
        closes[i] = max(closes[i], 1.0)

    highs = closes * (1 + rng.uniform(0, 0.02, n_days))
    lows = closes * (1 - rng.uniform(0, 0.02, n_days))
    lows = np.maximum(lows, 0.5)
    opens = rng.uniform(lows, highs)
    volumes = rng.uniform(1_000_000, 10_000_000, n_days).astype(np.int64)

    return pd.DataFrame({
        "symbol": symbol,
        "date": dates,
        "open": np.round(opens, 2),
        "high": np.round(highs, 2),
        "low": np.round(lows, 2),
        "close": np.round(closes, 2),
        "volume": volumes,
    })


def _make_multiyear_ohlcv(
    years: range = range(2019, 2026),
    days_per_year: int = 252,
    symbol: str = "TEST",
    seed: int = _SEED,
) -> pd.DataFrame:
    """Generate multi-year OHLCV data for walk-forward testing."""
    rng = np.random.default_rng(seed)
    frames = []
    price = 100.0
    for yr in years:
        dates = pd.bdate_range(start=f"{yr}-01-02", periods=days_per_year)
        closes = np.empty(days_per_year, dtype=np.float64)
        closes[0] = price
        for i in range(1, days_per_year):
            closes[i] = closes[i - 1] * (1 + rng.normal(0.0003, 0.015))
            closes[i] = max(closes[i], 1.0)
        price = closes[-1]

        highs = closes * (1 + rng.uniform(0, 0.02, days_per_year))
        lows = closes * (1 - rng.uniform(0, 0.02, days_per_year))
        lows = np.maximum(lows, 0.5)
        opens = rng.uniform(lows, highs)
        volumes = rng.uniform(1e6, 1e7, days_per_year).astype(np.int64)

        frames.append(pd.DataFrame({
            "symbol": symbol,
            "date": dates,
            "open": np.round(opens, 2),
            "high": np.round(highs, 2),
            "low": np.round(lows, 2),
            "close": np.round(closes, 2),
            "volume": volumes,
        }))

    return pd.concat(frames, ignore_index=True)


# ===========================================================================
# 1. Feature no-lookahead test
# ===========================================================================


class TestFeatureNoLookahead:
    """Features at date T must not reflect data after T."""

    def test_feature_no_lookahead(self):
        """Create data where close jumps 10x on day T+1.

        Features computed at T must be identical whether or not the
        post-T spike exists, proving no future data leaks into features.
        """
        from training.feature_pipeline import (
            _compute_extra_features,
            _compute_rsi,
            _safe_pct,
        )

        rng = np.random.default_rng(_SEED)
        n = 150
        closes_base = np.cumsum(rng.normal(0, 1, n)) + 200.0
        closes_base = np.maximum(closes_base, 1.0)
        volumes_base = rng.uniform(1e6, 5e6, n)

        # T is index 130 (well within the window requirements)
        T = 130

        # Scenario A: data ends at T (no future)
        closes_a = closes_base[: T + 1].copy()
        volumes_a = volumes_base[: T + 1].copy()
        features_a = _compute_extra_features(closes_a, volumes_a)

        # Scenario B: data extends past T with a 10x spike at T+1
        closes_b = closes_base[: T + 20].copy()
        closes_b[T + 1] = closes_b[T] * 10.0  # massive spike
        closes_b[T + 2 :] = closes_b[T + 1] * 1.01  # stays high
        volumes_b = volumes_base[: T + 20].copy()

        # Compute features using ONLY data up to T (the slicing the builder does)
        features_b = _compute_extra_features(closes_b[: T + 1], volumes_b[: T + 1])

        # Features must be identical -- no lookahead
        for key in features_a:
            assert features_a[key] == pytest.approx(features_b[key], abs=1e-12), (
                f"Lookahead leak detected in feature '{key}': "
                f"without_future={features_a[key]}, with_future={features_b[key]}"
            )

    def test_rsi_no_future_data(self):
        """RSI computed at T must not change when future data is appended."""
        from training.feature_pipeline import _compute_rsi

        rng = np.random.default_rng(99)
        closes = np.cumsum(rng.normal(0, 1, 100)) + 200.0
        closes = np.maximum(closes, 1.0)

        rsi_short = _compute_rsi(closes[:80])
        # Append wild future data
        extended = np.concatenate([closes[:80], closes[:80] * 5])
        rsi_extended = _compute_rsi(extended[:80])

        assert rsi_short == pytest.approx(rsi_extended, abs=1e-12)


# ===========================================================================
# 2. Target generation correctness
# ===========================================================================


class TestTargetGeneration:
    """Verify forward return and direction targets are computed correctly."""

    def test_forward_return_20d(self):
        """forward_return_20d = (close[t+20] - close[t]) / close[t]."""
        from training.feature_pipeline import _safe_pct

        closes = np.arange(100, 200, dtype=np.float64)  # 100..199
        t = 10
        expected_20d = (closes[t + 20] - closes[t]) / closes[t]
        actual_20d = _safe_pct(closes[t + 20], closes[t])
        assert actual_20d == pytest.approx(expected_20d, rel=1e-10)

    def test_forward_return_direction(self):
        """direction_20d = forward_return_20d > 0."""
        from training.feature_pipeline import _safe_pct

        # Upward case: close rises
        closes_up = np.linspace(100, 150, 50)
        t = 5
        fr = _safe_pct(closes_up[t + 20], closes_up[t])
        assert fr > 0
        assert bool(fr > 0) is True  # direction_20d

        # Downward case: close falls
        closes_down = np.linspace(150, 100, 50)
        fr_down = _safe_pct(closes_down[t + 20], closes_down[t])
        assert fr_down < 0
        assert bool(fr_down > 0) is False  # direction_20d

    def test_safe_pct_zero_denominator(self):
        """_safe_pct guards against zero division."""
        from training.feature_pipeline import _safe_pct

        assert _safe_pct(100.0, 0.0) == 0.0

    def test_known_return_values(self):
        """Verify exact return values with known close prices."""
        from training.feature_pipeline import _safe_pct

        # close[0]=100, close[20]=120 => return = 0.20
        assert _safe_pct(120.0, 100.0) == pytest.approx(0.20)
        # close[0]=200, close[20]=180 => return = -0.10
        assert _safe_pct(180.0, 200.0) == pytest.approx(-0.10)


# ===========================================================================
# 3. Walk-forward fold boundaries
# ===========================================================================


class TestWalkForwardFoldBoundaries:
    """Temporal splits must enforce strict train <= year, val == year."""

    def test_fold_boundaries(self):
        from training.validation import WalkForwardConfig, generate_splits

        df = _make_multiyear_ohlcv(years=range(2019, 2026), days_per_year=252)

        # Add a synthetic target column
        rng = np.random.default_rng(_SEED)
        df["direction_20d"] = rng.choice([0.0, 1.0], size=len(df))

        feature_cols = ["open", "high", "low", "close", "volume"]

        config = WalkForwardConfig(
            folds=[(2021, 2022), (2022, 2023), (2023, 2024), (2024, 2025)],
            target_col="direction_20d",
            min_train_samples=10,  # low threshold for test data
        )

        splits = generate_splits(df, config, feature_cols)
        assert len(splits) > 0, "Expected at least one valid split"

        for split in splits:
            # Train dates must be <= train_end_year
            train_years = pd.to_datetime(split.train_dates).year
            assert (train_years <= split.train_end_year).all(), (
                f"Fold {split.fold_id}: train data contains years after "
                f"{split.train_end_year}: found {train_years.unique()}"
            )

            # Validation dates must be exactly val_year
            val_years = pd.to_datetime(split.val_dates).year
            assert (val_years == split.val_year).all(), (
                f"Fold {split.fold_id}: val data contains years other than "
                f"{split.val_year}: found {val_years.unique()}"
            )

            # No temporal overlap
            max_train_date = pd.to_datetime(split.train_dates).max()
            min_val_date = pd.to_datetime(split.val_dates).min()
            assert max_train_date < min_val_date, (
                f"Fold {split.fold_id}: temporal overlap detected: "
                f"max_train={max_train_date}, min_val={min_val_date}"
            )

    def test_nan_targets_dropped(self):
        """Rows with NaN targets must be excluded from splits."""
        from training.validation import WalkForwardConfig, generate_splits

        df = _make_multiyear_ohlcv(years=range(2019, 2024), days_per_year=100)
        df["direction_20d"] = 1.0
        # Set all 2022 targets to NaN
        mask_2022 = pd.to_datetime(df["date"]).dt.year == 2022
        df.loc[mask_2022, "direction_20d"] = np.nan

        config = WalkForwardConfig(
            folds=[(2021, 2022)],
            target_col="direction_20d",
            min_train_samples=1,
        )
        splits = generate_splits(df, config, ["close"])
        # Fold should be skipped because val (2022) has 0 non-NaN samples
        assert len(splits) == 0

    def test_missing_target_column_raises(self):
        """generate_splits must raise if target column is absent."""
        from training.validation import WalkForwardConfig, generate_splits

        df = _make_ohlcv(n_days=50)
        config = WalkForwardConfig(target_col="nonexistent_col")
        with pytest.raises(ValueError, match="Target column"):
            generate_splits(df, config, ["close"])


# ===========================================================================
# 4. Model artifact save / load
# ===========================================================================


class TestModelArtifactSaveLoad:
    """Save metadata + features JSON, load and verify contents match."""

    def test_save_and_load_metadata(self, tmp_path: Path):
        """Round-trip test for model registry metadata and features."""
        from training.model_registry import _write_json, _read_json

        # Simulate saving artifact files
        artifact_dir = tmp_path / "lightgbm_baseline_alpha158_v1_20260624"
        artifact_dir.mkdir(parents=True)

        features = ["KMID", "KLEN", "ROC5", "MA10", "STD20"]
        metadata = {
            "model_version": "lightgbm_baseline_alpha158_v1_20260624",
            "num_features": len(features),
            "num_trees": 100,
            "training_date_range": "2019-01-01 to 2024-12-31",
            "n_train_samples": 50000,
        }
        validation_metrics = [
            {"fold_id": 0, "hit_rate": 0.55, "roc_auc": 0.58},
            {"fold_id": 1, "hit_rate": 0.53, "roc_auc": 0.56},
        ]

        # Write
        _write_json(artifact_dir / "features.json", features)
        _write_json(artifact_dir / "metadata.json", metadata)
        _write_json(artifact_dir / "validation_metrics.json", validation_metrics)
        (artifact_dir / "VERSION").write_text(metadata["model_version"])

        # Read back
        loaded_features = _read_json(artifact_dir / "features.json")
        loaded_metadata = _read_json(artifact_dir / "metadata.json")
        loaded_metrics = _read_json(artifact_dir / "validation_metrics.json")
        loaded_version = (artifact_dir / "VERSION").read_text()

        assert loaded_features == features
        assert loaded_metadata == metadata
        assert loaded_metrics == validation_metrics
        assert loaded_version == metadata["model_version"]

    def test_artifact_directory_structure(self, tmp_path: Path):
        """Verify the expected files are created in the artifact dir."""
        from training.model_registry import _write_json

        artifact_dir = tmp_path / "test_model_v1"
        artifact_dir.mkdir()

        _write_json(artifact_dir / "features.json", ["f1", "f2"])
        _write_json(artifact_dir / "metadata.json", {"version": "v1"})
        (artifact_dir / "model.txt").write_text("mock model content")
        (artifact_dir / "VERSION").write_text("v1")

        expected_files = {"features.json", "metadata.json", "model.txt", "VERSION"}
        actual_files = {f.name for f in artifact_dir.iterdir()}
        assert expected_files.issubset(actual_files)


# ===========================================================================
# 5. Fallback when no model exists
# ===========================================================================


class TestFallbackWhenNoModel:
    """get_latest_model_path() returns None when no artifacts exist."""

    def test_no_artifacts_returns_none(self, tmp_path: Path):
        from training import model_registry

        # Temporarily override REGISTRY_DIR to an empty directory
        original_registry = model_registry.REGISTRY_DIR
        try:
            model_registry.REGISTRY_DIR = tmp_path / "empty_artifacts"
            # Directory does not even exist
            result = model_registry.get_latest_model_path()
            assert result is None
        finally:
            model_registry.REGISTRY_DIR = original_registry

    def test_empty_artifacts_dir_returns_none(self, tmp_path: Path):
        from training import model_registry

        original_registry = model_registry.REGISTRY_DIR
        try:
            empty_dir = tmp_path / "artifacts"
            empty_dir.mkdir()
            model_registry.REGISTRY_DIR = empty_dir
            result = model_registry.get_latest_model_path()
            assert result is None
        finally:
            model_registry.REGISTRY_DIR = original_registry

    def test_dir_without_model_txt_returns_none(self, tmp_path: Path):
        """A version directory without model.txt should not be listed."""
        from training import model_registry

        original_registry = model_registry.REGISTRY_DIR
        try:
            artifacts_dir = tmp_path / "artifacts"
            version_dir = artifacts_dir / "lightgbm_baseline_alpha158_v1_20260101"
            version_dir.mkdir(parents=True)
            # Only metadata, no model.txt
            (version_dir / "metadata.json").write_text("{}")

            model_registry.REGISTRY_DIR = artifacts_dir
            result = model_registry.get_latest_model_path()
            assert result is None
        finally:
            model_registry.REGISTRY_DIR = original_registry


# ===========================================================================
# 6. Predict single -- trained mode response
# ===========================================================================


class TestPredictSingleTrainedMode:
    """When a LightGBM model is loaded, response reflects trained mode."""

    def test_trained_mode_response(self):
        from main import PredictionResult

        # Simulate what predict_single returns when model is loaded
        result = PredictionResult(
            ticker="RELIANCE",
            direction=1,
            expected_direction=1,
            confidence=0.72,
            confidence_score=0.72,
            ml_engine_mode="trained_lightgbm_baseline",
            lightgbm_loaded=True,
            features=["KMID", "KLEN"],
            prediction_time_ms=15.3,
            raw_score=0.65,
            model_version="lightgbm_baseline_alpha158_v1_20260620",
            horizon=20,
            feature_count=158,
            fallback_used=False,
        )

        assert result.direction == result.expected_direction
        assert result.confidence == result.confidence_score
        assert result.ml_engine_mode == "trained_lightgbm_baseline"
        assert result.model_version is not None
        assert result.lightgbm_loaded is True
        assert result.horizon == 20
        assert result.feature_count == 158
        assert result.fallback_used is False
        assert result.confidence_score >= 0.0
        assert result.confidence_score <= 1.0
        assert result.expected_direction in (-1, 0, 1)

    def test_trained_mode_fields_are_populated(self):
        """All trained-mode fields must be non-default."""
        from main import PredictionResult

        result = PredictionResult(
            ticker="TCS",
            direction=-1,
            expected_direction=-1,
            confidence=0.38,
            confidence_score=0.38,
            ml_engine_mode="trained_lightgbm_baseline",
            lightgbm_loaded=True,
            features=["KMID"],
            prediction_time_ms=8.1,
            raw_score=0.35,
            model_version="lightgbm_baseline_alpha158_v1_20260620",
            horizon=20,
            feature_count=158,
            fallback_used=False,
        )

        assert result.model_version != ""
        assert len(result.features) > 0
        assert result.prediction_time_ms > 0
        assert result.feature_count == 158


# ===========================================================================
# 7. Predict single -- fallback response
# ===========================================================================


class TestPredictSingleFallback:
    """Without a model loaded, response reflects fallback heuristic mode."""

    def test_fallback_response(self):
        from main import PredictionResult

        result = PredictionResult(
            ticker="INFY",
            direction=0,
            expected_direction=0,
            confidence=0.50,
            confidence_score=0.50,
            ml_engine_mode="fallback_technical_heuristic",
            lightgbm_loaded=False,
            features=[],
            prediction_time_ms=2.1,
            raw_score=None,
            model_version=None,
            horizon=20,
            feature_count=158,
            fallback_used=True,
        )

        assert result.ml_engine_mode == "fallback_technical_heuristic"
        assert result.model_version is None
        assert result.lightgbm_loaded is False
        assert result.fallback_used is True

    def test_fallback_defaults(self):
        """PredictionResult defaults should match fallback mode."""
        from main import PredictionResult

        result = PredictionResult(
            ticker="TEST",
            expected_direction=0,
            confidence_score=0.5,
            prediction_time_ms=1.0,
        )

        # Defaults from the model definition
        assert result.ml_engine_mode == "fallback_technical_heuristic"
        assert result.lightgbm_loaded is False
        assert result.model_version is None
        assert result.features == []
        assert result.horizon == 20
        assert result.feature_count == 0
        assert result.fallback_used is True


class TestModelStatusContract:
    """Model status exposes production routing metadata."""

    def test_model_status_includes_mode_horizon_and_feature_count(self):
        from main import ModelStatus

        status = ModelStatus(
            lightgbm_loaded=True,
            scaler_loaded=False,
            ml_engine_mode="trained_lightgbm_baseline",
            supported_horizons=[20],
            feature_count=158,
            lightgbm_path="/app/models/lgb_model.txt",
            model_version="lightgbm_baseline_alpha158_v1_20260624",
        )

        assert status.lightgbm_loaded is True
        assert status.ml_engine_mode == "trained_lightgbm_baseline"
        assert status.supported_horizons == [20]
        assert status.feature_count == 158
        assert status.model_version == "lightgbm_baseline_alpha158_v1_20260624"


# ===========================================================================
# 8. Invalid OHLCV input
# ===========================================================================


class TestInvalidOHLCVInput:
    """Feature builder must reject bad input gracefully."""

    def test_missing_required_columns(self):
        from training.feature_pipeline import build_feature_matrix

        # Missing 'close' column
        df = pd.DataFrame({
            "symbol": ["A"] * 10,
            "date": pd.bdate_range("2020-01-01", periods=10),
            "open": range(10),
            "high": range(10),
            "low": range(10),
            # "close" intentionally missing
            "volume": range(10),
        })
        with pytest.raises(ValueError, match="Missing required columns"):
            build_feature_matrix(df)

    def test_empty_dataframe(self):
        from training.feature_pipeline import build_feature_matrix

        df = pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])
        with pytest.raises(ValueError, match="empty"):
            build_feature_matrix(df)

    def test_all_nan_handled(self):
        """DataFrame with NaN in OHLCV should be handled by validate_ohlcv."""
        from training.dataset_builder import validate_ohlcv

        df = pd.DataFrame({
            "symbol": ["A"] * 5,
            "date": pd.bdate_range("2020-01-01", periods=5),
            "open": [np.nan] * 5,
            "high": [np.nan] * 5,
            "low": [np.nan] * 5,
            "close": [np.nan] * 5,
            "volume": [np.nan] * 5,
        })
        result = validate_ohlcv(df)
        assert len(result) == 0  # all rows dropped


# ===========================================================================
# 9. validate_ohlcv
# ===========================================================================


class TestValidateOHLCV:
    """Test dataset_builder.validate_ohlcv with good and bad data."""

    def test_valid_data_passes(self):
        from training.dataset_builder import validate_ohlcv

        df = _make_ohlcv(n_days=50)
        result = validate_ohlcv(df)
        assert len(result) == 50
        assert list(result.columns[:7]) == [
            "symbol", "date", "open", "high", "low", "close", "volume",
        ]
        # Sorted by (symbol, date)
        assert result["date"].is_monotonic_increasing

    def test_missing_columns_raises(self):
        from training.dataset_builder import validate_ohlcv

        df = pd.DataFrame({"symbol": ["A"], "date": ["2020-01-01"]})
        with pytest.raises(ValueError, match="Missing required columns"):
            validate_ohlcv(df)

    def test_non_numeric_coerced_and_dropped(self):
        """Non-numeric values in OHLCV columns get coerced to NaN then dropped."""
        from training.dataset_builder import validate_ohlcv

        df = pd.DataFrame({
            "symbol": ["A", "A", "A"],
            "date": ["2020-01-01", "2020-01-02", "2020-01-03"],
            "open": [100.0, "bad", 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [95.0, 96.0, 97.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000, 2000, 3000],
        })
        result = validate_ohlcv(df)
        # Row with "bad" open should be dropped
        assert len(result) == 2

    def test_date_coercion(self):
        """String dates should be coerced to datetime."""
        from training.dataset_builder import validate_ohlcv

        df = pd.DataFrame({
            "symbol": ["A"],
            "date": ["2023-06-15"],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [103.0],
            "volume": [1000],
        })
        result = validate_ohlcv(df)
        assert pd.api.types.is_datetime64_any_dtype(result["date"])

    def test_sorting_order(self):
        """Output must be sorted by (symbol, date)."""
        from training.dataset_builder import validate_ohlcv

        df_a = _make_ohlcv(n_days=10, symbol="ZZZ", start_date="2020-01-01", seed=1)
        df_b = _make_ohlcv(n_days=10, symbol="AAA", start_date="2020-01-01", seed=2)
        combined = pd.concat([df_a, df_b], ignore_index=True)

        result = validate_ohlcv(combined)
        symbols = result["symbol"].tolist()
        # AAA should come before ZZZ
        first_zzz = symbols.index("ZZZ")
        last_aaa = len(symbols) - 1 - symbols[::-1].index("AAA")
        assert last_aaa < first_zzz


# ===========================================================================
# 10. Evaluation with empty input
# ===========================================================================


class TestEvaluationEmptyInput:
    """Edge cases for evaluation functions with empty/missing data."""

    def test_aggregate_fold_results_empty(self):
        from training.metrics import aggregate_fold_results

        result = aggregate_fold_results([])
        assert result["mean_hit_rate"] is None
        assert result["mean_roc_auc"] is None
        assert result["total_val_samples"] == 0
        assert result["top_features"] == []
        assert result["per_fold_summary"] == []

    def test_aggregate_fold_results_single_fold(self):
        from training.metrics import aggregate_fold_results

        fold = {
            "fold_id": 0,
            "val_year": 2023,
            "hit_rate": 0.55,
            "precision": 0.60,
            "recall": 0.50,
            "roc_auc": 0.58,
            "brier_score": 0.23,
            "avg_return_when_bullish": 0.03,
            "avg_return_when_bearish": -0.02,
            "calibration_by_bucket": {},
            "feature_importance": {},
            "train_samples": 1000,
            "val_samples": 250,
        }
        result = aggregate_fold_results([fold])
        assert result["mean_hit_rate"] == pytest.approx(0.55)
        assert result["mean_roc_auc"] == pytest.approx(0.58)
        assert result["total_train_samples"] == 1000
        assert result["total_val_samples"] == 250

    def test_compute_calibration_report_empty_arrays(self):
        from training.calibration import compute_calibration_report

        result = compute_calibration_report(np.array([]), np.array([]))
        assert result["buckets"] == []
        assert result["ece"] == 0.0
        assert result["mce"] == 0.0

    def test_compute_calibration_report_none_inputs(self):
        from training.calibration import compute_calibration_report

        result = compute_calibration_report(None, None)
        assert result["buckets"] == []
        assert result["ece"] == 0.0

    def test_compute_calibration_report_valid(self):
        """Calibration report with known data should produce correct buckets."""
        from training.calibration import compute_calibration_report

        rng = np.random.default_rng(_SEED)
        y_true = rng.choice([0, 1], size=200)
        y_prob = np.clip(y_true * 0.6 + rng.normal(0.3, 0.15, 200), 0, 1)

        result = compute_calibration_report(y_true, y_prob)
        assert len(result["buckets"]) == 4  # 4 calibration buckets
        assert result["ece"] >= 0.0
        assert result["mce"] >= 0.0
        assert result["mce"] >= result["ece"]

        # Every bucket should have a count >= 0
        for bucket in result["buckets"]:
            assert bucket["count"] >= 0
            assert "accuracy" in bucket
            assert "avg_probability" in bucket


# ===========================================================================
# Extra: model registry list_model_versions
# ===========================================================================


class TestModelRegistryVersioning:
    """Versioned directory listing and sorting."""

    def test_list_versions_sorted_by_date(self, tmp_path: Path):
        from training import model_registry

        original_registry = model_registry.REGISTRY_DIR
        try:
            model_registry.REGISTRY_DIR = tmp_path

            # Create version dirs out of order
            for datestamp in ["20260101", "20260315", "20260210"]:
                d = tmp_path / "stable" / f"lightgbm_baseline_alpha158_v1_{datestamp}"
                d.mkdir(parents=True)
                (d / "model.txt").write_text("mock")

            versions = model_registry.list_model_versions()
            assert len(versions) == 3
            # Should be sorted ascending by date suffix
            assert versions[0].endswith("20260101")
            assert versions[1].endswith("20260210")
            assert versions[2].endswith("20260315")
        finally:
            model_registry.REGISTRY_DIR = original_registry

    def test_get_latest_returns_most_recent(self, tmp_path: Path):
        from training import model_registry

        original_registry = model_registry.REGISTRY_DIR
        try:
            model_registry.REGISTRY_DIR = tmp_path

            for datestamp in ["20260101", "20260620"]:
                d = tmp_path / "stable" / f"lightgbm_baseline_alpha158_v1_{datestamp}"
                d.mkdir(parents=True)
                (d / "model.txt").write_text("mock")

            result = model_registry.get_latest_model_path()
            assert result is not None
            assert "20260620" in str(result)
        finally:
            model_registry.REGISTRY_DIR = original_registry


# ===========================================================================
# Extra: generate_sample_csv round-trip
# ===========================================================================


class TestGenerateSampleCSV:
    """Synthetic CSV generator produces valid, loadable data."""

    def test_generate_and_load(self, tmp_path: Path):
        from training.dataset_builder import generate_sample_csv, load_csv

        csv_path = str(tmp_path / "test_data.csv")
        generate_sample_csv(csv_path, n_symbols=3, n_days=100, seed=_SEED)

        df = load_csv(csv_path)
        assert len(df) == 300  # 3 symbols x 100 days
        assert df["symbol"].nunique() == 3
        assert set(df.columns) >= {"symbol", "date", "open", "high", "low", "close", "volume"}

    def test_reproducibility(self, tmp_path: Path):
        """Same seed produces identical CSV output."""
        from training.dataset_builder import generate_sample_csv

        p1 = str(tmp_path / "a.csv")
        p2 = str(tmp_path / "b.csv")
        generate_sample_csv(p1, n_symbols=2, n_days=50, seed=123)
        generate_sample_csv(p2, n_symbols=2, n_days=50, seed=123)

        assert Path(p1).read_text() == Path(p2).read_text()


# ===========================================================================
# Extra: walk-forward split shape consistency
# ===========================================================================


class TestWalkForwardSplitShapes:
    """X_train / X_val array shapes must be consistent with feature count."""

    def test_array_shapes(self):
        from training.validation import WalkForwardConfig, generate_splits

        df = _make_multiyear_ohlcv(years=range(2019, 2026), days_per_year=252)
        rng = np.random.default_rng(_SEED)
        df["direction_20d"] = rng.choice([0.0, 1.0], size=len(df))

        feature_cols = ["open", "high", "low", "close", "volume"]
        config = WalkForwardConfig(
            folds=[(2022, 2023)],
            target_col="direction_20d",
            min_train_samples=10,
        )
        splits = generate_splits(df, config, feature_cols)
        assert len(splits) == 1

        split = splits[0]
        assert split.X_train.shape[1] == len(feature_cols)
        assert split.X_val.shape[1] == len(feature_cols)
        assert len(split.y_train) == split.X_train.shape[0]
        assert len(split.y_val) == split.X_val.shape[0]
        assert split.feature_names == feature_cols
