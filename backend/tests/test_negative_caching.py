"""SILENT-11: a transient provider failure is served but never cached as authoritative.

yfinance and services.disk_cache are MagicMocks (tests/conftest.py); each test spies
on the cache writes. Ticker resolution TTLs are covered by test_yfinance_client_guards.py.
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest
import redis

import routers.analysis as analysis_router
import routers.market as market_router
import services.cache_service as cs
import services.user_service as user_service


def _ticker(info: dict) -> MagicMock:
    tk = MagicMock()
    tk.info = info
    tk.history.return_value = pd.DataFrame()
    tk.news = []
    return tk


@pytest.fixture
def disk_cache_spy(monkeypatch):
    """quick-info caches through cache_service.cached_call -> cache.set_sync."""
    spy = MagicMock()
    monkeypatch.setattr(cs.cache, "get_sync", lambda *_a, **_k: None)
    monkeypatch.setattr(cs.cache, "set_sync", spy)
    return spy


def _quick_info_cached(spy) -> bool:
    """True when quick-info was cached for its full TTL (a 60 s negative entry does not count)."""
    return any(c.args[:1] == ("quick-info",) and c.args[3] == analysis_router._QUICK_INFO_TTL
               for c in spy.call_args_list)


@pytest.mark.parametrize("info,cached", [
    ({}, False),                                                  # Yahoo failed: hollow payload
    ({"currentPrice": 100.0, "longName": "Xyz Ltd"}, True),       # control: real data is cached
])
def test_quick_info_hollow_not_cached(client, monkeypatch, disk_cache_spy, info, cached):
    monkeypatch.setattr(analysis_router.yf, "Ticker", lambda *_a, **_k: _ticker(info))
    monkeypatch.setattr(analysis_router.time, "sleep", lambda *_a: None)

    resp = client.get("/quick-info?ticker=XYZ")

    assert resp.status_code == 200
    assert _quick_info_cached(disk_cache_spy) is cached


def _fin_frame() -> pd.DataFrame:
    col = pd.Timestamp("2026-06-30")
    return pd.DataFrame({col: [3.5e10, 5.0e9]}, index=["Total Revenue", "Net Income"])


@pytest.mark.parametrize("fin,cached", [(None, False), ("frame", True)])
def test_quarterly_empty_not_cached(client, monkeypatch, fin, cached):
    spy = MagicMock()
    monkeypatch.setattr(market_router, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_dcache_set", spy)
    frame = _fin_frame() if fin == "frame" else None
    monkeypatch.setattr(market_router, "_get_quarterly_fin", lambda _t: (MagicMock(), frame))

    resp = client.get("/quarterly-financials?ticker=NEGCACHE&exchange=NSE")

    assert resp.status_code == 200
    assert bool(resp.json()["quarters"]) is cached
    assert spy.called is cached


@pytest.fixture
def watchlist_row(test_user_id):
    """One watchlist row for the session test user, inserted directly (no tier quota)."""
    from database import Portfolio, get_session
    with get_session() as session:
        session.add(Portfolio(user_id=test_user_id, ticker="NEGWATCH", company_name="Neg Watch",
                              shares=0, buy_price=0, group_name="watchlist"))
        session.commit()
    user_service._watchlist_price_cache.pop(test_user_id, None)
    yield test_user_id
    user_service._watchlist_price_cache.pop(test_user_id, None)
    with get_session() as session:
        session.query(Portfolio).filter_by(user_id=test_user_id, ticker="NEGWATCH",
                                           group_name="watchlist").delete()
        session.commit()


def test_watchlist_unavailable_price_not_cached(monkeypatch, watchlist_row):
    uid = watchlist_row
    monkeypatch.setattr(user_service, "_get_asm_gsm_lists", lambda: {"ASM": set(), "GSM": set()})

    monkeypatch.setattr(user_service, "_yf_price", lambda _sym: (None, None))
    out = user_service.get_watchlist(uid)
    assert out is not None
    assert any(r["price_status"] == "unavailable" for r in out["watchlist"])
    assert uid not in user_service._watchlist_price_cache

    monkeypatch.setattr(user_service, "_yf_price", lambda _sym: (101.0, 100.0))
    user_service.get_watchlist(uid)
    assert uid in user_service._watchlist_price_cache  # control: live prices are cached


def test_cache_service_reads_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6380")
    assert cs.CacheService().redis_url == "redis://example:6380"


def test_configured_redis_down_logs_critical_once(monkeypatch, caplog):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:19999")
    monkeypatch.setattr(cs, "_critical_logged", False)
    svc = cs.CacheService()

    def _down(*_a, **_k):
        raise redis.ConnectionError("redis down")

    monkeypatch.setattr(svc._client, "get", _down)
    monkeypatch.setattr(cs, "_now", lambda: 0.0)

    with caplog.at_level("WARNING", logger=cs.logger.name):
        assert svc.get_sync("ns", "k") is None
        svc._down_until = 0.0  # leave backoff so the second call hits Redis again
        assert svc.get_sync("ns", "k") is None

    criticals = [r for r in caplog.records if r.levelname == "CRITICAL"]
    assert len(criticals) == 1
    assert "REDIS_URL configured" in criticals[0].getMessage()
