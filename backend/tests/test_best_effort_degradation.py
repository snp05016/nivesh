"""CMKT-04: optional enrichment failures degrade to partial 200s instead of HTTP 500.

Commit 6258ac68 turned best-effort fallbacks into `raise HTTPException(500)`; these
cover the stock profile, macro context, quick-info and the /analyze cache check.
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

import database
import routers.analysis as analysis_router
import routers.market as market_router
from models.db_models import AnalysisHistory


def _insert_row(ticker: str, full_json: str) -> None:
    with database.get_session() as session:
        session.add(AnalysisHistory(
            user_id=None, ticker=ticker, analysis_date="2026-10-01", signal="BULLISH",
            confidence_pct=70, full_json=full_json, scan_type="standard",
        ))
        session.commit()


def test_stock_profile_200_when_info_empty_and_history_row_malformed(client, monkeypatch):
    _insert_row("ZZPROF", '{"fundamentals_snapshot": null}')
    cache_writes = []
    monkeypatch.setattr(market_router, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(market_router, "_yf_fetch_info", lambda _sym: {})
    monkeypatch.setattr(market_router, "get_price_history", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_get_quarterly_fin", lambda _sym: (None, None))
    monkeypatch.setattr(market_router, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_dcache_set",
                        lambda ns, key, value, ttl=None: cache_writes.append(ttl))

    resp = client.get("/api/v1/stock-profile", params={"ticker": "ZZPROF"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "company_info_unavailable" in body["errors"]
    assert body["institutional_holding_pct"] is None
    assert body["fii_holding_pct"] is None
    assert body["dii_holding_pct"] is None
    assert body["quarterly_financials"]["promoter_history"] == []
    assert cache_writes == [60]  # partial profiles are cached briefly


def test_macro_context_200_when_ai_summary_unreadable(client, monkeypatch):
    _insert_row("ZZMACRO", "not json")
    import services.scraper as scraper
    monkeypatch.setattr(scraper, "fetch_market_pulse", lambda: {})
    monkeypatch.setattr(market_router, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_dcache_set", lambda *_a, **_k: None)

    resp = client.get("/macro-context/ZZMACRO")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ai_summary" not in body
    assert body["summary"]  # rule-based summary used instead


class _QuickInfoTicker:
    info = {"currentPrice": 100.0, "previousClose": 98.0, "longName": "ZZ Governance Ltd"}
    news: list = []
    dividends = pd.Series(dtype=float)
    actions = pd.DataFrame()
    earnings_history = pd.DataFrame()
    quarterly_financials = pd.DataFrame()

    def history(self, period="1y"):
        return pd.DataFrame()


def test_quick_info_200_when_governance_row_corrupt(client, monkeypatch):
    _insert_row("ZZGOV", "not json")
    monkeypatch.setattr(analysis_router, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(analysis_router, "yf", SimpleNamespace(Ticker=lambda _sym: _QuickInfoTicker()))
    monkeypatch.setattr(analysis_router, "_get_asm_gsm_lists", lambda: {"ASM": set(), "GSM": set()})
    disk_cache = sys.modules["services.disk_cache"]
    monkeypatch.setattr(disk_cache, "get", lambda *_a, **_k: None)
    cache_set = MagicMock()
    monkeypatch.setattr(disk_cache, "set", cache_set)

    resp = client.get("/quick-info", params={"ticker": "ZZGOV"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["current_price"] == 100.0
    assert body["governance_score"] is None
    assert body["governance_red_flags"] == []
    assert "governance_unavailable" in body["errors"]
    cache_set.assert_not_called()  # a degraded result is not cached


def test_analyze_cache_check_failure_spawns_job(client, auth_headers, spawned_jobs, monkeypatch):
    def _broken_cache(*_a, **_k):
        raise RuntimeError("corrupt cached analysis")

    monkeypatch.setattr(database, "get_analysis_for_date", _broken_cache)

    resp = client.post("/analyze", json={"ticker": "ZZCACHE", "exchange": "NSE"}, headers=auth_headers)

    assert resp.status_code == 202, resp.text
    assert resp.json()["job_id"]
    assert len(spawned_jobs) == 1
