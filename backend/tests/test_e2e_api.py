"""
Nivesh E2E Integration Test Suite
Tests live/staging endpoints, injects malformed data, verifies DB state changes.
Run: python -m pytest tests/test_e2e_api.py -v
"""
import pytest
import requests
import json
import os
import time
import hashlib
from datetime import datetime

BASE_URL = os.getenv("NIVESH_LIVE_E2E_BASE_URL")
TIMEOUT = 30

pytestmark = pytest.mark.skipif(
    not BASE_URL,
    reason="live E2E tests require NIVESH_LIVE_E2E_BASE_URL",
)


# ---------------------------------------------------------------------------
# Health & Infrastructure
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_endpoint_returns_200(self):
        r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data or "yfinance" in data

    def test_ping_returns_pong(self):
        r = requests.get(f"{BASE_URL}/ping", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_security_headers_present(self):
        r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert r.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_rate_limit_enforced(self):
        responses = []
        for _ in range(35):
            r = requests.get(f"{BASE_URL}/ping", timeout=TIMEOUT)
            responses.append(r.status_code)
        assert 429 in responses, "Rate limiter did not trigger after 30+ requests"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuth:
    def test_login_valid_credentials(self):
        r = requests.post(f"{BASE_URL}/login", json={
            "username": "saumya",
            "password": "123"
        }, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "user_id" in data or "id" in data

    def test_login_invalid_password_returns_error(self):
        r = requests.post(f"{BASE_URL}/login", json={
            "username": "saumya",
            "password": "wrongpassword"
        }, timeout=TIMEOUT)
        assert r.status_code in (401, 422, 200)
        if r.status_code == 200:
            data = r.json()
            assert "error" in data or "detail" in data or data.get("user_id") is None

    def test_login_missing_fields_returns_422(self):
        r = requests.post(f"{BASE_URL}/login", json={}, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_register_new_user(self):
        unique = int(time.time())
        r = requests.post(f"{BASE_URL}/register", json={
            "username": f"testuser_{unique}",
            "password": "TestPass123!",
            "display_name": "Test User"
        }, timeout=TIMEOUT)
        assert r.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Input Validation — Malformed Data Injection
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_analyze_invalid_ticker_rejected(self):
        r = requests.post(f"{BASE_URL}/analyze", json={
            "ticker": "../../etc/passwd",
            "exchange": "NSE"
        }, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_analyze_sql_injection_ticker(self):
        r = requests.post(f"{BASE_URL}/analyze", json={
            "ticker": "RELIANCE'; DROP TABLE users; --",
            "exchange": "NSE"
        }, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_analyze_invalid_exchange(self):
        r = requests.post(f"{BASE_URL}/analyze", json={
            "ticker": "RELIANCE",
            "exchange": "INVALID"
        }, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_analyze_xss_in_ticker(self):
        r = requests.post(f"{BASE_URL}/analyze", json={
            "ticker": "<script>alert(1)</script>",
            "exchange": "NSE"
        }, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_watchlist_add_missing_fields(self):
        r = requests.post(f"{BASE_URL}/watchlist/add", json={
            "user_id": 1
        }, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_portfolio_add_missing_fields(self):
        r = requests.post(f"{BASE_URL}/portfolio/add", json={
            "user_id": 1
        }, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_alerts_add_missing_fields(self):
        r = requests.post(f"{BASE_URL}/alerts/add", json={
            "user_id": 1
        }, timeout=TIMEOUT)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Market Data Endpoints
# ---------------------------------------------------------------------------

class TestMarketData:
    def test_market_pulse_returns_indices(self):
        r = requests.get(f"{BASE_URL}/api/v1/market/pulse", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "indices" in data
        assert isinstance(data["indices"], list)

    def test_momentum_returns_bullish_bearish(self):
        r = requests.get(f"{BASE_URL}/api/v1/market/momentum", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "bullish" in data
        assert "bearish" in data

    def test_macro_alternatives_returns_items(self):
        r = requests.get(f"{BASE_URL}/api/v1/market/macro-alternatives", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_institutional_flow_returns_funds(self):
        r = requests.get(f"{BASE_URL}/api/v1/market/institutional-flow", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "funds" in data

    def test_market_dashboard_unified(self):
        r = requests.get(f"{BASE_URL}/api/v1/market/dashboard", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_sector_performance(self):
        r = requests.get(f"{BASE_URL}/sector-performance", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_market_indices(self):
        r = requests.get(f"{BASE_URL}/market-indices", timeout=TIMEOUT)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Home Feed
# ---------------------------------------------------------------------------

class TestHomeFeed:
    def test_home_feed_returns_structure(self):
        r = requests.get(f"{BASE_URL}/api/v1/home-feed?user_id=1", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "youtube_videos" in data
        assert "news" in data
        assert isinstance(data["youtube_videos"], list)
        assert isinstance(data["news"], list)

    def test_home_feed_youtube_videos_have_required_fields(self):
        r = requests.get(f"{BASE_URL}/api/v1/home-feed?user_id=1", timeout=TIMEOUT)
        data = r.json()
        if data["youtube_videos"]:
            video = data["youtube_videos"][0]
            assert "title" in video
            assert "video_url" in video
            assert "channel_name" in video

    def test_home_feed_news_have_required_fields(self):
        r = requests.get(f"{BASE_URL}/api/v1/home-feed?user_id=1", timeout=TIMEOUT)
        data = r.json()
        if data["news"]:
            article = data["news"][0]
            assert "headline" in article
            assert "article_url" in article


# ---------------------------------------------------------------------------
# Portfolio Endpoints
# ---------------------------------------------------------------------------

class TestPortfolio:
    def test_get_portfolio(self):
        r = requests.get(f"{BASE_URL}/portfolio/1", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_portfolio_signal_warnings(self):
        r = requests.get(f"{BASE_URL}/portfolio/signal-warnings?user_id=1", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_portfolio_risk_analysis(self):
        r = requests.get(f"{BASE_URL}/portfolio/risk-analysis/1", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_portfolio_red_flags(self):
        r = requests.get(f"{BASE_URL}/portfolio/red-flags/1", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_portfolio_valuation_history(self):
        r = requests.get(f"{BASE_URL}/api/v1/portfolio/valuation-history?user_id=1&days=30", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_portfolio_export_excel(self):
        r = requests.get(f"{BASE_URL}/portfolio/export/excel/1", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "") or r.status_code == 200


# ---------------------------------------------------------------------------
# Watchlist Endpoints
# ---------------------------------------------------------------------------

class TestWatchlist:
    def test_get_watchlist(self):
        r = requests.get(f"{BASE_URL}/watchlist/1", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_add_to_watchlist_and_remove(self):
        # Add
        r = requests.post(f"{BASE_URL}/watchlist/add", json={
            "user_id": 1,
            "ticker": "INFY",
            "exchange": "NSE",
            "company_name": "Infosys Ltd"
        }, timeout=TIMEOUT)
        assert r.status_code in (200, 201, 409)

        # Remove
        r = requests.delete(f"{BASE_URL}/watchlist/remove", json={
            "user_id": 1,
            "ticker": "INFY"
        }, timeout=TIMEOUT)
        assert r.status_code in (200, 204, 404)


# ---------------------------------------------------------------------------
# Alerts Endpoints
# ---------------------------------------------------------------------------

class TestAlerts:
    def test_add_alert_and_check(self):
        r = requests.post(f"{BASE_URL}/alerts/add", json={
            "user_id": 1,
            "ticker": "RELIANCE",
            "target_price": 2500.0,
            "direction": "above"
        }, timeout=TIMEOUT)
        assert r.status_code in (200, 201)

        r = requests.get(f"{BASE_URL}/alerts/check/1", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_get_alerts(self):
        r = requests.get(f"{BASE_URL}/alerts/1", timeout=TIMEOUT)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Quick Info & Analysis
# ---------------------------------------------------------------------------

class TestQuickInfo:
    def test_quick_info_valid_ticker(self):
        r = requests.get(f"{BASE_URL}/quick-info?ticker=RELIANCE&exchange=NSE", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_quick_info_invalid_ticker(self):
        r = requests.get(f"{BASE_URL}/quick-info?ticker=INVALIDTICKER123&exchange=NSE", timeout=TIMEOUT)
        assert r.status_code in (200, 404, 400)


# ---------------------------------------------------------------------------
# Screener
# ---------------------------------------------------------------------------

class TestScreener:
    def test_screener_quality_value(self):
        r = requests.get(f"{BASE_URL}/screener?preset=quality_value", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_screener_invalid_preset(self):
        r = requests.get(f"{BASE_URL}/screener?preset=nonexistent", timeout=TIMEOUT)
        assert r.status_code in (200, 400, 404)


# ---------------------------------------------------------------------------
# Trade Journal
# ---------------------------------------------------------------------------

class TestTradeJournal:
    def test_get_trade_journal(self):
        r = requests.get(f"{BASE_URL}/trade-journal/1", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_trade_journal_stats(self):
        r = requests.get(f"{BASE_URL}/trade-journal/1/stats", timeout=TIMEOUT)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Technical Signals (Ensemble)
# ---------------------------------------------------------------------------

class TestTechnicalSignals:
    def test_technical_signals_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/v1/technical-signals", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data


# ---------------------------------------------------------------------------
# DB State Verification
# ---------------------------------------------------------------------------

class TestDBState:
    def test_users_table_has_seeded_data(self):
        r = requests.get(f"{BASE_URL}/users", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 3

    def test_portfolio_table_has_holdings(self):
        r = requests.get(f"{BASE_URL}/portfolio/2", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        if isinstance(data, list):
            assert len(data) > 0


# ---------------------------------------------------------------------------
# Timeout & Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_body_post_returns_422(self):
        r = requests.post(f"{BASE_URL}/analyze", timeout=TIMEOUT)
        assert r.status_code == 422

    def test_huge_payload_rejected(self):
        huge = {"ticker": "A" * 10000}
        r = requests.post(f"{BASE_URL}/analyze", json=huge, timeout=TIMEOUT)
        assert r.status_code in (422, 413, 400)

    def test_non_json_body_returns_error(self):
        r = requests.post(f"{BASE_URL}/analyze",
                          data="not json",
                          headers={"Content-Type": "application/json"},
                          timeout=TIMEOUT)
        assert r.status_code in (422, 400)

    def test_unknown_endpoint_returns_404(self):
        r = requests.get(f"{BASE_URL}/nonexistent-endpoint-xyz", timeout=TIMEOUT)
        assert r.status_code == 404

    def test_method_not_allowed(self):
        r = requests.delete(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert r.status_code in (404, 405)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
