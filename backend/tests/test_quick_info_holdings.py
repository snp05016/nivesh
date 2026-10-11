"""CMKT-08 / SILENT-22: /quick-info and /api/v1/stock-profile report the same shareholding
and D/E values in the same units, and never invent an FII/DII split or a pledge share
(the old quick-info set DII = 35% of institutional; see #256, #304, #306, #462)."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

import routers.analysis as analysis_router
import routers.market as market_router
from services.market_service import holdings_from_info

_INFO = {
    "currentPrice": 2500.0,
    "previousClose": 2480.0,
    "longName": "ZZ Holdings Ltd",
    "heldPercentInstitutions": 0.44,
    "heldPercentInsiders": 0.5,
    "debtToEquity": 36.6,  # Yahoo reports D/E as a percentage
}


def test_holdings_from_info():
    h = holdings_from_info(_INFO)
    assert h == {
        "promoter_holding_pct": 50.0,
        "institutional_holding_pct": 44.0,
        "fii_holding_pct": None,
        "dii_holding_pct": None,
        "promoter_pledged_pct": None,
        "debt_to_equity": 0.37,
    }


def test_holdings_from_info_missing_or_bad_values():
    h = holdings_from_info({"heldPercentInstitutions": float("nan"), "debtToEquity": "n/a"})
    assert all(v is None for v in h.values())


class _Ticker:
    info = _INFO
    news: list = []
    dividends = pd.Series(dtype=float)
    actions = pd.DataFrame()
    earnings_history = pd.DataFrame()
    quarterly_financials = pd.DataFrame()

    def history(self, period="1y"):
        return pd.DataFrame()


def test_quick_info_and_stock_profile_agree(client, monkeypatch):
    # quick-info: yfinance via routers.analysis.yf, cache via services.disk_cache
    monkeypatch.setattr(analysis_router, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(analysis_router, "yf", SimpleNamespace(Ticker=lambda _sym: _Ticker()))
    monkeypatch.setattr(analysis_router, "_get_asm_gsm_lists", lambda: {"ASM": set(), "GSM": set()})
    disk_cache = sys.modules["services.disk_cache"]
    monkeypatch.setattr(disk_cache, "get", lambda *_a, **_k: None)
    monkeypatch.setattr(disk_cache, "set", MagicMock())
    # stock-profile: info via routers.market._yf_fetch_info, its own disk cache helpers
    monkeypatch.setattr(market_router, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(market_router, "_yf_fetch_info", lambda _sym: dict(_INFO))
    monkeypatch.setattr(market_router, "get_price_history", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_get_quarterly_fin", lambda _sym: (None, None))
    monkeypatch.setattr(market_router, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_dcache_set", lambda *_a, **_k: None)

    quick = client.get("/quick-info", params={"ticker": "ZZHOLD"})
    profile = client.get("/api/v1/stock-profile", params={"ticker": "ZZHOLD"})

    assert quick.status_code == 200, quick.text
    assert profile.status_code == 200, profile.text
    q, p = quick.json(), profile.json()
    for body in (q, p):
        assert body["debt_to_equity"] == 0.37
        assert body["institutional_holding_pct"] == 44.0
        assert body["promoter_holding_pct"] == 50.0
        assert body["fii_holding_pct"] is None
        assert body["dii_holding_pct"] is None
    assert q["promoter_pledged_pct"] is None
