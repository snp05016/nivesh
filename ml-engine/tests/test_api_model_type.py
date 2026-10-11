"""ML-26: only the LightGBM booster is served, so the response provenance flags
always describe the path that produced the score."""

# LightGBM's OpenMP runtime must load before torch's; see test_inference_semantics.
import lightgbm  # noqa: F401
import pytest
from fastapi.testclient import TestClient

from main import app

_OHLCV = [
    {"open": 100 + i * 0.1, "high": 101 + i * 0.1, "low": 99 + i * 0.1, "close": 100.5 + i * 0.1, "volume": 1000}
    for i in range(120)
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("model_type", ["tra", "ensemble"])
def test_unserved_model_type_is_rejected(client, model_type):
    r = client.post("/predict/single", json={"ticker": "RELIANCE", "ohlcv": _OHLCV, "model_type": model_type})
    assert r.status_code == 422


def test_default_request_reports_lightgbm_provenance_and_no_fake_attribution(client):
    r = client.post("/predict/single", json={"ticker": "RELIANCE", "ohlcv": _OHLCV})
    assert r.status_code == 200
    data = r.json()
    assert data["lightgbm_loaded"] is True
    assert data["fallback_used"] is False
    assert data["features"] == []


def test_cross_section_endpoint_is_gone(client):
    r = client.post("/predict/cross-section", json={"stocks": [_OHLCV]})
    assert r.status_code == 404


def test_model_status_has_no_tra_flag(client):
    r = client.get("/model/status")
    assert r.status_code == 200
    assert "tra_loaded" not in r.json()
