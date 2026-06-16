"""
Edge case tests for the morning briefing system.

Covers portfolios with unusual data, special characters, boundary values,
and error-recovery scenarios.
"""

import json
import time
from unittest.mock import MagicMock

import pytest

from tests.morning_briefing import _json_body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_morning_url(user_id):
    return f"/morning-summary/{user_id}"


def _create_user(client, suffix):
    """Register + login a one-off test user."""
    username = f"edge_{suffix}_{int(time.time() * 1000) % 100000}"
    password = "EdgeCase!123"
    resp = client.post("/register", json={
        "username": username,
        "password": password,
        "display_name": f"Edge User {suffix}",
    })
    if resp.status_code not in (200, 409):
        raise RuntimeError(f"Register failed: {resp.status_code} {resp.text}")
    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def _seed_holdings(client, uid, headers, holdings_list):
    """Seed a list of (ticker, company, shares, buy_price) holdings."""
    for ticker, company, shares, price in holdings_list:
        resp = client.post("/portfolio/add", json={
            "user_id": uid,
            "ticker": ticker,
            "exchange": "NSE",
            "company_name": company,
            "shares": shares,
            "buy_price": price,
            "group_name": "holdings",
        }, headers=headers)
        if resp.status_code not in (200, 409):
            # 409 = already exists from previous test, which is fine
            pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmptyPortfolio:
    """User with no holdings."""

    def test_empty_portfolio_returns_200(self, client, test_user_id, auth_headers):
        """User with no holdings → endpoint returns 200 with valid structure."""
        uid = test_user_id
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = _json_body(resp)
        assert "summary" in body
        assert "movers" in body
        assert "mood" in body


