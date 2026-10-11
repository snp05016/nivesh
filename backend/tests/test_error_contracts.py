"""REL-17 — error contracts: DataHarvestingError maps to 503, deliberate 502/503/504
details pass through, and failures are non-2xx or flagged `degraded` without leaking
exception text."""
import asyncio
import json
import sys
from unittest.mock import MagicMock

from fastapi import HTTPException
from starlette.requests import Request

import helpers
import main
import routers.analysis as analysis_router
import routers.market as market_router
import routers.user as user_router


def _boom(*_args, **_kwargs):
    raise RuntimeError("boom /secret-path")


def test_single_data_harvesting_error_class():
    assert main.DataHarvestingError is helpers.DataHarvestingError


def test_data_harvesting_error_returns_503(client, monkeypatch):
    monkeypatch.setattr(market_router, "fetch_earnings_sync_ratio", _boom)
    resp = client.get("/api/v1/earnings/sync-ratio")
    assert resp.status_code == 503
    assert "boom" not in resp.text
    assert "secret-path" not in resp.text


def _call_http_handler(exc: HTTPException) -> dict:
    req = Request(scope={"type": "http", "method": "GET", "path": "/x", "headers": [], "query_string": b""})
    resp = asyncio.run(main._http_exception_handler(req, exc))
    return {"status": resp.status_code, "body": json.loads(bytes(resp.body))}


def test_http_exception_handler_passthrough():
    out = _call_http_handler(HTTPException(status_code=503, detail="retry later"))
    assert out == {"status": 503, "body": {"detail": "retry later"}}

    masked = _call_http_handler(HTTPException(status_code=500, detail="db creds"))
    assert masked["status"] == 500
    assert "db creds" not in masked["body"]["detail"]


def test_option_chain_unavailable_503(client, monkeypatch):
    monkeypatch.setattr(sys.modules["services.options_scraper"], "fetch_option_chain", MagicMock(return_value=None))
    resp = client.get("/api/v1/options/chain/TCS")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Option chain temporarily unavailable from NSE"


def test_earnings_calendar_failure_degraded_no_leak(client, monkeypatch):
    monkeypatch.setattr(market_router, "get_session", _boom)
    resp = client.get("/api/v1/earnings/calendar", params={"date": "2026-01-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["results"] == []
    assert "secret-path" not in resp.text


def test_earnings_progress_unavailable_503(client):
    # FAKE-08: no honest results-filing source, so the endpoint never invents progress.
    resp = client.get("/api/v1/earnings/progress")
    assert resp.status_code == 503


def test_notifications_test_failure_503(client, monkeypatch):
    monkeypatch.setattr(user_router.user_service, "test_notification", _boom)
    resp = client.post("/notifications/test", json={"user_id": 1, "ticker": "TCS", "exchange": "NSE"})
    assert resp.status_code == 503
    assert "secret-path" not in resp.text


def test_screener_failure_503(client, monkeypatch):
    failures = MagicMock()
    monkeypatch.setattr(analysis_router, "_yf_circuit_is_open", lambda: False)
    monkeypatch.setattr(analysis_router, "_yf_circuit_record_failure", failures)
    # A DB failure inside a preset must surface as 503, never as an empty "no matches" list.
    monkeypatch.setattr(analysis_router, "get_session", _boom)
    resp = client.get("/screener", params={"preset": "52w_low_bullish"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Screener temporarily unavailable"
    failures.assert_called_once()
