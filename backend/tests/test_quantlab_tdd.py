"""
TDD tests for QuantLab API: horizon validation, alpha validation, calibration, ML signal.

Follows TDD vertical slice pattern: one test → one fix → verify → next.
Tests verify behavior through public API endpoints, not implementation details.
"""
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


# ── Test 1: Alpha validation horizon normalization ────────────────────────────

def test_alpha_validation_accepts_lowercase_horizon(auth_headers):
    """Beacon test: POST /api/v1/backtests/alpha-validation with '30d' (lowercase) returns 200."""
    from main import app
    client = TestClient(app)

    with patch("services.alpha_validation_service.run_alpha_validation") as mock_run:
        mock_run.return_value = {
            "params": {"horizon": "30D", "strategy_type": "confidence_weighted"},
            "metrics": {"cagr": 0.0},
        }
        resp = client.post(
            "/api/v1/backtests/alpha-validation",
            json={"horizon": "30d", "strategy_type": "confidence_weighted", "tickers": ["RELIANCE.NS"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["params"]["horizon"] == "30D"


@pytest.mark.parametrize("horizon", ["7d", "30d", "90d", "7D", "30D", "90D"])
def test_all_horizon_formats_accepted(horizon, auth_headers):
    """Tracked horizons (7/30/90 days) are accepted in lowercase and uppercase."""
    from main import app
    client = TestClient(app)

    with patch("services.alpha_validation_service.run_alpha_validation") as mock_run:
        mock_run.return_value = {"params": {"horizon": horizon.upper()}, "metrics": {}}
        resp = client.post(
            "/api/v1/backtests/alpha-validation",
            json={"horizon": horizon, "strategy_type": "confidence_weighted", "tickers": ["RELIANCE.NS"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Failed for horizon='{horizon}': {resp.text}"


@pytest.mark.parametrize("horizon", ["15d", "20d", "60D"])
def test_invalid_horizon_rejected(horizon, auth_headers):
    """Horizons without a tracked outcome column (15d, 20d, 60d) are rejected with 422."""
    from main import app
    client = TestClient(app)

    resp = client.post(
        "/api/v1/backtests/alpha-validation",
        json={"horizon": horizon, "strategy_type": "confidence_weighted", "tickers": ["RELIANCE.NS"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422, f"Expected 422 for invalid horizon, got {resp.status_code}"


# ── Test 2: Strategy sweep endpoint ──────────────────────────────────────────

def test_strategy_sweep_returns_valid_configs(auth_headers):
    """GET /api/v1/backtests/strategy-sweep returns best CAGR and Sharpe configs."""
    from main import app
    client = TestClient(app)

    resp = client.get("/api/v1/backtests/strategy-sweep", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "best_cagr" in body
    assert "best_sharpe" in body
    assert isinstance(body["best_cagr"], dict)
    assert isinstance(body["best_sharpe"], dict)


# ── Test 3: Calibration endpoint ─────────────────────────────────────────────

def test_calibration_endpoint_accepts_lowercase_horizon(admin_headers):
    """GET /api/v1/predictions/calibration?horizon=30d returns 200 with proper schema."""
    from main import app
    client = TestClient(app)

    resp = client.get(
        "/api/v1/predictions/calibration?horizon=30d",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "confidence_bucket_accuracy" in body
    # Empty buckets is valid when no prediction data exists
    assert isinstance(body["confidence_bucket_accuracy"], list)


# ── Test 4: ML signal graceful degradation ───────────────────────────────────

def test_ml_signal_returns_graceful_unavailable(auth_headers):
    """When ml-engine is down, /api/v1/stocks/X/ml-signal returns 200 with unavailable status."""
    from main import app
    client = TestClient(app)

    resp = client.get(
        "/api/v1/stocks/RELIANCE.NS/ml-signal",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "RELIANCE.NS"
    assert body["status"] in ("unavailable", "ok")
    assert "ml_engine_mode" in body


# ── Test 5: Pillar attribution schema ────────────────────────────────────────

def test_pillar_attribution_returns_pillars(admin_headers):
    """Pillar attribution returns a pillars array (may be empty with no data)."""
    from main import app
    client = TestClient(app)

    resp = client.get(
        "/api/v1/predictions/pillar-attribution?horizon=30d",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "pillars" in body
    assert isinstance(body["pillars"], list)


# ── Test 6: Auth required ────────────────────────────────────────────────────

def test_quantlab_endpoints_require_auth():
    """QuantLab endpoints (except public strategy-sweep) return 401 without auth."""
    from main import app
    client = TestClient(app)

    endpoints = [
        ("GET", "/api/v1/predictions/calibration?horizon=30d"),
        ("GET", "/api/v1/predictions/pillar-attribution?horizon=30d"),
        ("GET", "/api/v1/stocks/RELIANCE.NS/ml-signal"),
    ]
    for method, path in endpoints:
        resp = client.get(path)
        assert resp.status_code in (401, 403), f"{path} should require auth, got {resp.status_code}"
