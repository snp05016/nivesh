import pytest
from unittest.mock import patch
import httpx

from services.qlib_engine.ml_client import predict_cross_section
from services.confidence_fusion import _fuse_final_confidence, _ml_weight_for_mode

import asyncio

def test_fallback_safety_on_connection_error():
    """Verify that if the ML microservice is down, it gracefully degrades."""
    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection Refused")):
            result = await predict_cross_section("RELIANCE", [])
            assert result is None  # Client swallows errors and returns None
    asyncio.run(run_test())

def test_confidence_fusion_weights():
    """Verify ML weights scale according to ml_engine_mode."""
    w_fallback = _ml_weight_for_mode("fallback_technical_heuristic")
    w_baseline = _ml_weight_for_mode("trained_lightgbm_baseline")
    w_calibrated = _ml_weight_for_mode("trained_live_calibrated")
    w_unavailable = _ml_weight_for_mode("unavailable")

    assert w_fallback == 0.05
    assert w_unavailable == 0.00
    assert w_baseline == 0.15
    assert w_calibrated == 0.25

def test_fused_confidence_incorporates_mode():
    """Verify the fusion equation applies the correct weights dynamically."""
    fused, breakdown = _fuse_final_confidence(
        llm_conf=80,
        quant_conf=0.7,
        venn_abers_conf=0.6,
        signal_agreement=0.5,
        ml_conf=0.9,
        ml_engine_mode="trained_lightgbm_baseline"
    )
    
    # ml weight should be 0.15 in breakdown
    assert breakdown["ml_engine_mode"] == "trained_lightgbm_baseline"
    assert breakdown["ml_weight_applied"] == 0.15
    assert breakdown["weights"]["ml"] == 0.15
