"""AUTH-21: prediction endpoints require the shared X-ML-Engine-Key secret when set."""
from __future__ import annotations

from pathlib import Path

import lightgbm  # noqa: F401  load in the main thread; first import in TestClient's portal thread segfaults on macOS
import pytest
from fastapi.testclient import TestClient

from main import app

_KEY = "unit-test-key"
_BODY = {"ticker": "X", "ohlcv_data": []}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("ML_ENGINE_API_KEY", _KEY)
    # No lifespan: auth runs before the handler, so model loading is irrelevant.
    return TestClient(app)


@pytest.mark.parametrize("headers", [{}, {"X-ML-Engine-Key": "wrong"}])
def test_predict_rejects_missing_or_wrong_key(client, headers) -> None:
    assert client.post("/predict/single", json=_BODY, headers=headers).status_code == 401


def test_model_status_rejects_missing_key(client) -> None:
    assert client.get("/model/status").status_code == 401


def test_correct_key_passes_auth(client) -> None:
    headers = {"X-ML-Engine-Key": _KEY}
    assert client.get("/model/status", headers=headers).status_code == 200
    assert client.post("/predict/single", json=_BODY, headers=headers).status_code != 401


def test_health_stays_open(client) -> None:
    assert client.get("/health").status_code == 200


def test_unset_key_keeps_dev_mode_open(monkeypatch) -> None:
    monkeypatch.delenv("ML_ENGINE_API_KEY", raising=False)
    assert TestClient(app).get("/model/status").status_code == 200


def test_deploy_script_passes_key_to_container() -> None:
    text = (Path(__file__).resolve().parents[2] / "scripts" / "deploy_ml_microservice.sh").read_text()
    assert "ML_ENGINE_API_KEY" in text
    assert "--env-file" in text
