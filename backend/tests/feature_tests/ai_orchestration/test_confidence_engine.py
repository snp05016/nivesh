import pytest
import pandas as pd

from backend.services.confidence_engine import (
    compute_signal_agreement, 
    apply_bear_asymmetry, 
    compute_final_confidence,
    compute_conformal_bounds
)

def test_compute_signal_agreement():
    reports = {
        "governance": "The signal is CAUTIOUSLY BULLISH.",
        "market": "The signal is BEARISH.",
        "fundamentals": "The signal is NEUTRAL.",
        "news": "The signal is BULLISH."
    }
    res = compute_signal_agreement(reports)
    assert res["total_voters"] == 4
    # "CAUTIOUSLY BULLISH" -> "BULLISH", "BULLISH" -> "BULLISH" => 2/4 BULLISH
    assert res["vote_counts"]["BULLISH"] == 2
    assert res["agreement_ratio"] == 0.5  # 2 out of 4

def test_compute_signal_agreement_empty():
    res = compute_signal_agreement({})
    assert res["total_voters"] == 0
    assert res["agreement_ratio"] == 0.0

def test_apply_bear_asymmetry():
    output = "Bull confidence: 60%. Bear confidence: 40%."
    res = apply_bear_asymmetry(output)
    
    assert res["bull_confidence"] == 0.60
    assert res["bear_confidence"] == 0.40
    # net_direction = (0.6 * 1.0 - 0.4 * 1.5) / 2.5 = 0.0
    assert res["net_direction"] == 0.0
    assert res["signal_override"] == "NEUTRAL"

def test_compute_final_confidence():
    res = compute_final_confidence(
        raw_llm_confidence=80,
        governance_score=35, # < 40 triggers cap
        signal_agreement_ratio=0.75,
        regime_multiplier=1.0,
        delivery_modifier=0.0,
        microstructure_modifier=0.0,
        rrg_modifier=0.0,
        minskyan_penalty=0.0,
        monsoon_modifier=0.0,
        cisi_modifier=0.0,
        auditor_boost=0.0,
        bear_asymmetry_adjustment=0.0,
        signal="BULLISH"
    )
    assert res["governance_cap_applied"] is True
    # The cap value is 40
    assert res["final_confidence_pct"] <= 40

def test_compute_final_confidence_no_cap():
    res = compute_final_confidence(
        raw_llm_confidence=80,
        governance_score=85, # > 40
        signal_agreement_ratio=1.0,
        regime_multiplier=1.0,
        delivery_modifier=0.05,
        microstructure_modifier=0.05,
        rrg_modifier=0.0,
        minskyan_penalty=0.0,
        monsoon_modifier=0.0,
        cisi_modifier=0.0,
        auditor_boost=0.0,
        bear_asymmetry_adjustment=0.1,
        signal="BULLISH"
    )
    assert res["governance_cap_applied"] is False
    assert res["final_confidence_pct"] > 80  # Thanks to positive modifiers

def test_compute_conformal_bounds_no_data():
    res = compute_conformal_bounds("RELIANCE", 100.0, None)
    assert "short_term_3m" in res
    assert res["short_term_3m"]["mid"] == 100.0
    assert res["short_term_3m"]["lower"] == 0.0
    assert res["short_term_3m"]["upper"] == 0.0

def test_compute_conformal_bounds_insufficient_data():
    # Provide a dataframe with < 63 rows (e.g. 5 rows)
    df = pd.DataFrame({"Close": [100.0] * 5})
    res = compute_conformal_bounds("RELIANCE", 100.0, df)
    assert res["short_term_3m"]["lower"] == 0.0
    assert res["short_term_3m"]["upper"] == 0.0
