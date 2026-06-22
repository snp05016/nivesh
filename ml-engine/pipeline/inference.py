"""
InferenceEngine — runs predictions using the loaded model and returns
results in the quant_payload-compatible dict shape.

Supports three modes:
  lightgbm  — tabular: single-row Alpha158 features -> scalar score
  tra       — sequence: [seq_len, 158] -> scalar score via TRA PyTorch model
  ensemble  — weighted average of lightgbm + tra scores

Output contract (matches quant_payload keys from orchestrator.py:§1893):
  {
    "expected_direction": int (-1, 0, 1),
    "confidence_score": float (0-1),
    "raw_score": float (model output before thresholding),
    "features_used": list[str],
  }
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

_LOG = logging.getLogger(__name__)

# ── Direction thresholds ───────────────────────────────────────────────────────

# Raw model score is a future return prediction (e.g. 0.02 = +2%).
# These thresholds map it to discrete direction (-1, 0, 1).
# Values are aligned with the existing quant_engine regime detection.
DIRECTION_THRESHOLD = 0.005  # ±0.5% — below this = neutral


class InferenceEngine:
    """Run model inference and return structured predictions."""

    def __init__(
        self,
        lightgbm_model: Any = None,
        tra_model: Any = None,
        lgb_params: dict[str, Any] | None = None,
        regime_thresholds: dict[str, Any] | None = None,
        confidence_config: dict[str, Any] | None = None,
    ) -> None:
        self._lgb_model = lightgbm_model
        self._tra_model = tra_model
        self._lgb_params = lgb_params or {}
        self._regime = regime_thresholds or {}
        self._conf = confidence_config or {}

    def predict(
        self,
        features_df: Any,  # Polars DataFrame with shape [1, 158]
        ticker: str = "UNKNOWN",
        model_type: str = "lightgbm",
    ) -> dict[str, Any]:
        """Run prediction and return quant_payload-compatible dict.

        Args:
            features_df: Single-row DataFrame with 158 Alpha158 features.
            ticker: Stock ticker for logging.
            model_type: "lightgbm", "tra", or "ensemble".

        Returns:
            Dict with expected_direction, confidence_score, raw_score, features_used.
        """
        if model_type == "lightgbm":
            raw_score = self._predict_lgb(features_df)
        elif model_type == "tra":
            raw_score = self._predict_tra(features_df)
        elif model_type == "ensemble":
            raw_lgb = self._predict_lgb(features_df)
            raw_tra = self._predict_tra(features_df)
            # Ensemble: 60% LightGBM + 40% TRA
            raw_score = 0.6 * raw_lgb + 0.4 * raw_tra
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        direction = self._score_to_direction(raw_score)
        confidence = self._calibrate_confidence(raw_score, features_df)

        return {
            "expected_direction": direction,
            "confidence_score": confidence,
            "raw_score": round(float(raw_score), 6),
            "features_used": list(features_df.columns)[:20],
        }

    # ── Model-specific prediction ──────────────────────────────────────────

    def _predict_lgb(self, features_df: Any) -> float:
        """LightGBM prediction. Falls back to heuristic if model not loaded."""
        if self._lgb_model is None:
            return self._fallback_score(features_df)

        # Convert Polars to numpy
        if hasattr(features_df, "to_numpy"):
            X = features_df.to_numpy().astype(np.float64)
        else:
            X = np.array(features_df, dtype=np.float64)

        if X.ndim == 1:
            X = X.reshape(1, -1)

        preds = self._lgb_model.predict(X)
        return float(preds[0]) if len(preds) > 0 else 0.0

    def _predict_tra(self, features_df: Any) -> float:
        """TRA PyTorch sequence prediction. Falls back to heuristic if not loaded."""
        if self._tra_model is None:
            return self._fallback_score(features_df)

        import torch

        if hasattr(features_df, "to_numpy"):
            X = features_df.to_numpy().astype(np.float32)
        else:
            X = np.array(features_df, dtype=np.float32)

        # TRA expects [batch=1, seq_len=60, features=158]
        # If we only have 1 row, repeat it to pad to seq_len
        seq_len = 60
        if X.shape[0] < seq_len:
            padding = np.tile(X[0:1], (seq_len - X.shape[0], 1))
            X = np.vstack([padding, X])  # pad at start so latest is at end
        X = X[-seq_len:]  # take last seq_len rows

        tensor = torch.from_numpy(X).unsqueeze(0)  # [1, 60, 158]
        with torch.no_grad():
            # TRA model needs hist_errors — pass zeros for cold start
            hist_errors = torch.zeros(1, self._tra_model.num_states)
            output = self._tra_model(tensor, hist_errors)
        return float(output.item())

    def _fallback_score(self, features_df: Any) -> float:
        """Multi-factor heuristic combining momentum, mean-reversion, and volatility.

        Used when no trained model is available. Balances trend-following
        with overbought/oversold detection to avoid always-bullish bias.
        """
        def _get(col: str, default: float) -> float:
            if col not in col_list:
                return default
            val = features_df[col][0]
            return float(val) if val is not None else default

        columns = features_df.columns if hasattr(features_df, "columns") else []
        col_list = list(columns)

        # Alpha158 ROC = Ref(close, N) / close
        # ROC < 1 means price rose over N days (bullish momentum)
        # ROC > 1 means price fell over N days (bearish momentum)
        roc5 = _get("ROC5", 1.0)
        roc20 = _get("ROC20", 1.0)

        # Short-term momentum: how much price moved in 5 days
        short_mom = 1.0 - roc5   # positive = bullish
        # Medium-term momentum: how much price moved in 20 days
        med_mom = 1.0 - roc20    # positive = bullish

        # RSV: position within N-day range [0=bottom, 1=top]
        rsv5 = _get("RSV5", 0.5)
        rsv20 = _get("RSV20", 0.5)

        # Overbought/oversold: blend short and medium RSV for mean-reversion
        rsv_blend = 0.4 * rsv5 + 0.6 * rsv20
        overbought_penalty = max(0.0, (rsv_blend - 0.7) * 3.0)
        oversold_boost = max(0.0, (0.3 - rsv_blend) * 3.0)

        # Volatility: high STD relative to price = uncertain = dampen signal
        std5 = _get("STD5", 0.01)
        vol_dampening = 1.0 / (1.0 + std5 * 50.0)  # high vol -> lower confidence

        # Trend divergence: short-term vs medium-term disagreement
        # If short momentum and medium momentum disagree, reduce signal
        divergence = abs(short_mom - med_mom)
        agreement_mult = 1.0 / (1.0 + divergence * 10.0)

        # Composite: blend momentum with mean-reversion
        raw_momentum = 0.5 * short_mom + 0.5 * med_mom
        mean_reversion = oversold_boost - overbought_penalty

        score = (0.6 * raw_momentum + 0.4 * mean_reversion) * vol_dampening * agreement_mult

        return np.clip(score * 0.05, -0.05, 0.05)

    # ── Direction mapping ──────────────────────────────────────────────────

    @staticmethod
    def _score_to_direction(raw_score: float) -> int:
        """Map raw return prediction to discrete direction.

        Threshold of ±0.5% separates signal from noise.
        Matches the existing quant_engine confidence calibration.
        """
        if raw_score > DIRECTION_THRESHOLD:
            return 1
        elif raw_score < -DIRECTION_THRESHOLD:
            return -1
        return 0

    # ── Confidence calibration ─────────────────────────────────────────────

    def _calibrate_confidence(self, raw_score: float, features_df: Any) -> float:
        """Calibrate confidence score (0-1) from model output.

        Uses:
        1. Signal magnitude (larger |score| → higher confidence)
        2. Feature stability (lower recent volatility → higher confidence)
        3. Clamp to [min_confidence, max_confidence]
        """
        min_conf = self._conf.get("min_confidence", 0.05)
        max_conf = self._conf.get("max_confidence", 0.95)
        base_prob = self._conf.get("default_base_probability", 0.50)

        # 1. Signal-strength component
        sigmoid = 1.0 / (1.0 + np.exp(-abs(raw_score) * 100))  # scale raw score to [0.5, 1)
        signal_conf = base_prob + (sigmoid - 0.5) * 0.4  # maps to [0.5, 0.9]

        # 2. Feature stability: check RSI proximity to extremes
        #    RSI near 30 or 70 → stronger signal → boost confidence
        stability_mult = 1.0
        if hasattr(features_df, "columns"):
            cols = list(features_df.columns)
            rsi_proxies = [c for c in cols if c.startswith("RSV") and len(c) <= 6]
            if rsi_proxies:
                val = features_df[rsi_proxies[0]][0]
                recent_rsv = float(val) if val is not None else 0.5
                extremity = abs(recent_rsv - 0.5) * 2.0  # [0, 1]
                stability_mult = 1.0 + extremity * 0.15  # up to 15% boost

        confidence = signal_conf * stability_mult
        return round(max(min_conf, min(max_conf, confidence)), 4)
