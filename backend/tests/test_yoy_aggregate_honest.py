"""FAKE-09: the YoY aggregate averages only tickers with a valid
same-quarter-prior-year comparison, and failure is null (not 0.0%/0.0%)."""
import sys
from types import SimpleNamespace

import pandas as pd

import routers.market as market_router
import services.scraper as scraper

_GOOD = {"RELIANCE.NS", "TCS.NS", "INFY.NS"}


def _fake_ticker(good: set):
    def make(symbol, *_a, **_k):
        if symbol in good:
            # 5 quarters, newest first: +10% vs the same quarter last year.
            rev = [110.0, 105.0, 103.0, 101.0, 100.0]
            profit = [22.0, 21.0, 20.5, 20.2, 20.0]
        else:
            rev, profit = [100.0, 99.0], [20.0, 19.0]
        cols = list(range(len(rev)))
        inc = pd.DataFrame([rev, profit], index=["Total Revenue", "Net Income"], columns=cols)
        return SimpleNamespace(quarterly_income_stmt=inc)
    return make


def test_short_history_does_not_dilute(monkeypatch):
    monkeypatch.setattr(sys.modules["yfinance"], "Ticker", _fake_ticker(_GOOD))
    out = scraper._fetch_yoy_fallback()
    assert out["revenue_yoy_pct"] == 10.0
    assert out["net_profit_yoy_pct"] == 10.0
    assert out["companies_reported"] == 3
    assert out["sample_size"] > 3
    assert out["source"] == "yfinance_sample"


def test_all_short_is_null(monkeypatch):
    monkeypatch.setattr(sys.modules["yfinance"], "Ticker", _fake_ticker(set()))
    out = scraper._fetch_yoy_fallback()
    assert out["revenue_yoy_pct"] is None
    assert out["net_profit_yoy_pct"] is None
    assert out["companies_reported"] == 0


def test_dashboard_pulse_null_yoy_health(client, monkeypatch):
    monkeypatch.setattr(market_router, "fetch_market_pulse", lambda: {})
    monkeypatch.setattr(market_router, "fetch_momentum", lambda: {})
    monkeypatch.setattr(market_router, "_build_cap_index_grid", lambda: [])
    monkeypatch.setattr(
        market_router, "fetch_yoy_aggregate_indicators",
        lambda: {"revenue_yoy_pct": None, "net_profit_yoy_pct": None,
                 "companies_reported": 0, "source": "yfinance_sample"},
    )
    resp = client.get("/api/v1/market/dashboard-pulse")
    assert resp.status_code == 200, resp.text
    assert resp.json()["yoy_market_health"] is None
