"""ML-10: /predict/single payload caps, generic error details, loopback-only deploys."""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import lightgbm  # noqa: F401  load in the main thread; first import in TestClient's portal thread segfaults on macOS
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


def test_oversize_series_rejected() -> None:
    with TestClient(app) as client:
        resp = client.post("/predict/single", json={"ticker": "X", "ohlcv_data": _rows(501)})
    assert resp.status_code == 422


def test_oversize_ticker_rejected() -> None:
    with TestClient(app) as client:
        resp = client.post("/predict/single", json={"ticker": "X" * 33, "ohlcv_data": _rows(80)})
    assert resp.status_code == 422


def test_inference_error_detail_is_generic() -> None:
    with TestClient(app) as client:
        assert main._inference_engine is not None
        with patch.object(main._inference_engine, "predict", side_effect=RuntimeError("secret-path /x")):
            resp = client.post("/predict/single", json={"ticker": "X", "ohlcv_data": _rows(80)})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Inference failed"}
    assert "secret-path" not in resp.text


def test_feature_error_detail_is_generic() -> None:
    with TestClient(app) as client:
        assert main._feature_computer is not None
        with patch.object(main._feature_computer, "compute_all", side_effect=ValueError("boom-detail")):
            resp = client.post("/predict/single", json={"ticker": "X", "ohlcv_data": _rows(80)})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Feature computation failed"
    assert "boom-detail" not in resp.text


def test_predict_single_is_sync_so_it_runs_in_threadpool() -> None:
    import inspect

    assert not inspect.iscoroutinefunction(main.predict_single)


def test_deploy_scripts_publish_ml_port_on_loopback_only() -> None:
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    found = 0
    # deploy_ml_engine.sh delegates the docker run to deploy_ml_microservice.sh.
    for name in ("deploy_ml_engine.sh", "deploy_ml_microservice.sh"):
        text = (scripts / name).read_text()
        mappings = re.findall(r"""\s-p\s+['"]?([^'"\s]+)""", text)
        found += len(mappings)
        for m in mappings:
            assert m.startswith("127.0.0.1:"), f"{name} publishes {m} beyond loopback"
    assert found, "no docker -p mapping found in the deploy scripts"
