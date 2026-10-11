"""AUTH-11: the limiter keys on method + exact route and evicts idle windows.

The conftest fixture clears the store around every test.
"""
import types
import uuid

import pytest
from fastapi import HTTPException

from core import rate_limiter
from core.rate_limiter import _check_rate_limit, _rate_limit_store


def _allow(client_id, path, method, n):
    for _ in range(n):
        assert _check_rate_limit(client_id, path, method) is True


def test_job_polling_is_not_on_the_job_start_budget():
    # The app polls these every 2-3 s; the old "/analyze" prefix gave them 10 per hour.
    _allow("ip", f"/analyze/job/{uuid.uuid4()}", "GET", 30)
    _allow("ip", "/analyze/active", "GET", 30)
    _allow("ip", "/analyze/cache-status/RELIANCE", "GET", 30)


def test_eleventh_analyze_start_in_an_hour_is_429():
    _allow("ip", "/analyze", "POST", 10)
    with pytest.raises(HTTPException) as exc:
        _check_rate_limit("ip", "/analyze", "POST")
    assert exc.value.status_code == 429
    assert exc.value.headers is not None and int(exc.value.headers["Retry-After"]) > 0


@pytest.mark.parametrize("path, limit", [("/login", 5), ("/register", 10), ("/quick-info", 60)])
def test_real_routes_get_their_own_limits(path, limit):
    method = "GET" if path == "/quick-info" else "POST"
    _allow("ip", path, method, limit)
    with pytest.raises(HTTPException):
        _check_rate_limit("ip", path, method)
    # Another method on the same path is not counted against the rule.
    assert _check_rate_limit("ip", path, "OPTIONS") is True


def test_middleware_does_not_throttle_job_polling(client):
    statuses = {client.get("/analyze/active").status_code for _ in range(15)}
    assert 429 not in statuses


def test_idle_windows_are_evicted_and_live_ones_kept(monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr(rate_limiter, "time", types.SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(rate_limiter, "_last_sweep", clock[0])

    for _ in range(10_000):
        _check_rate_limit("ip", f"/analyze/job/{uuid.uuid4()}", "GET")
    _allow("ip", "/analyze", "POST", 10)
    assert len(_rate_limit_store["ip"]) == 10_001

    clock[0] += 120  # past the default 60 s window, inside POST /analyze's hour
    _check_rate_limit("other", "/ping", "GET")  # any request runs the due sweep
    assert list(_rate_limit_store["ip"]) == ["POST /analyze"]
    with pytest.raises(HTTPException):  # the sweep never resets a live limit
        _check_rate_limit("ip", "/analyze", "POST")

    clock[0] += 3600
    _check_rate_limit("other", "/ping", "GET")
    assert "ip" not in _rate_limit_store
