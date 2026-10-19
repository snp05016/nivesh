"""money_market_series: engine series client, chunking, caching and the display gate (no network)."""
from __future__ import annotations

import dataclasses
import json

import httpx
import pytest

from services import money_market_series as mms
from services.research import config as research_config
from services.research.client import MLEngineClient


@pytest.fixture(autouse=True)
def env(monkeypatch):
    store = {}
    monkeypatch.setattr(mms.disk_cache, "get", lambda ns, key: store.get((ns, key)))
    monkeypatch.setattr(mms.disk_cache, "set", lambda ns, key, value, ttl=None: store.__setitem__((ns, key), value))
    cfg = dataclasses.replace(research_config.CONFIG, ml_engine_api_key="k-test", ml_engine_url="http://engine.test", mode="on")
    monkeypatch.setattr(research_config, "CONFIG", cfg)
    return store


def _use(monkeypatch, handler):
    monkeypatch.setattr(mms, "MLEngineClient", lambda: MLEngineClient("http://engine.test", "k-test", transport=httpx.MockTransport(handler)))


def _ok_handler(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((request.url.path, request.headers.get("X-ML-Engine-Key"), body))
        results = [{"key": i["key"], "status": "ok", "return_pct": 3.2, "nifty_return_pct": 1.1,
                    "start_date": "2024-03-05", "end_date": "2024-04-04", "stale_exit": False} for i in body["items"]]
        return httpx.Response(200, json={"results": results, "last_session": "2026-10-09"})
    return handler


def _item(i, **kw):
    return {"key": f"j{i}:21", "symbol": "infy.ns", "start": "2024-03-05", "sessions": 21, **kw}


def test_header_sent_and_symbol_normalised(monkeypatch):
    calls = []
    _use(monkeypatch, _ok_handler(calls))
    out = mms.window_returns([_item(1)])
    assert out["j1:21"]["return_pct"] == 3.2
    path, key, body = calls[0]
    assert path == "/research/v1/series/window-returns" and key == "k-test"
    assert body["items"][0]["symbol"] == "INFY"


def test_chunks_at_1000(monkeypatch):
    calls = []
    _use(monkeypatch, _ok_handler(calls))
    out = mms.window_returns([_item(i) for i in range(2300)])
    assert [len(c[2]["items"]) for c in calls] == [1000, 1000, 300]
    assert len(out) == 2300


def test_none_on_500_timeout_and_missing_key(monkeypatch):
    _use(monkeypatch, lambda r: httpx.Response(500))
    assert mms.window_returns([_item(1)]) is None

    def boom(request):
        raise httpx.ReadTimeout("slow")

    _use(monkeypatch, boom)
    assert mms.window_returns([_item(2)]) is None

    cfg = dataclasses.replace(research_config.CONFIG, ml_engine_api_key=None)
    monkeypatch.setattr(research_config, "CONFIG", cfg)
    assert mms.window_returns([_item(3)]) is None


def test_cache_hit_skips_call_and_pending_not_cached(monkeypatch):
    calls = []
    _use(monkeypatch, _ok_handler(calls))
    mms.window_returns([_item(1)])
    mms.window_returns([_item(1)])
    assert len(calls) == 1

    pend_calls = []

    def pending(request):
        pend_calls.append(1)
        body = json.loads(request.content)
        return httpx.Response(200, json={"results": [{"key": i["key"], "status": "pending"} for i in body["items"]]})

    _use(monkeypatch, pending)
    assert mms.window_returns([_item(9)])["j9:21"]["status"] == "pending"
    mms.window_returns([_item(9)])
    assert len(pend_calls) == 2


def test_raw_highs_route(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        body = json.loads(request.content)
        return httpx.Response(200, json={"results": [{"key": i["key"], "status": "ok", "high": 10.0} for i in body["items"]]})

    _use(monkeypatch, handler)
    out = mms.raw_highs([{"key": "a", "symbol": "TCS", "isin": None, "date": "2018-01-31"}])
    assert out["a"]["high"] == 10.0 and seen == ["/research/v1/series/raw-high"]


@pytest.mark.parametrize("mode,expected", [("on", True), ("shadow", False), ("off", False)])
def test_display_allowed(monkeypatch, mode, expected):
    monkeypatch.setattr(research_config, "CONFIG", dataclasses.replace(research_config.CONFIG, mode=mode))
    assert mms.display_allowed() is expected


def test_display_allowed_false_on_error(monkeypatch):
    monkeypatch.setattr(research_config, "CONFIG", None)
    assert mms.display_allowed() is False
