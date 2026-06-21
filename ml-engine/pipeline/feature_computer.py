"""
FeatureComputer — computes all 158 Alpha158 factors from raw OHLCV data.

Input:  Polars DataFrame with columns [date, open, high, low, close, volume, vwap]
Output: Polars DataFrame with 158 Alpha158 feature columns, scaled and ready for inference.

Category breakdown (from config.py):
  Category 1  — Kline basic (9):      KMID, KLEN, KMID2, KUP, KUP2, KLOW, KLOW2, KSFT, KSFT2
  Category 2  — Static price (4):     OPEN0, HIGH0, LOW0, VWAP0
  Category 3  — Trend (25):           ROC, MA, BETA, RSQR, RESI × [5,10,20,30,60]
  Category 4  — Volatility (30):      STD, MAX, MIN, QTLU, QTLD, RSV × [5,10,20,30,60]
  Category 5  — Extreme position (15): IMAX, IMIN, IMXD × [5,10,20,30,60]
  Category 6  — Price-volume stat (45): CORR, CORD, CNTP, CNTN, CNTD, SUMP, SUMN, SUMD, RANK × [5,10,20,30,60]
  Category 7  — Volume volatility (10): VMA, VSTD × [5,10,20,30,60]
  Category 8  — Price-vol weighted (20): WVMA, VSUMP, VSUMN, VSUMD × [5,10,20,30,60]

All math follows the original Alpha158 specification from Microsoft Qlib.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import polars as pl

_LOG = logging.getLogger(__name__)


class FeatureComputer:
    """Compute Alpha158 features and apply RobustZScoreNorm scaling."""

    def __init__(
        self,
        feature_list: list[str],
        scaler_params: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.feature_list = feature_list
        self.scaler_params = scaler_params or {}
        self._n_features = len(feature_list)

    # ── Public API ─────────────────────────────────────────────────────────

    def compute_all(self, df: pl.DataFrame) -> pl.DataFrame:
        """Compute all 158 Alpha158 features from raw OHLCV data.

        Args:
            df: Polars DataFrame with [date, open, high, low, close, volume, vwap]

        Returns:
            DataFrame with shape [1, 158] (single row = latest feature snapshot).
            Row 0 is the most recent date's features, suitable for model inference.
        """
        self._validate_input(df)

        features: dict[str, float] = {}

        # Category 1: Kline basic
        features.update(self._compute_kline_basic(df))

        # Category 2: Static price ratios
        features.update(self._compute_static_price(df))

        # Categories 3-8: Windowed factors
        features.update(self._compute_windowed(df))

        # Assemble into a single-row DataFrame with ordered columns
        result = pl.DataFrame(
            [features],
            schema=self.feature_list,
        )

        # Apply RobustZScoreNorm if scaler is available
        if self.scaler_params:
            result = self._apply_scaler(result)

        return result

    # ── Input Validation ───────────────────────────────────────────────────

    @staticmethod
    def _validate_input(df: pl.DataFrame) -> None:
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                f"Input must have: open, high, low, close, volume, vwap, date"
            )
        if len(df) < 5:
            raise ValueError("Need at least 5 rows of OHLCV data")

    # ── Category 1: Kline Basic (9 factors, single-day geometry) ───────────

    @staticmethod
    def _compute_kline_basic(df: pl.DataFrame) -> dict[str, float]:
        """Compute 9 candlestick geometry factors from the latest row."""
        row = df[-1]  # latest row
        o, h, l, c = (
            float(row["open"][0]),
            float(row["high"][0]),
            float(row["low"][0]),
            float(row["close"][0]),
        )

        denom_o = o if o != 0 else 1.0
        denom_hl = (h - l) if (h - l) != 0 else 1.0

        return {
            "KMID": (c - o) / denom_o,
            "KLEN": (h - l) / denom_o,
            "KMID2": (c - o) / denom_hl,
            "KUP": (h - max(o, c)) / denom_o,
            "KUP2": (h - max(o, c)) / denom_hl,
            "KLOW": (min(o, c) - l) / denom_o,
            "KLOW2": (min(o, c) - l) / denom_hl,
            "KSFT": (2 * c - h - l) / denom_o,
            "KSFT2": (2 * c - h - l) / denom_hl,
        }

    # ── Category 2: Static Price (4 factors) ───────────────────────────────

    @staticmethod
    def _compute_static_price(df: pl.DataFrame) -> dict[str, float]:
        """Compute OHLC ratios relative to latest close."""
        row = df[-1]
        c = float(row["close"][0])
        c_safe = c if c != 0 else 1.0
        o, h, l = float(row["open"][0]), float(row["high"][0]), float(row["low"][0])
        vwap_val = (
            float(row["vwap"][0])
            if "vwap" in df.columns and row["vwap"][0] is not None
            else (h + l + c) / 3.0
        )
        return {
            "OPEN0": o / c_safe,
            "HIGH0": h / c_safe,
            "LOW0": l / c_safe,
            "VWAP0": vwap_val / c_safe,
        }

    # ── Categories 3-8: Windowed Factors ───────────────────────────────────

    def _compute_windowed(self, df: pl.DataFrame) -> dict[str, float]:
        """Compute all 145 windowed Alpha158 factors.

        Uses 5 rolling windows: [5, 10, 20, 30, 60] days.
        """
        # Convert to numpy for efficient rolling-window math
        closes = df["close"].to_numpy().astype(np.float64)
        opens = df["open"].to_numpy().astype(np.float64)
        highs = df["high"].to_numpy().astype(np.float64)
        lows = df["low"].to_numpy().astype(np.float64)
        volumes = df["volume"].to_numpy().astype(np.float64)

        features: dict[str, float] = {}
        windows = [5, 10, 20, 30, 60]

        for n in windows:
            if len(closes) < n:
                continue  # skip windows larger than available data

            c = closes[-1]
            c_safe = c if c != 0 else 1.0
            window_closes = closes[-n:]
            window_highs = highs[-n:]
            window_lows = lows[-n:]
            window_volumes = volumes[-n:]

            # ── Category 3: Trend (25 factors) ─────────────────────────────
            features[f"ROC{n}"] = window_closes[0] / c_safe
            features[f"MA{n}"] = float(np.mean(window_closes)) / c_safe
            features[f"BETA{n}"] = self._slope(window_closes) / c_safe
            features[f"RSQR{n}"] = self._rsquared(window_closes)
            features[f"RESI{n}"] = self._resi(window_closes) / c_safe

            # ── Category 4: Volatility (30 factors) ────────────────────────
            features[f"STD{n}"] = float(np.std(window_closes)) / c_safe
            features[f"MAX{n}"] = float(np.max(window_highs)) / c_safe
            features[f"MIN{n}"] = float(np.min(window_lows)) / c_safe
            features[f"QTLU{n}"] = float(np.quantile(window_closes, 0.8)) / c_safe
            features[f"QTLD{n}"] = float(np.quantile(window_closes, 0.2)) / c_safe
            hl_range = float(np.max(window_highs) - np.min(window_lows))
            features[f"RSV{n}"] = (c - float(np.min(window_lows))) / hl_range if hl_range != 0 else 0.5

            # ── Category 5: Extreme position (15 factors) ──────────────────
            features[f"IMAX{n}"] = float(np.argmax(window_highs)) / n
            features[f"IMIN{n}"] = float(np.argmin(window_lows)) / n
            features[f"IMXD{n}"] = (float(np.argmax(window_highs)) - float(np.argmin(window_lows))) / n

            # ── Category 6: Price-volume statistical (45 factors) ──────────
            ret_1d = np.diff(window_closes) / window_closes[:-1]
            vol_change = np.diff(window_volumes)
            log_vol = np.log(window_volumes + 1)
            features[f"CORR{n}"] = self._corr(window_closes, log_vol)
            if len(ret_1d) >= 2 and len(vol_change) >= 2:
                log_vol_change = np.log(np.abs(vol_change) + 1)
                features[f"CORD{n}"] = self._corr(ret_1d, log_vol_change)
            else:
                features[f"CORD{n}"] = 0.0
            up_days = (ret_1d > 0).astype(float)
            dn_days = (ret_1d < 0).astype(float)
            features[f"CNTP{n}"] = float(np.mean(up_days))
            features[f"CNTN{n}"] = float(np.mean(dn_days))
            features[f"CNTD{n}"] = features[f"CNTP{n}"] - features[f"CNTN{n}"]
            abs_ret = np.abs(ret_1d)
            total_abs = float(np.sum(abs_ret))
            if total_abs > 0:
                pos_part = np.maximum(ret_1d, 0)
                neg_part = np.maximum(-ret_1d, 0)
                features[f"SUMP{n}"] = float(np.sum(pos_part)) / total_abs
                features[f"SUMN{n}"] = float(np.sum(neg_part)) / total_abs
            else:
                features[f"SUMP{n}"] = 0.5
                features[f"SUMN{n}"] = 0.5
            features[f"SUMD{n}"] = features[f"SUMP{n}"] - features[f"SUMN{n}"]
            features[f"RANK{n}"] = float(np.searchsorted(np.sort(window_closes), c)) / n

            # ── Category 7: Volume volatility (10 factors) ─────────────────
            v_last = window_volumes[-1]
            v_last_safe = v_last if v_last != 0 else 1.0
            features[f"VMA{n}"] = float(np.mean(window_volumes)) / v_last_safe
            features[f"VSTD{n}"] = float(np.std(window_volumes)) / v_last_safe

            # ── Category 8: Price-volume weighted (20 factors) ─────────────
            ret_mag = np.abs(ret_1d)
            weighted = ret_mag * window_volumes[1:] if len(window_volumes) > 1 else np.array([0.0])
            w_mean = float(np.mean(weighted)) if len(weighted) > 0 else 1.0
            w_std = float(np.std(weighted)) if len(weighted) > 0 else 0.0
            features[f"WVMA{n}"] = w_std / w_mean if w_mean != 0 else 0.0
            vol_diff = np.diff(window_volumes)
            abs_vol_diff = np.abs(vol_diff)
            total_vol_diff = float(np.sum(abs_vol_diff))
            if total_vol_diff > 0:
                features[f"VSUMP{n}"] = float(np.sum(np.maximum(vol_diff, 0))) / total_vol_diff
                features[f"VSUMN{n}"] = float(np.sum(np.maximum(-vol_diff, 0))) / total_vol_diff
            else:
                features[f"VSUMP{n}"] = 0.5
                features[f"VSUMN{n}"] = 0.5
            features[f"VSUMD{n}"] = features[f"VSUMP{n}"] - features[f"VSUMN{n}"]

        return features

    # ── Math Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _slope(y: np.ndarray) -> float:
        """Linear regression slope of y on x = [0, 1, ..., n-1]."""
        n = len(y)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=np.float64)
        x_mean = x.mean()
        y_mean = y.mean()
        num = ((x - x_mean) * (y - y_mean)).sum()
        denom = ((x - x_mean) ** 2).sum()
        return float(num / denom) if denom != 0 else 0.0

    @staticmethod
    def _rsquared(y: np.ndarray) -> float:
        """R-squared of linear regression of y on index."""
        n = len(y)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=np.float64)
        slope = FeatureComputer._slope(y)
        intercept = y.mean() - slope * x.mean()
        y_pred = slope * x + intercept
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    @staticmethod
    def _resi(y: np.ndarray) -> float:
        """Residual (actual - predicted) from linear regression for the last point."""
        n = len(y)
        if n < 2:
            return 0.0
        x = np.arange(n, dtype=np.float64)
        slope = FeatureComputer._slope(y)
        intercept = y.mean() - slope * x.mean()
        return float(y[-1] - (slope * x[-1] + intercept))

    @staticmethod
    def _corr(a: np.ndarray, b: np.ndarray) -> float:
        """Pearson correlation between two arrays."""
        if len(a) < 2 or len(b) < 2:
            return 0.0
        a_std = a.std()
        b_std = b.std()
        if a_std == 0 or b_std == 0:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])

    # ── Scaling ────────────────────────────────────────────────────────────

    def _apply_scaler(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply RobustZScoreNorm: (value - median) / IQR.

        If a feature is missing from the scaler params, passes through unscaled.
        """
        for col in df.columns:
            if col in self.scaler_params:
                median = self.scaler_params[col].get("median", 0.0)
                iqr = self.scaler_params[col].get("iqr", 1.0)
                iqr_safe = iqr if iqr != 0 else 1.0
                df = df.with_columns(
                    ((pl.col(col) - median) / iqr_safe).alias(col)
                )
        return df
