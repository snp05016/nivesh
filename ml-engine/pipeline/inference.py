"""
InferenceEngine — runs the loaded LightGBM booster and returns results in the
quant_payload-compatible dict shape.

The booster is a binary classifier (objective=binary): its output is P(up)
over the training horizon, not a return forecast. A direction is served only
for a model that passed the promotion gate (model_validated) with a known
training base rate and neutral band; every other case (unvalidated model,
no model, TRA/ensemble with no shipped TRA weights) returns signal_state
"no_edge" with direction 0 and confidence 0.0.

Output contract (matches quant_payload keys from orchestrator.py:§1893):
  {
    "expected_direction": int (-1, 0, 1),  # always 0 unless signal_state == "ok"
    "confidence_score": float (0-1),       # always 0.0 unless signal_state == "ok"
    "raw_score": float | None,             # booster P(up); None without a booster
    "p_up": float | None,
    "base_rate": float | None,             # training base rate of the up class
    "signal_state": "ok" | "no_edge",
    "features_used": list[str],
  }
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

_LOG = logging.getLogger(__name__)

_MODEL_TYPES = ("lightgbm", "tra", "ensemble")


class InferenceEngine:
    """Run model inference and return structured predictions."""

    def __init__(
        self,
        lightgbm_model: Any = None,
        tra_model: Any = None,
        lgb_params: dict[str, Any] | None = None,
        regime_thresholds: dict[str, Any] | None = None,
        confidence_config: dict[str, Any] | None = None,
        lgb_objective: str | None = None,
        model_validated: bool = False,
        base_rate: float | None = None,
        neutral_band: float | None = None,
    ) -> None:
        # predict() reads the booster output as P(up); a booster trained on any
        # other objective (e.g. a return regressor) would be silently misread.
        if lightgbm_model is not None and not (lgb_objective or "").startswith("binary"):
            raise ValueError(
                f"Unsupported LightGBM objective {lgb_objective!r}: the inference "
                "contract reads the booster output as P(up) from a binary classifier"
            )
        self._lgb_model = lightgbm_model
        self._tra_model = tra_model
        self._lgb_params = lgb_params or {}
        self._regime = regime_thresholds or {}
        self._conf = confidence_config or {}
        self._base_rate = None if base_rate is None else float(base_rate)
        self._neutral_band = None if neutral_band is None else float(neutral_band)
        self._validated = bool(model_validated) and lightgbm_model is not None
        if self._validated:
            if self._base_rate is None or self._neutral_band is None:
                raise ValueError("A validated model needs base_rate and neutral_band")
            if not (0.0 < self._base_rate < 1.0 and 0.0 <= self._neutral_band < 0.5):
                raise ValueError(
                    f"base_rate {self._base_rate} must be in (0, 1) and "
                    f"neutral_band {self._neutral_band} in [0, 0.5)"
                )

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
            Dict with expected_direction, confidence_score, raw_score, p_up,
            base_rate, signal_state and features_used.
        """
        if model_type not in _MODEL_TYPES:
            raise ValueError(f"Unknown model_type: {model_type}")

        # Only the LightGBM booster yields a probability. No TRA weights ship,
        # so tra/ensemble have no model output to serve.
        p_up = None
        if model_type == "lightgbm" and self._lgb_model is not None:
            p_up = self._predict_lgb(features_df)

        direction, confidence, signal_state = 0, 0.0, "no_edge"
        base, band = self._base_rate, self._neutral_band
        if p_up is not None and self._validated and base is not None and band is not None:
            edge = p_up - base
            if abs(edge) > band:
                direction = 1 if edge > 0 else -1
            # 0.5 at the base rate and rising with |edge|; equals the probability
            # of the called outcome when the base rate is 0.5.
            confidence = round(min(self._conf.get("max_confidence", 0.95), 0.5 + abs(edge)), 4)
            signal_state = "ok"

        p = None if p_up is None else round(p_up, 6)
        return {
            "expected_direction": direction,
            "confidence_score": confidence,
            "raw_score": p,
            "p_up": p,
            "base_rate": base,
            "signal_state": signal_state,
            "features_used": list(features_df.columns)[:20],
        }

    # ── Model-specific prediction ──────────────────────────────────────────

    def _predict_lgb(self, features_df: Any) -> float:
        """LightGBM prediction: the booster's P(up) for the single feature row."""
        # Convert Polars to numpy
        if hasattr(features_df, "to_numpy"):
            X = features_df.to_numpy().astype(np.float64)
        else:
            X = np.array(features_df, dtype=np.float64)

        if X.ndim == 1:
            X = X.reshape(1, -1)

        preds = self._lgb_model.predict(X)
        return float(preds[0])
