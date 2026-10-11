"""PERF-10: global market endpoints are single-flight cached with per-item isolation.

The endpoint functions are called directly from threads. Every test gets its own
CacheService with Redis forced down, so the bounded in-process fallback is used
and nothing leaks into (or out of) the shared singleton.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import redis

import routers.earnings as earnings_router
import routers.market as market_router
import services.cache_service as cs


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cs, "_now", lambda: now[0])
    return now


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, clock):
    svc = cs.CacheService(redis_url="redis://localhost:19999")

    def _down(*_a, **_k):
        raise redis.ConnectionError("redis down")

    for op in ("get", "set", "delete", "info"):
        monkeypatch.setattr(svc._client, op, _down)
    monkeypatch.setattr(cs, "cache", svc)
    return svc


def _hammer(fn, n=10):
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(lambda _: fn(), range(n)))


def test_macro_strip_single_flight(monkeypatch):
    calls = []
    lock = threading.Lock()

    def _ticker(sym):
        with lock:
            calls.append(sym)
        time.sleep(0.05)
        return SimpleNamespace(info={"regularMarketPrice": 83.25})

    monkeypatch.setattr(market_router.yf, "Ticker", _ticker)

    results = _hammer(market_router.macro_strip_endpoint)

    assert sorted(calls) == sorted(sym for _, sym in market_router._MACRO_SYMBOLS)
    for body in results:
        assert body["usd_inr"] == 83.25
        assert body["india_vix_source"] == "live"
        assert "rbi_source" in body


def test_macro_strip_one_failing_symbol_is_null(monkeypatch):
    def _ticker(sym):
        if sym == "BZ=F":
            raise RuntimeError("yahoo 429")
        return SimpleNamespace(info={"regularMarketPrice": 70.0})

    monkeypatch.setattr(market_router.yf, "Ticker", _ticker)
    body = market_router.macro_strip_endpoint()
    assert body["brent_oil_usd"] is None
    assert body["usd_inr"] == 70.0


def test_sector_partial_not_cached_long(monkeypatch, clock):
    good = {t for t, _ in market_router.SECTOR_TICKERS[:2]}
    calls = []
    lock = threading.Lock()

    def _price(ticker):
        with lock:
            calls.append(ticker)
        return (110.0, 100.0) if ticker in good else (None, None)

    monkeypatch.setattr(market_router, "_yf_price", _price)

    first = market_router.sector_performance_endpoint()
    assert len(first["sectors"]) == 2
    assert first["sectors"][0]["change_pct"] == 10.0
    assert len(calls) == len(market_router.SECTOR_TICKERS)

    clock[0] += 30  # inside the 60 s negative TTL: served from cache
    market_router.sector_performance_endpoint()
    assert len(calls) == len(market_router.SECTOR_TICKERS)

    clock[0] += 31  # 61 s later: the partial result has expired and is refetched
    market_router.sector_performance_endpoint()
    assert len(calls) == 2 * len(market_router.SECTOR_TICKERS)


def test_sector_full_result_single_flight(monkeypatch):
    calls = []
    lock = threading.Lock()

    def _price(ticker):
        with lock:
            calls.append(ticker)
        time.sleep(0.05)
        return 105.0, 100.0

    monkeypatch.setattr(market_router, "_yf_price", _price)
    results = _hammer(market_router.sector_performance_endpoint)
    assert len(calls) == len(market_router.SECTOR_TICKERS)
    assert all(len(r["sectors"]) == len(market_router.SECTOR_TICKERS) for r in results)


def test_earnings_calendar_one_bad_ticker(monkeypatch):
    holdings = ["TCS", "INFY", "BAD", "HDFCBANK", "ITC"]
    upcoming = date.today() + timedelta(days=10)
    calls = []
    lock = threading.Lock()

    class _Ticker:
        def __init__(self, sym):
            self.sym = sym

        @property
        def calendar(self):
            with lock:
                calls.append(self.sym)
            time.sleep(0.05)
            if self.sym == "BAD":
                raise RuntimeError("yahoo rate limited")
            return {"Earnings Date": [upcoming]}

    monkeypatch.setattr(earnings_router, "_holding_tickers", lambda: list(holdings))
    monkeypatch.setattr(earnings_router, "_resolve_ticker", lambda t, _ex: t)
    monkeypatch.setattr(earnings_router.yf, "Ticker", _Ticker)

    results = _hammer(earnings_router.earnings_calendar_endpoint)

    assert sorted(calls) == sorted(holdings)  # 10 concurrent callers, one upstream pass
    for body in results:
        tickers = sorted(e["ticker"] for e in body["events"])
        assert tickers == sorted(t for t in holdings if t != "BAD")
        assert all(e["days_away"] == 10 for e in body["events"])
