"""
Deterministic Confidence Fusion Engine

Fuses LLM-generated confidence, quantitative model outputs, statistical calibration, 
and ML predictions into a single, measurable confidence score.

Formula:
    0.45 * LLM + 0.25 * Quant + 0.15 * VennAbers + 0.10 * SignalAgreement + 0.05 * ML
"""

def _fuse_final_confidence(
    llm_conf: int | float | None,
    quant_conf: float | None,
    venn_abers_conf: float | None,
    signal_agreement: float | None,
    ml_conf: float | None,
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

    # 2. Apply weights
    w_llm = 0.45
    w_quant = 0.25
    w_va = 0.15
    w_agree = 0.10
    w_ml = 0.05

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
        "formula": "0.45*llm + 0.25*quant + 0.15*va + 0.10*agreement + 0.05*ml",
    }
    
    return fused_int, breakdown

def get_ml_engine_mode(ml_model_loaded: bool) -> str:
    """Returns the mode string based on whether the LightGBM model is active."""
    return "lgbm_trained" if ml_model_loaded else "fallback_technical_heuristic"
