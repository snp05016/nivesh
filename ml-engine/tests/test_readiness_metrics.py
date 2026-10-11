"""ML-24: readiness distinct from liveness, and a rolling prediction-distribution monitor."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import lightgbm  # noqa: F401  load in the main thread; first import in TestClient's portal thread segfaults on macOS
import pytest
from fastapi.testclient import TestClient

import main
from main import app


def _rows(n: int) -> list[dict]:
    today = date.today()
    return [
        {
            "date": (today - timedelta(days=n - 1 - i)).isoformat(),
            "open": 100.0 + i * 0.1,
            "high": 102.0 + i * 0.1,
            "low": 98.0 + i * 0.1,
            "close": 101.0 + i * 0.1 + (i % 3),
            "volume": 1000.0 + 10 * (i % 7),
        }
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def _fresh_window(monkeypatch):
    monkeypatch.setattr(main, "_recent", main.deque(maxlen=500))
    monkeypatch.setattr(main, "_degenerate_flagged", False)


def test_ready_503_when_model_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "LIGHTGBM_MODEL_PATH", tmp_path / "missing_lgb_model.txt")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200  # liveness stays green
        resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_ready_200_with_real_model() -> None:
    with TestClient(app) as client:
        resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_constant_direction_flags_degenerate() -> None:
    with TestClient(app) as client:
        engine = main._inference_engine
        assert engine is not None
        real_predict = engine.predict

        def _always_up(*args, **kwargs):
            out = real_predict(*args, **kwargs)
            out["expected_direction"] = 1
            out["signal_state"] = "ok"  # a validated model that collapsed to one class
            return out

        with patch.object(engine, "predict", side_effect=_always_up):
            for _ in range(60):
                assert client.post("/predict/single", json={"ticker": "X", "ohlcv_data": _rows(80)}).status_code == 200
        stats = client.get("/model/status").json()["recent_predictions"]
    assert stats["n"] == 60
    assert stats["n_ok"] == 60
    assert stats["class_share"]["1"] == 1.0
    assert stats["degenerate"] is True
    assert stats["fallback_rate"] == 0.0


def test_unvalidated_no_edge_not_degenerate() -> None:
    """No MANIFEST gate: every call is no_edge direction 0 by design, not a collapse."""
    with TestClient(app) as client:
        assert main._model_validated is False
        for _ in range(60):
            resp = client.post("/predict/single", json={"ticker": "X", "ohlcv_data": _rows(80)})
            assert resp.status_code == 200
            assert resp.json()["signal_state"] == "no_edge"
        stats = client.get("/model/status").json()["recent_predictions"]
    assert stats["n"] == 60
    assert stats["n_ok"] == 0
    assert stats["no_edge_rate"] == 1.0
    assert stats["degenerate"] is False


def test_mixed_directions_not_degenerate() -> None:
    for i in range(60):
        main._recent.append((i % 3 - 1, False, "ok"))
    assert main._prediction_stats()["degenerate"] is False
