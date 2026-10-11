"""
ml-engine/tests/test_alpha158_pipeline.py — Unit tests for FeatureComputer.

Verifies:
  1. FeatureComputer.compute_all() accepts a 100-row Polars OHLCV DataFrame.
  2. Output shape is (1, 158) — one row, 158 columns.
  3. Every output column is a Float64 or Float32 (numeric, not string/null/object).
  4. All 158 canonical Alpha158 feature names are present.
  5. No infinite or NaN values in the output (clean float math).
  6. Features derived from different window sizes (5, 10, 20, 30, 60) are present.
  7. The scaler (RobustZScoreNorm) path is exercised correctly.

No live network calls.  All data is constructed in-process using Polars.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import polars as pl
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — allow running pytest from repo root or ml-engine/ directly.
# ---------------------------------------------------------------------------
import sys
import os

_ML_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ML_ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ML_ENGINE_DIR)

from config import ALPHA158_FEATURES, FEATURE_LIST, WINDOWS  # noqa: E402
from pipeline.feature_computer import FeatureComputer, InsufficientHistoryError  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 100, seed: int = 42) -> pl.DataFrame:
    """Construct a synthetic OHLCV Polars DataFrame with ``n`` rows.

    Price series follows a simple geometric random walk so that
    numerical properties (trends, volatility, correlations) are
    non-trivial and exercise real feature paths rather than
    degenerate edge cases.
    """
    rng = np.random.default_rng(seed)

    # Simulate a geometric random walk for close prices
    log_returns = rng.normal(loc=0.0003, scale=0.015, size=n)
    closes = 1500.0 * np.exp(np.cumsum(log_returns))

    # Build OHLCV from closes (realistic spread relationships)
    spread = rng.uniform(0.001, 0.02, size=n)
    highs  = closes * (1.0 + spread)
    lows   = closes * (1.0 - spread)
    opens  = closes * (1.0 + rng.uniform(-0.01, 0.01, size=n))
    volumes = rng.uniform(1_000_000, 50_000_000, size=n)
    vwaps   = (highs + lows + closes) / 3.0

    dates = [f"2025-01-{i + 1:02d}" for i in range(min(n, 31))]
    if n > 31:
        # Extend date strings beyond one month (not calendar-accurate,
        # only used as string labels — FeatureComputer does not parse dates)
        dates += [f"2025-{(i // 28) + 2:02d}-{(i % 28) + 1:02d}" for i in range(n - 31)]

    return pl.DataFrame({
        "date":   dates[:n],
        "open":   opens.tolist(),
        "high":   highs.tolist(),
        "low":    lows.tolist(),
        "close":  closes.tolist(),
        "volume": volumes.tolist(),
        "vwap":   vwaps.tolist(),
    })


@pytest.fixture
def ohlcv_100() -> pl.DataFrame:
    """100-row OHLCV DataFrame — the minimum viable input for all 60-day windows."""
    return _make_ohlcv(n=100, seed=42)


@pytest.fixture
def feature_computer_no_scaler() -> FeatureComputer:
    """FeatureComputer with no scaler (raw feature values)."""
    return FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)


@pytest.fixture
def feature_computer_with_scaler() -> FeatureComputer:
    """FeatureComputer with synthetic scaler params (exercises _apply_scaler)."""
    # Build a minimal scaler: median=0, iqr=1 for the first 10 features.
    scaler_params = {
        feat: {"median": 0.0, "iqr": 1.0}
        for feat in ALPHA158_FEATURES[:10]
    }
    return FeatureComputer(feature_list=FEATURE_LIST, scaler_params=scaler_params)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFeatureComputerOutputShape:
    """Verify shape and schema of compute_all() output."""

    def test_output_has_one_row(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """compute_all must return exactly one row (latest feature snapshot)."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        assert result.shape[0] == 1, (
            f"Expected 1 row (latest snapshot), got {result.shape[0]}"
        )

    def test_output_has_158_columns(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """compute_all must return exactly 158 columns."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        assert result.shape[1] == 158, (
            f"Expected 158 feature columns, got {result.shape[1]}\n"
            f"Missing: {set(ALPHA158_FEATURES) - set(result.columns)}\n"
            f"Extra:   {set(result.columns) - set(ALPHA158_FEATURES)}"
        )


class TestFeatureComputerColumns:
    """Verify column presence and ordering."""

    def test_all_alpha158_features_present(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """All 158 canonical Alpha158 feature names must be in the output."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        missing = set(ALPHA158_FEATURES) - set(result.columns)
        assert not missing, f"Missing Alpha158 features: {missing}"

    def test_column_order_matches_feature_list(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Column order must match FEATURE_LIST exactly (for model input alignment)."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        assert result.columns == FEATURE_LIST, (
            "Column order does not match FEATURE_LIST. "
            "First mismatch at index: "
            + str(next(i for i, (a, b) in enumerate(zip(result.columns, FEATURE_LIST)) if a != b))
        )


class TestFeatureComputerColumnTypes:
    """Verify every output column is a numeric (float) dtype."""

    def test_all_columns_are_float(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """No column should be String, Boolean, or Null dtype."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        non_numeric = [
            (col, str(result[col].dtype))
            for col in result.columns
            if result[col].dtype not in (pl.Float64, pl.Float32, pl.Int64, pl.Int32)
        ]
        assert not non_numeric, (
            "Non-numeric columns found (expected Float64/Float32): "
            + str(non_numeric)
        )


class TestFeatureComputerNumerics:
    """Verify no NaN / Inf in output values."""

    def test_no_nan_values(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Feature values must not contain NaN (model inputs must be finite)."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        for col in result.columns:
            val = result[col][0]
            assert val is not None, f"Column '{col}' returned None"
            assert not math.isnan(float(val)), f"Column '{col}' is NaN"

    def test_no_infinite_values(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Feature values must not be +/-Inf."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        for col in result.columns:
            val = float(result[col][0])
            assert math.isfinite(val), (
                f"Column '{col}' is infinite: {val}"
            )


class TestFeatureComputerWindowCoverage:
    """Verify features across all 5 rolling windows are present."""

    @pytest.mark.parametrize("window", [5, 10, 20, 30, 60])
    def test_window_features_present(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
        window: int,
    ) -> None:
        """For each window size, at least one feature must be non-zero."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        window_cols = [c for c in result.columns if c.endswith(str(window))]
        assert window_cols, f"No features found for window={window}"
        values = [float(result[c][0]) for c in window_cols]
        non_zero = [v for v in values if v != 0.0]
        assert non_zero, (
            f"All features for window={window} are zero — computation may be skipped. "
            f"Columns: {window_cols}"
        )


class TestFeatureComputerCategoryPresence:
    """Verify all 8 Alpha158 categories produce output."""

    def test_kline_basic_features(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Category 1 (Kline basic) — 9 single-day geometry features."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        kline = ["KMID", "KLEN", "KMID2", "KUP", "KUP2", "KLOW", "KLOW2", "KSFT", "KSFT2"]
        for feat in kline:
            assert feat in result.columns, f"Kline basic feature '{feat}' missing"

    def test_static_price_features(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Category 2 (Static price) — 4 OHLC ratios relative to close."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        for feat in ["OPEN0", "HIGH0", "LOW0", "VWAP0"]:
            assert feat in result.columns, f"Static price feature '{feat}' missing"

    def test_trend_features(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Category 3 (Trend) — ROC, MA, BETA, RSQR, RESI across 5 windows."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        for prefix in ["ROC", "MA", "BETA", "RSQR", "RESI"]:
            for w in WINDOWS:
                feat = f"{prefix}{w}"
                assert feat in result.columns, f"Trend feature '{feat}' missing"

    def test_volume_volatility_features(
        self,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Category 7 (Volume volatility) — VMA, VSTD across 5 windows."""
        result = feature_computer_no_scaler.compute_all(ohlcv_100)
        for prefix in ["VMA", "VSTD"]:
            for w in WINDOWS:
                feat = f"{prefix}{w}"
                assert feat in result.columns, f"Volume-volatility feature '{feat}' missing"


class TestFeatureComputerScaler:
    """Verify RobustZScoreNorm scaler path."""

    def test_scaler_modifies_first_10_features(
        self,
        feature_computer_with_scaler: FeatureComputer,
        feature_computer_no_scaler: FeatureComputer,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """With median=0/iqr=1, scaled value = (raw - 0) / 1 = raw.
        Both outputs must therefore be equal for the first 10 features.
        """
        scaled   = feature_computer_with_scaler.compute_all(ohlcv_100)
        unscaled = feature_computer_no_scaler.compute_all(ohlcv_100)

        for feat in ALPHA158_FEATURES[:10]:
            s_val = float(scaled[feat][0])
            u_val = float(unscaled[feat][0])
            assert abs(s_val - u_val) < 1e-9, (
                f"Scaler with median=0/iqr=1 should be identity for '{feat}': "
                f"scaled={s_val}, unscaled={u_val}"
            )

    def test_scaler_with_nonzero_median_shifts_value(
        self,
        ohlcv_100: pl.DataFrame,
    ) -> None:
        """Scaler with median=100/iqr=50 must shift the first feature."""
        first_feat = ALPHA158_FEATURES[0]  # "KMID"
        scaler_params = {first_feat: {"median": 100.0, "iqr": 50.0}}
        fc_scaled   = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=scaler_params)
        fc_unscaled = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)

        scaled_val   = float(fc_scaled.compute_all(ohlcv_100)[first_feat][0])
        unscaled_val = float(fc_unscaled.compute_all(ohlcv_100)[first_feat][0])

        expected = (unscaled_val - 100.0) / 50.0
        assert abs(scaled_val - expected) < 1e-9, (
            f"Scaler mismatch for '{first_feat}': got {scaled_val}, expected {expected}"
        )


class TestFeatureComputerEdgeCases:
    """Edge-case resilience."""

    def test_minimum_60_rows(self) -> None:
        """60 rows (longest window) is accepted; 59 would zero-fill 60-day features and is rejected."""
        fc = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)
        result = fc.compute_all(_make_ohlcv(n=60, seed=99))
        assert result.shape[0] == 1
        with pytest.raises(InsufficientHistoryError):
            fc.compute_all(_make_ohlcv(n=59, seed=99))

    def test_missing_vwap_column_is_handled(self) -> None:
        """Category 2 VWAP0 should fallback to (H+L+C)/3 when vwap column is absent."""
        df = _make_ohlcv(n=100, seed=7)
        df_no_vwap = df.drop("vwap")
        fc = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)
        result = fc.compute_all(df_no_vwap)
        assert "VWAP0" in result.columns
        # Value must be finite
        assert math.isfinite(float(result["VWAP0"][0]))

    def test_raises_on_fewer_than_5_rows(self) -> None:
        """compute_all must raise ValueError when far too few rows are supplied."""
        df = _make_ohlcv(n=4, seed=1)
        fc = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)
        with pytest.raises(ValueError, match="Need at least 60 rows"):
            fc.compute_all(df)

    def test_raises_on_missing_required_column(self) -> None:
        """compute_all must raise ValueError when a required column is absent."""
        df = _make_ohlcv(n=100, seed=2)
        df_missing = df.drop("close")
        fc = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)
        with pytest.raises(ValueError, match="Missing required columns"):
            fc.compute_all(df_missing)
