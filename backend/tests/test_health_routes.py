"""REL-18: one handler per health path; readiness really checks the DB."""
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.routing import APIRoute

import routers.health as health
from main import app


@pytest.mark.parametrize("path", ["/health", "/health/ready", "/health/live", "/healthz"])
def test_single_handler_per_health_path(path):
    handlers = [r for r in app.routes
                if isinstance(r, APIRoute) and r.path == path and "GET" in r.methods]
    assert len(handlers) == 1


@pytest.mark.parametrize("path", ["/health", "/health/ready"])
def test_ready_200_when_db_up(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/health", "/health/ready"])
def test_ready_503_when_db_down(client, monkeypatch, path):
    def _down():
        raise RuntimeError("secret-dsn")

    monkeypatch.setattr(health, "get_session", _down)
    resp = client.get(path)
    assert resp.status_code == 503
    assert "secret-dsn" not in resp.text


def test_live_does_not_touch_db(client, monkeypatch):
    monkeypatch.setattr(health, "get_session", MagicMock(side_effect=RuntimeError("db down")))
    assert client.get("/health/live").status_code == 200


def test_healthz_requires_admin(client, auth_headers):
    assert client.get("/healthz").status_code == 401
    assert client.get("/healthz", headers=auth_headers).status_code == 403


def test_healthz_reports_config_without_yfinance(client, admin_headers, monkeypatch):
    yf = sys.modules.get("yfinance")
    if yf is not None:
        monkeypatch.setattr(yf, "Ticker", MagicMock(side_effect=AssertionError("no yfinance in /healthz")),
                            raising=False)
    monkeypatch.setattr(health, "_ml_engine_ok", lambda: False)
    monkeypatch.setattr(health, "_redis_ok", lambda: False)

    resp = client.get("/healthz", headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["db"] == "ok"
    assert body["config"]["jwt_secret_set"] is True
    assert "apns_configured" in body["config"]
    assert {"ml_engine", "redis"} <= set(body["degraded"])
