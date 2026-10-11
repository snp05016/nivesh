"""REL-01: request handlers never run blocking yfinance/LLM/DB work on the event loop.

FastAPI runs `async def` handlers ON the single event loop; a sync call inside one
freezes every other request (/ping, auth, SSE). Handlers with no await must be
plain `def` so Starlette runs them in the threadpool.

Hermetic: conftest mocks yfinance/LLM clients; the DB is the temp SQLite file.
"""
import ast
import asyncio
import time
from pathlib import Path

import httpx

import main
import routers.earnings as earnings
import services.earnings_surprise as es
import services.market_service as market_service

BACKEND = Path(__file__).resolve().parent.parent
_ROUTE_METHODS = {"get", "post", "put", "delete", "patch"}
# dashboard_stream only builds a StreamingResponse; its SSE body is REL-11's.
_ALLOWED = {"routers/dashboard.py:dashboard_stream"}


def _is_route(fn: ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in _ROUTE_METHODS
        for d in fn.decorator_list
    )


def test_no_async_route_without_await():
    files = sorted((BACKEND / "routers").glob("*.py")) + [BACKEND / "services" / "harvest_worker.py"]
    offenders = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.AsyncFunctionDef) and _is_route(node)):
                continue
            if any(isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for n in ast.walk(node)):
                continue
            name = f"{path.relative_to(BACKEND)}:{node.name}"
            if name not in _ALLOWED:
                offenders.append(f"{name} (line {node.lineno})")
    assert not offenders, (
        "async route handlers with no await block the event loop; make them plain def: "
        + ", ".join(offenders)
    )


def test_blocking_estimates_does_not_stall_ping(monkeypatch):
    monkeypatch.setattr(market_service, "_yf_fetch_info", lambda _sym: time.sleep(1.0) or {})
    monkeypatch.setattr(market_service, "_to_ns", lambda t: t)

    async def scenario():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            t0 = time.perf_counter()
            slow = asyncio.create_task(ac.get("/api/v1/earnings/estimates", params={"ticker": "ZZSLOW"}))
            await asyncio.sleep(0.05)
            p0 = time.perf_counter()
            ping = await ac.get("/ping")
            ping_s = time.perf_counter() - p0
            est = await slow
            return ping, ping_s, est, time.perf_counter() - t0

    ping, ping_s, est, est_s = asyncio.run(scenario())
    assert ping.status_code == 200
    assert est.status_code == 200, est.text
    assert est_s >= 1.0  # the patched yfinance call really ran
    assert ping_s < 0.3, f"/ping took {ping_s:.2f}s while a yfinance call was in flight"


def test_earnings_surprises_cached(monkeypatch):
    calls = []
    store = {}
    monkeypatch.setattr(es, "compute_surprise_for_ticker", lambda t: calls.append(t))
    monkeypatch.setattr(es, "_dc_get", lambda ns, key: store.get((ns, key)))
    monkeypatch.setattr(es, "_dc_set", lambda ns, key, value, ttl=None: store.__setitem__((ns, key), value))

    assert es.get_all_surprises("current_quarter") == []
    assert es.get_all_surprises("current_quarter") == []
    # A random, attacker-chosen period must not bypass the cache either.
    assert es.get_all_surprises("cache-bust-8f3a") == []
    assert len(calls) == 8  # later calls served from cache: no yfinance, no DB writes
