"""CMKT-03: /api/v1/market/dashboard-pulse reads the keys the scrapers really return.

fetch_market_pulse (Firecrawl extract and yfinance fallback) puts advances, declines,
unchanged and breadth_ratio at the top level; there is no "breadth" sub-dict.
"""
import pytest

import routers.market as market

_BULL = {
    "ticker": "TCS", "last_price": 4000.0, "ma20": 3900.0, "ma50": 3800.0,
    "sparkline": [1.0], "trend_date": "2026-10-09", "crossover": "golden_cross",
}


@pytest.fixture
def pulse(client, monkeypatch):
    """GET dashboard-pulse with fetch_market_pulse returning pulse_raw; returns the JSON body."""
    def _get(pulse_raw: dict) -> dict:
        monkeypatch.setattr(market, "fetch_market_pulse", lambda: pulse_raw)
        monkeypatch.setattr(market, "fetch_momentum",
                            lambda: {"bullish": [_BULL], "bearish": [], "fetched_at": "x"})
        monkeypatch.setattr(market, "fetch_yoy_aggregate_indicators", lambda: {})
        monkeypatch.setattr(market, "_build_cap_index_grid", lambda: [])
        resp = client.get("/api/v1/market/dashboard-pulse")
        assert resp.status_code == 200, resp.text
        return resp.json()
    return _get


def test_dashboard_pulse_passes_real_scraper_shapes(pulse):
    body = pulse({"indices": [], "advances": 12, "declines": 8, "unchanged": 0,
                  "breadth_ratio": 1.5, "breadth_sample_size": 20, "fetched_at": "x"})

    assert body["pulse"]["advances"] == 12
    assert body["pulse"]["declines"] == 8
    assert body["pulse"]["breadth_ratio"] == 1.5
    assert body["pulse"]["breadth_sample_size"] == 20
    assert body["momentum"]["bullish"][0]["last_price"] == 4000.0
    assert body["momentum"]["bullish"][0]["ma20"] == 3900.0


def test_dashboard_pulse_computes_breadth_ratio_when_missing(pulse):
    body = pulse({"indices": [], "advances": 10, "declines": 5, "unchanged": 1, "fetched_at": "x"})

    assert body["pulse"]["breadth_ratio"] == 2.0
    assert body["pulse"]["unchanged"] == 1


def test_dashboard_pulse_without_breadth_reports_none(pulse):
    body = pulse({})

    assert (body["pulse"]["advances"], body["pulse"]["declines"]) == (0, 0)
    assert body["pulse"]["breadth_ratio"] is None
