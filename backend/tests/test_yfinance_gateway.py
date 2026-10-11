"""PERF-07: yfinance goes through one cached gateway.

_yf_price / _yf_fetch_info / yf_history are cached in the shared cache with
per-key single flight; get_quotes dedupes and fetches concurrently; failures
are never cached. yf.Ticker is a counting fake and the cache is an in-process
CacheService with Redis forced off, so nothing touches the network.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

import services.cache_service as cs
import services.yfinance_client as yfc

_IDX = pd.date_range(end="2026-10-09", periods=5, freq="D", tz="Asia/Kolkata", name="Date")


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    svc = cs.CacheService(redis_url="redis://localhost:19999")
    svc._down_until = float("inf")  # never try Redis: bounded in-process fallback only
    monkeypatch.setattr(cs, "cache", svc)
    return svc


@pytest.fixture
def upstream(monkeypatch):
    """Counting fake for yf.Ticker(sym).history(period=...)."""
    state = {"calls": [], "frame": pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=_IDX),
             "delay": 0.0}
    lock = threading.Lock()

    class _Ticker:
        def __init__(self, sym):
            self.sym = sym

        def history(self, period=None, **_kw):
            with lock:
                state["calls"].append((self.sym, period))
            if state["delay"]:
                threading.Event().wait(state["delay"])  # not time.sleep: tests may stub it
            return state["frame"].copy()

    monkeypatch.setattr(yfc.yf, "Ticker", _Ticker)
    return state


def test_quote_cached(upstream):
    syms = [f"S{i}.NS" for i in range(10)]
    for _ in range(20):
        for sym in syms:
            assert yfc._yf_price(sym) == (104.0, 103.0)
    assert len(upstream["calls"]) == 10


def test_single_flight(upstream):
    upstream["delay"] = 0.05
    with ThreadPoolExecutor(20) as ex:
        results = list(ex.map(lambda _: yfc._yf_price("X.NS"), range(20)))
    assert len(upstream["calls"]) == 1
    assert all(r == (104.0, 103.0) for r in results)


def test_get_quotes_dedupes(upstream):
    quotes = yfc.get_quotes(["A.NS", "A.NS", "B.NS"])
    assert set(quotes) == {"A.NS", "B.NS"}
    assert quotes["A.NS"] == (104.0, 103.0)
    assert len(upstream["calls"]) == 2


def test_failed_quote_not_cached(upstream, monkeypatch):
    monkeypatch.setattr(yfc.time, "sleep", lambda *_a: None)  # skip the retry pause
    upstream["frame"] = pd.DataFrame()

    assert yfc._yf_price("EMPTY.NS") == (None, None)
    first = len(upstream["calls"])
    assert first >= 1
    assert yfc._yf_price("EMPTY.NS") == (None, None)
    assert len(upstream["calls"]) == 2 * first  # hit upstream again: nothing was cached


def test_yf_history_roundtrip(upstream):
    first = yfc.yf_history("X.NS", "90d")
    second = yfc.yf_history("X.NS", "90d")

    assert len(upstream["calls"]) == 1
    for frame in (first, second):
        assert frame.index.equals(_IDX)  # tz-aware IST index survives the cache
        assert [d.strftime("%Y-%m-%d") for d in frame.index] == [d.strftime("%Y-%m-%d") for d in _IDX]
        assert frame["Close"].tolist() == [100.0, 101.0, 102.0, 103.0, 104.0]


def test_yf_history_failure_is_empty_and_not_cached(upstream):
    upstream["frame"] = pd.DataFrame()
    assert yfc.yf_history("X.NS", "35d").empty
    assert yfc.yf_history("X.NS", "35d").empty
    assert len(upstream["calls"]) == 2


def test_nested_cached_call_from_pool_threads_does_not_deadlock(upstream, monkeypatch):
    """/sector-performance shape: an outer cached_call fans out to _yf_price
    (itself a cached_call) on pool threads. With the old 64 striped locks, 300
    inner keys hit the outer key's stripe with ~99% odds and hung forever."""
    monkeypatch.setattr(yfc, "_yf_guard", lambda: True)  # skip the token bucket
    syms = [f"^SEC{i}" for i in range(300)]

    def _compute():
        with ThreadPoolExecutor(8) as ex:
            return list(ex.map(yfc._yf_price, syms))

    out = {}
    t = threading.Thread(target=lambda: out.update(r=cs.cached_call("sector", "performance", _compute)), daemon=True)
    t.start()
    t.join(timeout=5)

    assert not t.is_alive(), "nested cached_call deadlocked"
    assert out["r"] == [(104.0, 103.0)] * len(syms)
    assert cs._SF_LOCKS == {}  # per-key locks are dropped once idle


def test_cache_hit_records_last_good(upstream, monkeypatch, isolated_cache):
    """A quote another process wrote to the shared cache still feeds the stale fallback."""
    monkeypatch.setattr(yfc, "_LAST_GOOD", {})
    isolated_cache.set_sync("quote", "HIT.NS", [50.0, 49.0], 60)

    assert yfc._yf_price("HIT.NS") == (50.0, 49.0)
    assert upstream["calls"] == []
    assert yfc._LAST_GOOD["HIT.NS"][:2] == (50.0, 49.0)
