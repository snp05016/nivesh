import pytest
from fastapi.testclient import TestClient

from main import app

def test_model_status():
    """Verify the /model/status endpoint returns expected keys and LightGBM is loaded."""
    with TestClient(app) as client:
        response = client.get("/model/status")
        assert response.status_code == 200
        data = response.json()
        assert "lightgbm_loaded" in data
        assert "ml_engine_mode" in data
        assert "model_version" in data
        assert "supported_horizons" in data
        assert "feature_count" in data
    
    # Assuming the baseline model is loaded, verify these specific fields
    # If this runs in an environment where the model is not present, it gracefully falls back,
    # but for production verification, we assert it must be loaded.
    assert data["lightgbm_loaded"] is True
    assert data["ml_engine_mode"] == "trained_lightgbm_baseline"
    assert data["model_version"] is not None

def test_predict_single():
    """Verify /predict/single returns complete metadata along with prediction."""
    dummy_ohlcv = [
        {"open": 100, "high": 105, "low": 98, "close": 102, "volume": 1000}
        for _ in range(252) # Provide enough data to pass feature computation
    ]
    payload = {
        "ticker": "RELIANCE",
        "ohlcv": dummy_ohlcv
    }
    with TestClient(app) as client:
        response = client.post("/predict/single", json=payload)
        assert response.status_code == 200
        data = response.json()
    
        # Basic prediction fields
        assert "direction" in data
        assert "confidence" in data
        assert "ml_engine_mode" in data
        assert "lightgbm_loaded" in data
        assert "model_version" in data
        assert "horizon" in data
        assert "feature_count" in data
        assert "fallback_used" in data

        # Verify model is successfully utilized
        assert data["lightgbm_loaded"] is True
        assert data["ml_engine_mode"] == "trained_lightgbm_baseline"
        assert data["fallback_used"] is False
        assert data["model_version"] is not None
