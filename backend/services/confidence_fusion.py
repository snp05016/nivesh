"""
Deterministic Confidence Fusion Engine

Blends LLM-generated confidence, quantitative model outputs, statistical calibration
and ML predictions into a single 0-100 score.

This is a heuristic blend with hand-set weights, NOT a calibrated probability that
the call is right (ML-12). Static mode-aware weights are the default; calibration-
recommended weights are used only when FUSION_DYNAMIC_WEIGHTS_ENABLED is set and the
recommendation is confident on matured outcomes (ML-04).
"""

import os
import time
import logging
import threading

_LOG = logging.getLogger(__name__)


_NON_ML_BASE_WEIGHTS = {
    "llm": 0.45,
    "quant": 0.25,
    "venn_abers": 0.15,
    "signal_agreement": 0.10,
}

# Only a model that passed the ml-engine promotion gate (ml_client maps it to
# trained_live_calibrated) gets weight; unvalidated modes contribute nothing.
_ML_WEIGHTS_BY_MODE = {
    "fallback_technical_heuristic": 0.0,
    "unavailable": 0.0,
    "trained_lightgbm_baseline": 0.0,
    "trained_live_calibrated": 0.25,
}

STATIC_WEIGHTS_VERSION = "static-v1"
CONFIDENCE_KIND = "heuristic_blend_uncalibrated"
_PILLARS = ("llm", "quant", "venn_abers", "signal_agreement", "ml")
# Calibration-service column name for each fusion pillar.
_DYNAMIC_KEYS = {
    "llm": "llm_confidence",
    "quant": "quant_confidence",
    "venn_abers": "venn_abers_confidence",
    "signal_agreement": "signal_agreement",
    "ml": "ml_confidence",
}

_WEIGHTS_CACHE = None
_WEIGHTS_CACHE_TIME = 0.0
_CACHE_TTL = 3600  # 1 hour
_WEIGHTS_LOCK = threading.Lock()


def dynamic_weights_enabled() -> bool:
    """Manual opt-in for calibration-recommended fusion weights (off by default)."""
    return os.getenv("FUSION_DYNAMIC_WEIGHTS_ENABLED", "false").strip().lower() in ("1", "true", "yes")


def _get_dynamic_weights():
    """The applied calibration recommendation dict, or None for static weights.

    Flag off: returns None without touching the DB. A None result (recommendation
    not confident / not approved) is cached for the TTL too, not re-queried per call.
    """
    if not dynamic_weights_enabled():
        return None
    global _WEIGHTS_CACHE, _WEIGHTS_CACHE_TIME
    with _WEIGHTS_LOCK:
        now = time.time()
        if (now - _WEIGHTS_CACHE_TIME) > _CACHE_TTL:
            try:
                from services.prediction_calibration_service import get_fusion_weight_recommendations
                rec = get_fusion_weight_recommendations(min_sample=100)
                if rec.get("is_confident") and rec.get("apply_recommendation"):
                    _WEIGHTS_CACHE = rec
                    _LOG.info(
                        "Confidence fusion using dynamic weights %s: %s",
                        rec.get("weights_version"), rec.get("recommended_weights"),
                    )
                else:
                    _WEIGHTS_CACHE = None
            except Exception as e:
                _LOG.warning("Failed to fetch dynamic weights from calibration system: %s", e)
                _WEIGHTS_CACHE = None
            _WEIGHTS_CACHE_TIME = now
        return _WEIGHTS_CACHE


def _ml_weight_for_mode(ml_engine_mode: str | None) -> float:
    """Return the capped ML pillar weight for the active engine mode."""
    return _ML_WEIGHTS_BY_MODE.get(ml_engine_mode or "fallback_technical_heuristic", 0.0)


def _clamp01(value) -> float | None:
    return None if value is None else max(0.0, min(1.0, float(value)))


