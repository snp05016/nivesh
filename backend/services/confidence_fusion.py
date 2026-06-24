"""
Deterministic Confidence Fusion Engine

Fuses LLM-generated confidence, quantitative model outputs, statistical calibration, 
and ML predictions into a single, measurable confidence score.

Formula:
    Dynamic weights from prediction_calibration_service (if available & confident),
    else fallback to static mode-aware weights.
"""

import time
import logging

_LOG = logging.getLogger(__name__)


_NON_ML_BASE_WEIGHTS = {
    "llm": 0.45,
    "quant": 0.25,
    "venn_abers": 0.15,
    "signal_agreement": 0.10,
}

_ML_WEIGHTS_BY_MODE = {
    "fallback_technical_heuristic": 0.05,
    "unavailable": 0.00,
    "trained_lightgbm_baseline": 0.15,
    "trained_live_calibrated": 0.25,
}

_WEIGHTS_CACHE = None
_WEIGHTS_CACHE_TIME = 0.0
_CACHE_TTL = 3600  # 1 hour

def _get_dynamic_weights():
    global _WEIGHTS_CACHE, _WEIGHTS_CACHE_TIME
    now = time.time()
    if _WEIGHTS_CACHE is None or (now - _WEIGHTS_CACHE_TIME) > _CACHE_TTL:
        try:
            from services.prediction_calibration_service import get_fusion_weight_recommendations
            rec = get_fusion_weight_recommendations(min_sample=100)
            if rec.get("is_confident"):
                _WEIGHTS_CACHE = rec.get("recommended_weights")
                _LOG.info("Confidence fusion updated dynamic weights from calibration system: %s", _WEIGHTS_CACHE)
            else:
                _WEIGHTS_CACHE = None
        except Exception as e:
            _LOG.warning("Failed to fetch dynamic weights from calibration system: %s", e)
            _WEIGHTS_CACHE = None
        _WEIGHTS_CACHE_TIME = now
    return _WEIGHTS_CACHE


def _ml_weight_for_mode(ml_engine_mode: str | None) -> float:
    """Return the capped ML pillar weight for the active engine mode."""
    return _ML_WEIGHTS_BY_MODE.get(ml_engine_mode or "fallback_technical_heuristic", 0.05)


def _fuse_final_confidence(
    llm_conf: int | float | None,
    quant_conf: float | None,
    venn_abers_conf: float | None,
    signal_agreement: float | None,
    ml_conf: float | None,
    ml_engine_mode: str | None = None,
) -> tuple[int, dict]:
    """
    Fuses multiple confidence sources into a single 0-100 score.
    Returns:
        fused_int: Final confidence score scaled to 0-100 integer.
        breakdown: Dictionary detailing the inputs and calculation.
    """
    # 1. Normalize all inputs to [0, 1] range
    n_llm = float(llm_conf) / 100.0 if llm_conf is not None else 0.5
    n_quant = float(quant_conf) if quant_conf is not None else 0.5
    n_va = float(venn_abers_conf) if venn_abers_conf is not None else 0.5
    n_agree = float(signal_agreement) if signal_agreement is not None else 0.5
    n_ml = float(ml_conf) if ml_conf is not None else 0.0  # Default to 0 if ML not available
    
    # Bound check
    n_llm = max(0.0, min(1.0, n_llm))
    n_quant = max(0.0, min(1.0, n_quant))
    n_va = max(0.0, min(1.0, n_va))
    n_agree = max(0.0, min(1.0, n_agree))
    n_ml = max(0.0, min(1.0, n_ml))

    # 2. Apply weights. Prefer dynamic weights from calibration system if confident,
    # otherwise fallback to mode-aware static weights.
    dynamic = _get_dynamic_weights()
    if dynamic:
        w_llm = dynamic.get("llm_confidence", 0.45)
        w_quant = dynamic.get("quant_confidence", 0.25)
        w_va = dynamic.get("venn_abers_confidence", 0.15)
        w_agree = dynamic.get("signal_agreement", 0.10)
        w_ml = dynamic.get("ml_confidence", 0.05)
        total = w_llm + w_quant + w_va + w_agree + w_ml
        if total > 0:
            w_llm /= total
            w_quant /= total
            w_va /= total
            w_agree /= total
            w_ml /= total
    else:
        w_ml = _ml_weight_for_mode(ml_engine_mode)
        non_ml_total = sum(_NON_ML_BASE_WEIGHTS.values())
        non_ml_scale = (1.0 - w_ml) / non_ml_total
        w_llm = _NON_ML_BASE_WEIGHTS["llm"] * non_ml_scale
        w_quant = _NON_ML_BASE_WEIGHTS["quant"] * non_ml_scale
        w_va = _NON_ML_BASE_WEIGHTS["venn_abers"] * non_ml_scale
        w_agree = _NON_ML_BASE_WEIGHTS["signal_agreement"] * non_ml_scale

    fused = (
        (w_llm * n_llm) +
        (w_quant * n_quant) +
        (w_va * n_va) +
        (w_agree * n_agree) +
        (w_ml * n_ml)
    )
    
    # 3. Scale back to 0-100
    fused_int = int(round(fused * 100.0))
    fused_int = max(0, min(100, fused_int))
    
    breakdown = {
        "llm_confidence": llm_conf if llm_conf is not None else 50,
        "quant_confidence": round(n_quant, 4),
        "venn_abers_confidence": round(n_va, 4),
        "signal_agreement": round(n_agree, 4),
        "ml_confidence": round(n_ml, 4),
        "ml_engine_mode": ml_engine_mode or "fallback_technical_heuristic",
        "ml_weight_applied": round(w_ml, 4),
        "dynamic_weights_active": bool(dynamic),
        "weights": {
            "llm": round(w_llm, 4),
            "quant": round(w_quant, 4),
            "venn_abers": round(w_va, 4),
            "signal_agreement": round(w_agree, 4),
            "ml": round(w_ml, 4),
        },
        "formula": (
            f"{w_llm:.4f}*llm + {w_quant:.4f}*quant + "
            f"{w_va:.4f}*va + {w_agree:.4f}*agreement + {w_ml:.4f}*ml"
        ),
    }
    
    return fused_int, breakdown

def get_ml_engine_mode(ml_model_loaded: bool, reported_mode: str | None = None) -> str:
    """Return the canonical ML engine mode from service metadata."""
    if reported_mode in _ML_WEIGHTS_BY_MODE:
        return reported_mode
    return "trained_lightgbm_baseline" if ml_model_loaded else "fallback_technical_heuristic"
