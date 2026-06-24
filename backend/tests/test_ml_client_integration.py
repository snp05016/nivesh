import pytest
import asyncio
from unittest.mock import patch, MagicMock

from services.qlib_engine.ml_client import predict_cross_section

def test_ml_client_preserves_metadata():
    """Verify ml_client successfully maps all LightGBM production metadata fields without collapsing."""
    async def run_test():
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "direction": 1,
            "confidence": 0.82,
            "ml_engine_mode": "trained_lightgbm_baseline",
            "model_version": "lightgbm_baseline_alpha158_v1_20260624",
            "lightgbm_loaded": True,
            "horizon": 20,
            "feature_count": 166,
            "fallback_used": False
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            result = await predict_cross_section("RELIANCE", [{"open": 100, "high": 105, "low": 98, "close": 102, "volume": 1000}])
            
            assert result is not None
            assert result["direction"] == 1
            assert result["confidence"] == 0.82
            assert result["ml_engine_mode"] == "trained_lightgbm_baseline"
            assert result["model_version"] == "lightgbm_baseline_alpha158_v1_20260624"
            assert result["lightgbm_loaded"] is True
            assert result["horizon"] == 20
            assert result["feature_count"] == 166
            assert result["fallback_used"] is False

    asyncio.run(run_test())
