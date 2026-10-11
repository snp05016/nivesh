"""SILENT-14: a degraded morning brief is never cached, and pre-generation counts
an unusable LLM reply as an error instead of storing a 'please refresh' placeholder.

Before the fix a missing ANTHROPIC_API_KEY (or a parse failure) cached the canned
'Market data loaded' brief for 24 h, and the cache read served it until expiry.
"""
import asyncio
import random
from types import SimpleNamespace

import pandas as pd
import pytest

import database
import routers.morning_brief as morning_brief
import services.disk_cache as disk_cache
import services.llm_utils as llm_utils
from models.db_models import Portfolio, User
from services import portfolio_snapshot


@pytest.fixture
def brief_env(monkeypatch):
    """Consent granted, no cached brief, no network; records every cache write."""
    sets = []
    monkeypatch.setattr(morning_brief, "has_active_consent", lambda _uid, _c: True)
    monkeypatch.setattr(morning_brief, "_dcache_get", lambda _ns, _key: None)
    monkeypatch.setattr(morning_brief, "_dcache_set",
                        lambda ns, key, value, ttl=None: sets.append((ns, key)))
    monkeypatch.setattr(morning_brief, "_yf_price", lambda _sym: (None, None))
    monkeypatch.setattr(morning_brief, "_get_indices_data", lambda: {"indices": []})
    monkeypatch.setattr(morning_brief.llm_budget, "guard", lambda *_a, **_k: None)
    return sets


def test_missing_key_not_cached(client, auth_headers, test_user_id, brief_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["degraded"] is True
    assert not [s for s in brief_env if s[0] == "morning_brief"]


def test_parse_failure_not_cached(client, auth_headers, test_user_id, brief_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setattr(llm_utils, "claude_messages",
                        lambda **_kw: SimpleNamespace(content=[SimpleNamespace(text="not json")]))

    resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["degraded"] is True
    assert not [s for s in brief_env if s[0] == "morning_brief"]


def test_cached_degraded_brief_is_regenerated(client, auth_headers, test_user_id, brief_env, monkeypatch):
    stale = {"summary": morning_brief.FALLBACK_SUMMARY, "movers": [], "mood": "cautious",
             "generated_at": "01:00", "degraded": True}
    monkeypatch.setattr(morning_brief, "_dcache_get", lambda _ns, _key: stale)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setattr(llm_utils, "claude_messages", lambda **_kw: SimpleNamespace(
        content=[SimpleNamespace(text='{"summary":"• fresh","movers":[],"mood":"positive"}')]))

    resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"] == "• fresh"
    assert "degraded" not in body
    assert ("morning_brief", str(test_user_id)) in brief_env


def test_pregen_parse_failure_counts_error(monkeypatch):
    uid = random.randint(10_000_000, 99_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"pregen_bad_{uid}", password_hash="x", display_name="Pregen Bad"))
        session.add(Portfolio(user_id=uid, ticker="TCS", company_name="TCS", shares=5,
                              buy_price=3000.0, group_name="holdings"))
        session.commit()

    # Only this user is processed; every other session user is skipped.
    monkeypatch.setattr(portfolio_snapshot, "has_active_consent", lambda user_id, _c: user_id == uid)
    monkeypatch.setattr(llm_utils, "deepseek_chat", lambda _messages, **_kw: "garbage")
    ticker = SimpleNamespace(history=lambda period="2d": pd.DataFrame({"Close": [3000.0, 3090.0]}))
    monkeypatch.setattr(portfolio_snapshot, "yf", SimpleNamespace(Ticker=lambda _sym: ticker))
    cached = {}
    monkeypatch.setattr(disk_cache, "set",
                        lambda ns, key, value, ttl=None: cached.__setitem__((ns, key), value))

    result = asyncio.run(portfolio_snapshot.pregen_morning_briefs_all_users())

    assert result["errors"] == 1, result
    assert result["generated"] == 0, result
    assert ("morning_brief", str(uid)) not in cached
