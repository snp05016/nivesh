import asyncio

import pytest


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "signal_state": "ok",
            "p_up": 0.81,
            "direction": 1,
            "expected_direction": 1,
            "confidence": 0.73,
            "confidence_score": 0.73,
            "ml_engine_mode": "trained_lightgbm_baseline",
            "lightgbm_loaded": True,
            "model_version": "lightgbm_baseline_alpha158_v1_20260624",
            "horizon": 20,
            "feature_count": 158,
            "fallback_used": False,
        }


class _FakeAsyncClient:
    last_headers = None

    def __init__(self, *_, **__):
        self.payload = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, _url, json, headers=None):
        self.payload = json
        _FakeAsyncClient.last_headers = headers
        return _FakeResponse()


def test_ml_client_preserves_trained_model_metadata(monkeypatch):
    from services.qlib_engine import ml_client

    monkeypatch.setattr(ml_client.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        ml_client.predict_cross_section(
            "RELIANCE",
            [{"open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}],
        )
    )

    assert result == {
        "direction": 1,
        "confidence": 0.73,
        "ml_engine_mode": "trained_lightgbm_baseline",
        "model_version": "lightgbm_baseline_alpha158_v1_20260624",
        "lightgbm_loaded": True,
        "horizon": 20,
        "feature_count": 158,
        "fallback_used": False,
        "p_up": 0.81,
    }


@pytest.mark.parametrize(("key", "expected"), [("k-123", {"X-ML-Engine-Key": "k-123"}), (None, {})])
def test_ml_client_sends_engine_key_only_when_configured(monkeypatch, key, expected):
    """AUTH-21: ml-engine rejects calls without the shared secret once it is set."""
    from services.qlib_engine import ml_client

    if key is None:
        monkeypatch.delenv("ML_ENGINE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ML_ENGINE_API_KEY", key)
    monkeypatch.setattr(ml_client.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_headers = None

    asyncio.run(ml_client.predict_cross_section("RELIANCE", [{"open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}]))

    assert _FakeAsyncClient.last_headers == expected


@pytest.mark.parametrize(
    ("mode", "expected_weight"),
    [
        ("fallback_technical_heuristic", 0.05),
        ("trained_lightgbm_baseline", 0.15),
        ("trained_live_calibrated", 0.25),
        ("unavailable", 0.0),
    ],
)
def test_confidence_fusion_caps_ml_weight_by_engine_mode(mode, expected_weight):
    from services.confidence_fusion import _fuse_final_confidence

    _, breakdown = _fuse_final_confidence(
        llm_conf=70,
        quant_conf=0.65,
        venn_abers_conf=0.60,
        signal_agreement=0.75,
        ml_conf=0.80,
        ml_engine_mode=mode,
    )

    assert breakdown["ml_engine_mode"] == mode
    assert breakdown["ml_weight_applied"] == pytest.approx(expected_weight)
    assert breakdown["weights"]["ml"] == pytest.approx(expected_weight)
    assert sum(breakdown["weights"].values()) == pytest.approx(1.0, abs=0.001)


def test_analysis_prediction_stores_trained_model_provenance():
    from models.db_models import AnalysisPrediction

    pred = AnalysisPrediction(
        symbol="RELIANCE",
        recommendation="BULLISH",
        confidence_pct=78,
        llm_confidence=75,
        quant_confidence=0.64,
        ml_confidence=0.81,
        venn_abers_confidence=0.69,
        signal_agreement=0.8,
        ml_engine_mode="trained_lightgbm_baseline",
        model_version="lightgbm_baseline_alpha158_v1_20260624",
        horizon_days=20,
        entry_price=2850.0,
    )

    assert pred.ml_confidence == 0.81
    assert pred.ml_engine_mode == "trained_lightgbm_baseline"
    assert pred.model_version == "lightgbm_baseline_alpha158_v1_20260624"
    assert pred.horizon_days == 20
    assert pred.confidence_pct == 78
    assert pred.recommendation == "BULLISH"
    assert pred.entry_price == 2850.0
