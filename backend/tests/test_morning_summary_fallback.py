"""FAKE-22: a morning brief nobody computed carries no mood and is never cached.

The fallback used to report mood "cautious" and was cached for MORNING_BRIEF_TTL
(24 h), so one LLM timeout pinned a canned 'cautious' brief for the day, and the
morning push turned it into a NEUTRAL notification.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import routers.morning_brief as morning_brief
import services.llm_utils as llm_utils
import services.user_service as user_service
from services.alerts_service import PushResult


@pytest.fixture
def brief_edges(monkeypatch):
    """No network, consent granted, empty cache; returns the _dcache_set recorder."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(morning_brief, "has_active_consent", lambda *_a: True)
    monkeypatch.setattr(morning_brief, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(morning_brief, "_yf_price", lambda _sym: (None, None))
    monkeypatch.setattr(morning_brief, "_get_indices_data", lambda: {"indices": []})
    monkeypatch.setattr(morning_brief.llm_budget, "guard", lambda *_a: None)
    cache_set = MagicMock()
    monkeypatch.setattr(morning_brief, "_dcache_set", cache_set)
    return cache_set


def _llm_reply(monkeypatch, text):
    reply = SimpleNamespace(content=[SimpleNamespace(text=text)])
    monkeypatch.setattr(llm_utils, "claude_messages", MagicMock(return_value=reply))


def _brief_writes(cache_set):
    return [c for c in cache_set.call_args_list if c.args and c.args[0] == "morning_brief"]


def test_llm_failure_returns_uncached_brief_without_mood(client, auth_headers, test_user_id, brief_edges, monkeypatch):
    monkeypatch.setattr(llm_utils, "claude_messages", MagicMock(side_effect=TimeoutError("anthropic timeout")))

    resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"] == morning_brief.FALLBACK_SUMMARY
    assert body["mood"] == morning_brief.MOOD_UNAVAILABLE
    assert _brief_writes(brief_edges) == []


def test_unparseable_llm_output_is_not_cached(test_user_id, brief_edges, monkeypatch):
    _llm_reply(monkeypatch, "not json at all")

    result = morning_brief.build_morning_summary(test_user_id)

    assert result["mood"] == morning_brief.MOOD_UNAVAILABLE
    assert _brief_writes(brief_edges) == []


def test_invalid_mood_is_unavailable_not_cautious(test_user_id, brief_edges, monkeypatch):
    _llm_reply(monkeypatch, '{"summary": "• Nifty flat", "movers": [], "mood": "bullish-ish"}')

    result = morning_brief.build_morning_summary(test_user_id)

    assert result["summary"] == "• Nifty flat"
    assert result["mood"] == morning_brief.MOOD_UNAVAILABLE


def test_real_brief_is_cached(test_user_id, brief_edges, monkeypatch):
    _llm_reply(monkeypatch, '{"summary": "• Nifty up", "movers": [], "mood": "positive"}')

    result = morning_brief.build_morning_summary(test_user_id)

    assert result["mood"] == "positive"
    assert len(_brief_writes(brief_edges)) == 1


def test_push_refuses_brief_without_computed_mood(client, auth_headers, test_user_id, monkeypatch):
    deliver = MagicMock(return_value=PushResult.SENT)
    monkeypatch.setattr(user_service, "_deliver_apns", deliver)
    brief = {"summary": "• Enable 'AI processing' ...", "movers": [], "mood": morning_brief.MOOD_UNAVAILABLE}
    monkeypatch.setattr(morning_brief, "build_morning_summary", MagicMock(return_value=brief))

    resp = client.post("/notifications/morning-summary-push", json={"user_id": test_user_id}, headers=auth_headers)

    assert resp.status_code == 503
    deliver.assert_not_called()
