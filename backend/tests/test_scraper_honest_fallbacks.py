"""FAKE-14 / FAKE-V2: scraper fallbacks must report what they measured, never
synthesise market-wide numbers (x10 breadth, hardcoded fund returns,
extrapolated 'declared results' counts)."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

import services.scraper as scraper

_REAL_FIRECRAWL_EXTRACT = scraper._firecrawl_extract


@pytest.fixture(autouse=True)
def _no_cache_no_firecrawl(monkeypatch):
    monkeypatch.setattr(scraper, "_cache_get", lambda key: None)
    monkeypatch.setattr(scraper, "_cache_set", lambda key, data: None)
    monkeypatch.setattr(scraper, "_firecrawl_extract", lambda url, schema: None)


def _fake_yf(download):
    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame()  # no index data, no retry sleeps
    return SimpleNamespace(Ticker=lambda sym: ticker, download=download)


def _boom(*args, **kwargs):
    raise RuntimeError("network down")


def test_pulse_fallback_unscaled(monkeypatch):
    sample = scraper._NIFTY_SAMPLE
    cols = {}
    for i, sym in enumerate(sample):
        cols[(sym, "Close")] = [100.0, 101.0 if i < 14 else 99.0]  # 14 up, 6 down
    frame = pd.DataFrame(cols)  # tuple keys -> MultiIndex columns, like yf group_by="ticker"
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(lambda *a, **k: frame))

    result = scraper.fetch_market_pulse()

    assert result["advances"] == 14
    assert result["declines"] == 6
    assert result["advances"] + result["declines"] + result["unchanged"] <= len(sample)
    assert result["breadth_sample_size"] == len(sample) == 20
    assert result["source"] == "yfinance_sample"


def test_institutional_flow_no_hardcoded_funds(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(_boom))

    result = scraper.fetch_institutional_flow()

    assert result["funds"] == []
    assert result["source"] == "unavailable"


def test_mf_fallback_uses_real_history(monkeypatch):
    syms = list(scraper._MF_YF_TICKERS.values())
    cols = {(sym, "Close"): [100.0 + d for d in range(20)] for sym in syms}
    frame = pd.DataFrame(cols)  # tuple keys -> MultiIndex columns, like yf group_by="ticker"
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(lambda *a, **k: frame))

    result = scraper.fetch_institutional_flow()

    assert len(result["funds"]) == len(syms)
    assert result["source"] == "yfinance"
    assert all(f["one_year_return_pct"] == 19.0 for f in result["funds"])


def test_sync_ratio_unavailable(monkeypatch):
    monkeypatch.setattr(scraper.requests, "get", _boom)
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(_boom))

    result = scraper.fetch_earnings_sync_ratio()

    assert result["declared_count"] is None
    assert result["source"] == "unavailable"


def test_firecrawl_extract_v2(monkeypatch):
    calls = {}

    def scrape(url, formats):
        calls["formats"] = formats
        return SimpleNamespace(json={"a": 1})

    monkeypatch.setattr(scraper, "_get_firecrawl", lambda: SimpleNamespace(scrape=scrape))

    assert _REAL_FIRECRAWL_EXTRACT("https://example.com", {"type": "object"}) == {"a": 1}
    assert calls["formats"] == [{"type": "json", "schema": {"type": "object"}}]


def test_firecrawl_output_normalised_to_ios_contract(monkeypatch):
    """Null A/D counts or a fund with no category must never reach iOS:
    MarketPulseResponse/MutualFund decode those fields as non-optional."""
    def extract(url, schema):
        if schema is scraper._PULSE_SCHEMA:
            return {
                "indices": [
                    {"name": "NIFTY 50", "value": "24,000", "change_pts": "+10",
                     "change_pct": "+0.04%", "direction": "up"},
                    {"name": "BANK", "value": None, "change_pts": "+1",
                     "change_pct": "+0.1%", "direction": "up"},
                ],
                "advances": None, "declines": 10, "unchanged": 2,
            }
        return {"funds": [
            {"name": "Good Fund", "category": "Large Cap", "one_year_return_pct": 12.5, "aum_cr": None},
            {"name": "No Category", "category": None, "one_year_return_pct": 30.0, "aum_cr": 100.0},
            {"name": "Bad Return", "category": "Large Cap", "one_year_return_pct": "12%"},
        ]}

    monkeypatch.setattr(scraper, "_firecrawl_extract", extract)
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(_boom))

    pulse = scraper.fetch_market_pulse()
    assert pulse["source"] == "yfinance_sample"
    assert all(isinstance(pulse[k], int) for k in ("advances", "declines", "unchanged"))

    flow = scraper.fetch_institutional_flow()
    assert flow["source"] == "firecrawl"
    assert [f["name"] for f in flow["funds"]] == ["Good Fund"]
    assert all(isinstance(f["name"], str) and isinstance(f["category"], str) for f in flow["funds"])


def test_firecrawl_pulse_accepted_when_valid(monkeypatch):
    row = {"name": "NIFTY 50", "value": "24,000", "change_pts": "+10",
           "change_pct": "+0.04%", "direction": "up", "junk": None}
    monkeypatch.setattr(scraper, "_firecrawl_extract",
                        lambda url, schema: {"indices": [row], "advances": 30, "declines": 15, "unchanged": 5})

    pulse = scraper.fetch_market_pulse()
    assert pulse["source"] == "firecrawl"
    assert pulse["indices"] == [{k: row[k] for k in scraper._PULSE_INDEX_KEYS}]
    assert pulse["breadth_ratio"] == 2.0
