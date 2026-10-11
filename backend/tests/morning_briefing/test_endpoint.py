"""
Integration tests for the GET /morning-summary/{user_id} endpoint.

Validates the full request → cache → Anthropic → response pipeline,
plus auth enforcement, cache hit/miss behaviour, and fallback paths.

Regression coverage:
  - B3: No extra_body in Anthropic call (verified via mock_calls inspection)
  - N1: No cache_control in orchestrator (verified via source search in test_regression.py)
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.morning_briefing import _json_body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_morning_url(user_id):
    return f"/morning-summary/{user_id}"


# ---------------------------------------------------------------------------
# Tests — basic endpoint behaviour
# ---------------------------------------------------------------------------

class TestEndpointBasic:
    """Basic endpoint response structure and content tests."""

    def test_endpoint_returns_200(self, client, seeded_user, auth_headers):
        """Basic request → verify 200 status code."""
        uid = seeded_user
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code} — {resp.text}"

    def test_endpoint_returns_valid_structure(self, client, seeded_user, auth_headers):
        """Response must contain required fields: summary, movers, mood, generated_at."""
        uid = seeded_user
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        body = _json_body(resp)

        assert "summary" in body, f"Missing 'summary' in response: {body}"
        assert "movers" in body, f"Missing 'movers' in response: {body}"
        assert "mood" in body, f"Missing 'mood' in response: {body}"
        assert "generated_at" in body, f"Missing 'generated_at' in response: {body}"

    def test_endpoint_mood_is_valid_enum(self, client, seeded_user, auth_headers):
        """mood field must be one of: positive, cautious, negative, or "unavailable"
        when no brief could be computed (FAKE-22: never a made-up "cautious")."""
        uid = seeded_user
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        body = _json_body(resp)

        assert body["mood"] in ("positive", "cautious", "negative", "unavailable"), \
            f"Invalid mood value: {body['mood']}"

    def test_endpoint_returns_real_content_not_fallback(
        self, client, seeded_user, auth_headers, monkeypatch,
    ):
        """When the Anthropic mock returns valid JSON, the response must NOT
        contain the fallback string 'AI brief unavailable'.

        The endpoint expects the LLM to return a JSON object with 'summary',
        'movers', and 'mood' keys, wrapped in text. We return a valid JSON
        string that the endpoint's _extract_json_from_text can parse.
        """
        uid = seeded_user

        import anthropic as _anthro
        valid_json = json.dumps({
            "summary": "• Nifty opened flat today\n• RELIANCE up 2% to ₹2,560\nOverall mood: positive",
            "movers": ["RELIANCE"],
            "mood": "positive",
        })
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=valid_json)]
        mock_resp.usage = MagicMock(input_tokens=50, output_tokens=30)
        mock_client.messages.create.return_value = mock_resp
        monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: mock_client)

        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        body = _json_body(resp)

        assert "AI brief unavailable" not in body.get("summary", ""), \
            f"Fallback text detected: {body}"

    def test_endpoint_no_portfolio_returns_200(self, client, test_user_id, auth_headers):
        """User with no holdings still gets a 200 response (with fallback content)."""
        uid = test_user_id
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Tests — caching behaviour
# ---------------------------------------------------------------------------

class TestEndpointCaching:
    """Cache hit/miss/expiry tests for the morning-summary endpoint."""

    def test_endpoint_cache_hit(
        self, client, seeded_user, auth_headers, monkeypatch,
    ):
        """First call populates cache → second call returns cached content
        without making a second Anthropic call.

        We instrument the Anthropic client to count calls and inject a real
        in-memory dict for _dcache_get/_dcache_set so caching actually works.
        """
        uid = seeded_user
        call_count = [0]

        # Replace the mocked disk_cache with a real in-memory dict.
        # The morning-brief router imports _dcache_get/_dcache_set at module load
        # time, so we must monkeypatch the router module's own reference.
        _test_cache = {}
        import routers.morning_brief as _pmod
        monkeypatch.setattr(_pmod, "_dcache_get", lambda ns, key: _test_cache.get(f"{ns}:{key}"))
        monkeypatch.setattr(_pmod, "_dcache_set", lambda ns, key, val, ttl=None: _test_cache.__setitem__(f"{ns}:{key}", val))

        import anthropic as _anthro
        valid_json = json.dumps({
            "summary": "• Cached morning brief — markets steady",
            "movers": ["RELIANCE"],
            "mood": "cautious",
        })

        class CountingClient:
            def __init__(self):
                self.messages = CountingMessages()
        class CountingMessages:
            def create(self, **kwargs):
                call_count[0] += 1
                resp = MagicMock()
                resp.content = [MagicMock(text=valid_json)]
                resp.usage = MagicMock(input_tokens=10, output_tokens=5)
                return resp

        monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: CountingClient())

        # First call — should call Anthropic
        resp1 = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp1.status_code == 200
        assert call_count[0] == 1

        # Second call — should use cache, no Anthropic call
        resp2 = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp2.status_code == 200
        assert call_count[0] == 1, "Anthropic was called again on cache hit!"

        body2 = _json_body(resp2)
        body1 = _json_body(resp1)
        assert body2.get("summary") == body1.get("summary")

    def test_endpoint_cache_miss_generates_fresh(
        self, client, seeded_user, auth_headers, monkeypatch,
    ):
        """After invalidating the cache, the next request makes a fresh Anthropic call."""
        uid = seeded_user
        call_count = [0]

        import anthropic as _anthro

        def make_brief(idx):
            return json.dumps({
                "summary": f"• Brief #{idx}" if idx == 1 else "• Second brief — fresh",
                "movers": [],
                "mood": "cautious",
            })

        class CountingClient:
            def __init__(self):
                self.messages = CountingMessages()
        class CountingMessages:
            def create(self, **kwargs):
                call_count[0] += 1
                resp = MagicMock()
                resp.content = [MagicMock(text=make_brief(call_count[0]))]
                resp.usage = MagicMock(input_tokens=10, output_tokens=5)
                return resp

        monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: CountingClient())

        # First call populates cache
        resp1 = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp1.status_code == 200
        assert call_count[0] == 1

        # Invalidate the cache by modifying portfolio (add then remove a holding)
        client.post("/portfolio/add", json={
            "user_id": uid,
            "ticker": "INFY",
            "exchange": "NSE",
            "company_name": "Infosys Ltd",
            "shares": 1,
            "buy_price": 1500.0,
            "group_name": "holdings",
        }, headers=auth_headers)
        client.request("DELETE", "/portfolio/remove", json={
            "user_id": uid,
            "ticker": "INFY",
            "group_name": "holdings",
        }, headers=auth_headers)

        # Second call should be a cache miss — new Anthropic call
        resp2 = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp2.status_code == 200
        assert call_count[0] == 2, f"Expected 2 Anthropic calls, got {call_count[0]}"

        body2 = _json_body(resp2)
        assert "Second brief" in body2.get("summary", ""), \
            f"Expected fresh content, got: {body2}"

    def test_endpoint_portfolio_change_invalidates(
        self, client, seeded_user, auth_headers, monkeypatch,
    ):
        """Adding a new holding invalidates the morning brief cache for that user.

        Regression for B1: cache invalidation on portfolio mutation.
        """
        uid = seeded_user
        call_count = [0]

        import anthropic as _anthro
        class CountingClient:
            def __init__(self):
                self.messages = CountingMessages()
        class CountingMessages:
            def create(self, **kwargs):
                call_count[0] += 1
                resp = MagicMock()
                # Valid JSON: a canned fallback is never cached (FAKE-22), which
                # would make the second call a miss even without invalidation.
                text = json.dumps({"summary": f"• Brief #{call_count[0]}", "movers": [], "mood": "positive"})
                resp.content = [MagicMock(text=text)]
                resp.usage = MagicMock(input_tokens=10, output_tokens=5)
                return resp

        monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: CountingClient())

        # First brief
        client.get(_get_morning_url(uid), headers=auth_headers)
        assert call_count[0] == 1

        # Add a holding — this calls _cache_invalidate("morning_brief", str(user_id))
        client.post("/portfolio/add", json={
            "user_id": uid,
            "ticker": "ITC",
            "exchange": "NSE",
            "company_name": "ITC Ltd",
            "shares": 5,
            "buy_price": 450.0,
            "group_name": "holdings",
        }, headers=auth_headers)

        # Second brief — should be a cache miss
        client.get(_get_morning_url(uid), headers=auth_headers)
        assert call_count[0] == 2, f"Expected cache invalidation; call_count={call_count[0]}"

    def test_endpoint_no_cache_returns_fallback_on_api_error(
        self, client, seeded_user, auth_headers, monkeypatch,
    ):
        """When Anthropic API fails, the endpoint returns fallback text.

        We simulate an empty API key which triggers the fallback path.
        """
        uid = seeded_user
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")

        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = _json_body(resp)
        # Must return a fallback, not crash
        assert "summary" in body
        assert "mood" in body


class TestEndpointTTL:
    """Cache TTL validation tests."""

    def test_endpoint_24h_ttl_value(self):
        """Verify MORNING_BRIEF_TTL is exactly 86400.

        Regression for B5: TTL must be 86400 seconds (24 hours).
        """
        from config.settings import MORNING_BRIEF_TTL
        assert MORNING_BRIEF_TTL == 86400, \
            f"MORNING_BRIEF_TTL expected 86400, got {MORNING_BRIEF_TTL}"

    def test_cache_service_ttl_map_morning_brief(self):
        """CacheService.ttl_map['morning_brief'] must be 86400."""
        from services.cache_service import CacheService
        svc = CacheService(redis_url="redis://localhost:19999")
        assert svc.ttl_map["morning_brief"] == 86400


class TestEndpointAuth:
    """Authentication enforcement tests."""

    def test_endpoint_requires_auth(self, client):
        """Request without auth header → 401 or 422."""
        resp = client.get(_get_morning_url(1))
        # 401 Unauthorized or 422 Unprocessable Entity (missing header)
        assert resp.status_code in (401, 403, 422), \
            f"Expected auth error, got {resp.status_code}: {resp.text}"

    def test_endpoint_token_user_mismatch(self, client, test_user_id, auth_headers):
        """User-1's token accessing user-2's summary → 401."""
        uid = test_user_id
        other_uid = uid + 99999  # Non-existent user ID
        resp = client.get(_get_morning_url(other_uid), headers=auth_headers)
        assert resp.status_code == 401, \
            f"Expected 401 for user mismatch, got {resp.status_code}: {resp.text}"

    def test_endpoint_own_summary_works(self, client, test_user_id, auth_headers):
        """User accessing their own summary → 200."""
        uid = test_user_id
        resp = client.get(_get_morning_url(uid), headers=auth_headers)
        assert resp.status_code in (200, 404), \
            f"Expected 200 or 404 (no portfolio), got {resp.status_code}: {resp.text}"


class TestEndpointNoCacheExploit:
    """Prevent cache-less AI abuse."""

    def test_endpoint_does_not_loop_on_repeated_calls(self, client, seeded_user, auth_headers):
        """Submitting the same request 5 times should not cause 500s or timeouts."""
        uid = seeded_user
        for i in range(5):
            resp = client.get(_get_morning_url(uid), headers=auth_headers)
            assert resp.status_code == 200, \
                f"Request #{i} failed with {resp.status_code}: {resp.text}"