def _fuse_final_confidence(
    llm_conf: int | float | None,
    quant_conf: float | None,
    venn_abers_conf: float | None,
    signal_agreement: float | None,
    ml_conf: float | None,
    ml_engine_mode: str | None = None,
    final_direction: int | None = None,
    ml_direction: int | None = None,
) -> tuple[int, dict]:
    """
    Fuses multiple confidence sources into a single 0-100 score.

    Missing pillars (None) are excluded and the remaining weights renormalized.
    The ML pillar is direction-conditional: it counts as ml_conf when the ML call
    agrees with final_direction and as 1 - ml_conf when it disagrees; it is excluded
    when either direction is 0/None or the engine mode carries no weight.

    Returns:
        fused_int: Final confidence score scaled to 0-100 integer.
        breakdown: Dictionary detailing the inputs and calculation.
    """
    mode = ml_engine_mode or "fallback_technical_heuristic"
    ml_cap = _ml_weight_for_mode(mode)

    dynamic = _get_dynamic_weights()
    if dynamic:
        rec_weights = dynamic.get("recommended_weights") or {}
        base = {p: float(rec_weights.get(_DYNAMIC_KEYS[p], 0.0)) for p in _PILLARS}
        # An unvalidated or absent ML engine never gains weight from the recommendation.
        base["ml"] = min(base["ml"], ml_cap)
        weights_version = dynamic.get("weights_version") or "dynamic"
    else:
        non_ml_scale = (1.0 - ml_cap) / sum(_NON_ML_BASE_WEIGHTS.values())
        base = {p: w * non_ml_scale for p, w in _NON_ML_BASE_WEIGHTS.items()}
        base["ml"] = ml_cap
        weights_version = STATIC_WEIGHTS_VERSION

    n_ml = None
    c_ml = _clamp01(ml_conf)
    if c_ml is not None and base["ml"] > 0 and final_direction and ml_direction:
        n_ml = c_ml if (ml_direction > 0) == (final_direction > 0) else 1.0 - c_ml

    values = {
        "llm": _clamp01(float(llm_conf) / 100.0) if llm_conf is not None else None,
        "quant": _clamp01(quant_conf),
        "venn_abers": _clamp01(venn_abers_conf),
        "signal_agreement": _clamp01(signal_agreement),
        "ml": n_ml,
    }
    used = [p for p in _PILLARS if values[p] is not None and base[p] > 0]
    total = sum(base[p] for p in used)
    weights = {p: (base[p] / total if p in used else 0.0) for p in _PILLARS}

    if total > 0:
        fused = sum(weights[p] * values[p] for p in used)  # type: ignore[operator]
        fused_int = max(0, min(100, int(round(fused * 100.0))))
    else:
        fused_int = 50

    breakdown = {
        "llm_confidence": llm_conf,
        "quant_confidence": None if values["quant"] is None else round(values["quant"], 4),
        "venn_abers_confidence": None if values["venn_abers"] is None else round(values["venn_abers"], 4),
        "signal_agreement": None if values["signal_agreement"] is None else round(values["signal_agreement"], 4),
        "ml_confidence": None if n_ml is None else round(n_ml, 4),
        "ml_engine_mode": mode,
        "ml_weight_applied": round(weights["ml"], 4),
        "dynamic_weights_active": bool(dynamic),
        "weights_version": weights_version,
        "confidence_kind": CONFIDENCE_KIND,
        "pillars_used": used,
        "weights": {p: round(weights[p], 4) for p in _PILLARS},
        "formula": " + ".join(f"{weights[p]:.4f}*{p}" for p in used) or "no inputs",
    }
    if total <= 0:
        breakdown["no_inputs"] = True

    return fused_int, breakdown

def get_ml_engine_mode(ml_model_loaded: bool, reported_mode: str | None = None) -> str:
    """Return the canonical ML engine mode from service metadata."""
    if reported_mode in _ML_WEIGHTS_BY_MODE:
        return reported_mode
    return "trained_lightgbm_baseline" if ml_model_loaded else "fallback_technical_heuristic"
