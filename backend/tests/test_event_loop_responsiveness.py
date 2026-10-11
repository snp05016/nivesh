"""PERF-02: the job-poll, cancel, home-feed, valuation and attribution handlers run
their blocking DB / yfinance / subprocess work in the threadpool, never on the loop.

Requests share one event loop through httpx.ASGITransport, so a handler that
blocked the loop would hold /ping up for the full blocking call.
"""
import asyncio
import contextlib
import inspect
import time

import httpx

import database
import main
import routers.analysis as analysis
import routers.portfolio as portfolio
import routers.portfolio_analytics as portfolio_analytics
import services.job_manager as job_manager

_BLOCK_S = 1.0
_PING_BUDGET_S = 0.25


def _ping_while(method: str, path: str, **kwargs):
    """Start a slow request, ping meanwhile; return (slow response, ping seconds, slow seconds)."""
    async def scenario():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            t0 = time.perf_counter()
            slow = asyncio.create_task(ac.request(method, path, **kwargs))
            await asyncio.sleep(0.05)
            p0 = time.perf_counter()
            ping = await ac.get("/ping")
            ping_s = time.perf_counter() - p0
            assert ping.status_code == 200
            resp = await slow
            return resp, ping_s, time.perf_counter() - t0

    return asyncio.run(scenario())


def test_job_poll_is_sync_handler():
    handlers = [
        analysis.get_job_status, analysis.get_active_job, analysis.cancel_job_endpoint,
        analysis.cache_status, analysis.get_home_feed, portfolio.portfolio_endpoint,
        portfolio_analytics.get_valuation_history, portfolio_analytics.portfolio_attribution_endpoint,
    ]
    offenders = [h.__name__ for h in handlers if inspect.iscoroutinefunction(h)]
    assert not offenders, f"blocking handlers must be plain def: {offenders}"


def test_home_feed_does_not_block_loop(monkeypatch):
    real_session = analysis.get_session

    @contextlib.contextmanager
    def _slow_session():
        time.sleep(_BLOCK_S)  # stands in for a slow/locked DB
        with real_session() as s:
            yield s

    monkeypatch.setattr(analysis, "get_session", _slow_session)

    resp, ping_s, slow_s = _ping_while("GET", "/api/v1/home-feed", params={"user_id": 0})

    assert resp.status_code == 200, resp.text
    assert slow_s >= _BLOCK_S  # the patched session really ran
    assert ping_s < _PING_BUDGET_S, f"/ping took {ping_s:.2f}s while home-feed was in flight"


def test_cancel_offloop(monkeypatch):
    monkeypatch.setattr(analysis, "_owned_job", lambda job_id, caller: {"job_id": job_id, "user_id": caller})
    monkeypatch.setattr(job_manager, "cancel_job", lambda _job_id: time.sleep(_BLOCK_S))
    headers = {"Authorization": f"Bearer {database.create_access_token(990001)}"}

    resp, ping_s, slow_s = _ping_while("POST", "/analyze/perf02-job/cancel", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CANCELLED"
    assert slow_s >= _BLOCK_S
    assert ping_s < _PING_BUDGET_S, f"/ping took {ping_s:.2f}s while cancel was terminating a worker"