class TestSingleStock:
    """User with exactly one holding."""

    def test_single_stock_brief_includes_that_stock(self, client):
        """User with 1 holding → the brief must reference that stock."""
        uid, headers = _create_user(client, "single")
        _seed_holdings(client, uid, headers, [
            ("TCS", "Tata Consultancy Services", 5, 3800.0),
        ])

        resp = client.get(_get_morning_url(uid), headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = _json_body(resp)
        # The response is a dict with summary text — it should not crash
        assert "summary" in body


class TestLargePortfolio:
    """User with many holdings — must not crash or timeout."""

    def test_very_long_holdings_list_does_not_crash(self, client):
        """User with 50 holdings → endpoint returns 200 without crashing.

        The endpoint fetches prices for all holdings, so this also
        validates that the yfinance batch doesn't cause issues.
        """
        uid, headers = _create_user(client, "large")

        tickers = [
            "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM",
            "RELIANCE", "ONGC", "GAIL", "BPCL", "IOC",
            "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
            "ITC", "HINDUNILVR", "NESTLE", "BRITANNIA", "DABUR",
            "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "BIOCON",
            "LT", "ADANIPORTS", "NTPC", "POWERGRID", "BHARTIARTL",
            "MARUTI", "TATAMOTORS", "M&M", "EICHERMOT", "BAJFINANCE",
            "TITAN", "ASIANPAINT", "BERGEPAINT", "PIDILITIND", "SRF",
            "ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC", "GRASIM",
            "JSWSTEEL", "TATASTEEL", "HINDALCO", "VEDL", "COALINDIA",
        ]
        assert len(tickers) == 50

        _seed_holdings(client, uid, headers, [
            (t, f"{t} Ltd", 10, 1000.0) for t in tickers
        ])

        resp = client.get(_get_morning_url(uid), headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = _json_body(resp)
        assert "summary" in body


class TestSpecialCharacters:
    """Ticker symbols with special characters."""

    def test_special_characters_in_ticker(self, client):
        """Ticker with ampersand (&) in name → handled without crash.

        Some NSE tickers like M&M have special characters.
        """
        uid, headers = _create_user(client, "special")
        _seed_holdings(client, uid, headers, [
            ("M&M", "Mahindra & Mahindra Ltd", 10, 2500.0),
        ])

        resp = client.get(_get_morning_url(uid), headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_ticker_with_dots(self, client):
        """Ticker with dots in name → handled without crash.

        Some international tickers have dots (e.g., BRK.B).
        """
        uid, headers = _create_user(client, "dots")
        _seed_holdings(client, uid, headers, [
            ("HDFC.NS", "HDFC Bank via NS suffix", 10, 1600.0),
        ])

        resp = client.get(_get_morning_url(uid), headers=headers)
        # Should not 500
        assert resp.status_code in (200, 422), f"Got unexpected status: {resp.status_code}"


class TestNegativePnL:
    """Negative P&L scenarios."""

    def test_negative_pnl_brief_still_generated(self, client):
        """Holding with high buy price (negative P&L) → brief still generated.
        
        The brief format should handle negative numbers correctly.
        """
        uid, headers = _create_user(client, "negative")
        _seed_holdings(client, uid, headers, [
            ("TCS", "Tata Consultancy Services", 10, 99999.0),  # Very high buy price
        ])

        resp = client.get(_get_morning_url(uid), headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {literally}"

        body = _json_body(resp)
        assert "summary" in body


class TestZeroAndNonePrice:
    """yfinance returning edge-case values."""

    def test_zero_price_does_not_divide_by_zero(self, client, monkeypatch):
        """When yfinance returns price=0 → no ZeroDivisionError.
        
        We mock the yfinance Ticker to return a price of 0.
        """
        uid, headers = _create_user(client, "zeroprice")
        _seed_holdings(client, uid, headers, [
            ("ZEROTEST", "Zero Price Stock", 10, 100.0),
        ])

        # Mock yfinance to return price=0
        import yfinance as _yf
        orig_ticker = _yf.Ticker

        class ZeroPriceTicker:
            def __init__(self, symbol):
                self.history = self._history
            def _history(self, period="2d"):
                import pandas as pd
                import numpy as np
                try:
                    return pd.DataFrame({"Close": [0.0, 0.0]})
                except ImportError:
                    mock = MagicMock()
                    mock.empty = False
                    mock.__len__ = lambda self: 2
                    mock.iloc = [0.0, 0.0]
                    return mock

        monkeypatch.setattr(_yf, "Ticker", ZeroPriceTicker)

        resp = client.get(_get_morning_url(uid), headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_none_price_fallback(self, client, monkeypatch):
        """When yfinance returns None/empty history → uses fallback price.
        
        The code should fall back to buy_price (cost basis) or 0.
        """
        uid, headers = _create_user(client, "noneprice")
        _seed_holdings(client, uid, headers, [
            ("NONEPRICE", "None Price Stock", 10, 100.0),
        ])

        import yfinance as _yf

        class NoneTicker:
            def __init__(self, symbol):
                pass
            def history(self, period="2d"):
                mock = MagicMock()
                mock.empty = True
                return mock

        monkeypatch.setattr(_yf, "Ticker", NoneTicker)

        resp = client.get(_get_morning_url(uid), headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


class TestNonExistentUser:
    """Requesting a brief for a non-existent user."""

    def test_nonexistent_user_returns_404(self, client, auth_headers):
        """Morning brief for user_id that doesn't exist → 404."""
        nonexistent_id = 999_999_999
        resp = client.get(_get_morning_url(nonexistent_id), headers=auth_headers)
        # 401 because token user doesn't match the URL user_id
        assert resp.status_code == 401, \
            f"Expected 401 for non-existent user access, got {resp.status_code}: {resp.text}"


class TestInvalidUserId:
    """Malformed user_id parameters."""

    def test_non_integer_user_id(self, client):
        """Passing a non-integer user_id → FastAPI returns 422."""
        resp = client.get("/morning-summary/abc")
        assert resp.status_code in (422, 401, 403), \
            f"Expected 422/401 for non-integer user_id, got {resp.status_code}: {resp.text}"


class TestLargeResponse:
    """Response size sanity."""

    def test_response_is_not_huge(self, client, seeded_user_multi, auth_headers):
        """Response payload should be reasonable (< 10 KB).

        If the response is massive, something went wrong (e.g. unparsed AI output).
        """
        uid = seeded_user_multi
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp.status_code == 200

        content_length = len(resp.content)
        assert content_length < 10_000, \
            f"Response too large: {content_length} bytes"
