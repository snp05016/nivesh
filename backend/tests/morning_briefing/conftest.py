"""
Fixtures for morning_briefing test suite.

Leverages the parent conftest.py module-level mocks (yfinance, anthropic, etc.)
and adds morning-briefing-specific fixtures for cache, seeded users, etc.

Run from the backend directory:
    .venv/bin/python3 -m pytest tests/morning_briefing/ -v --tb=short
"""

import sys
import os
import time
import threading
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pull in parent conftest fixtures so we don't duplicate user/auth setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ---------------------------------------------------------------------------
# Cache-related fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cache_dict():
    """A plain dict acting as a mock Redis cache for unit tests."""
    return {}


@pytest.fixture
def cache_service_instance():
    """Create a fresh CacheService instance pointing at an invalid Redis URL
    so it always falls back to the in-process dict. This gives us real cache
    behaviour without needing a Redis server."""
    from services.cache_service import CacheService
    svc = CacheService(redis_url="redis://localhost:19999")  # non-existent port → fallback
    # Clear any cruft from previous tests
    svc._fallback_cache.clear()
    return svc


@pytest.fixture
def mock_cache_service(monkeypatch, cache_service_instance):
    """
    Replace the global `cache` singleton with our isolated instance
    so tests don't interfere with each other.
    """
    import services.cache_service as _cs
    monkeypatch.setattr(_cs, "cache", cache_service_instance)
    # Also patch the sync helpers to use our instance
    monkeypatch.setattr(_cs, "sync_get", cache_service_instance.get_sync)
    monkeypatch.setattr(_cs, "sync_set", cache_service_instance.set_sync)
    return cache_service_instance


@pytest.fixture(autouse=True)
def _ai_processing_consent(monkeypatch):
    """These tests exercise the AI brief path, which needs the opt-in
    'ai_processing' consent (FINSEC-04). The gate itself is covered by
    tests/test_ai_consent_gate.py."""
    import routers.portfolio as _pmod
    monkeypatch.setattr(_pmod, "has_active_consent", lambda *_args, **_kwargs: True)


# ---------------------------------------------------------------------------
# Anthropic / LLM mocks with richer Morning Brief responses
# ---------------------------------------------------------------------------
# Re-export from the package __init__ for backward compatibility
from tests.morning_briefing import MOCK_MORNING_BRIEF_TEXT, _json_body
from tests.conftest import REGISTER_CONSENT

MOCK_MORNING_BRIEF_JSON = {
    "summary": MOCK_MORNING_BRIEF_TEXT,
    "movers": ["RELIANCE"],
    "mood": "positive",
    "generated_at": "08:30",
}


@pytest.fixture
def mock_anthropic_response():
    """Return a MagicMock that mimics anthropic.Anthropic().messages.create() response."""
    resp = MagicMock()
    resp.content = [MagicMock(text=MOCK_MORNING_BRIEF_TEXT)]
    resp.usage = MagicMock(input_tokens=150, output_tokens=120)
    return resp


@pytest.fixture
def mock_anthropic_client(monkeypatch, mock_anthropic_response):
    """Patch the Anthropic client to return our mock response."""
    import anthropic as _anthro
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    # We need to patch at the point of creation in the endpoint
    monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# User and auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_user_creds(client):
    """Register and login a dedicated morning-brief test user (session-scoped).
    Returns a dict with 'user_id' (int), 'headers' (dict), and 'token' (str)."""
    username = f"mb_test_{int(time.time() * 1000) % 1000000}"
    password = "MorningTest!123"
    resp = client.post("/register", json={
        "username": username,
        "password": password,
        "display_name": "Morning Brief Tester",
        **REGISTER_CONSENT,
    })
    assert resp.status_code in (200, 409), resp.text  # 409 = already exists from prior run
    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()
    return {
        "user_id": data["user_id"],
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest.fixture
def auth_headers(test_user_creds):
    """Return just the Authorization header dict (strings only)."""
    return test_user_creds["headers"]


@pytest.fixture
def test_user_id(test_user_creds):
    """Return the test user's integer user_id."""
    return test_user_creds["user_id"]


@pytest.fixture
def seeded_user(client, test_user_id, auth_headers):
    """Add a portfolio holding into the test user, return user_id."""
    uid = test_user_id
    resp = client.post("/portfolio/add", json={
        "user_id": uid,
        "ticker": "RELIANCE",
        "exchange": "NSE",
        "company_name": "Reliance Industries Ltd",
        "shares": 10,
        "buy_price": 2500.0,
        "group_name": "holdings",
    }, headers=auth_headers)
    if resp.status_code not in (200, 409):
        raise RuntimeError(f"Failed to seed holding: {resp.status_code} {resp.text}")
    return uid


@pytest.fixture
def seeded_user_multi(client, test_user_id, auth_headers):
    """Add multiple holdings to the test user, return user_id."""
    uid = test_user_id
    holdings = [
        ("RELIANCE", "Reliance Industries Ltd", 10, 2500.0),
        ("TCS", "Tata Consultancy Services", 5, 3800.0),
        ("HDFCBANK", "HDFC Bank Ltd", 15, 1650.0),
    ]
    for ticker, company, shares, price in holdings:
        resp = client.post("/portfolio/add", json={
            "user_id": uid,
            "ticker": ticker,
            "exchange": "NSE",
            "company_name": company,
            "shares": shares,
            "buy_price": price,
            "group_name": "holdings",
        }, headers=auth_headers)
        if resp.status_code not in (200, 409):
            raise RuntimeError(f"Failed to seed {ticker}: {resp.status_code} {resp.text}")
    return uid


