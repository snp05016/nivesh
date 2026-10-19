"""LLM-19: read endpoints reuse their paid LLM output instead of calling on every request."""
import json
import random
from unittest.mock import MagicMock

import pytest

import database
from models.db_models import AnalysisHistory, Portfolio, User
from routers import analysis, portfolio_analytics
from services import llm_budget


@pytest.fixture
def env(monkeypatch):
    """Dict-backed disk cache, consent granted, budget open, DeepSeek mocked per router."""
    store = {}

    def _get(ns, key):
        return store.get((ns, key))

    def _set(ns, key, value, ttl=None):
        store[(ns, key)] = value

    llms = {}
    for module, reply in ((analysis, "Do X."), (portfolio_analytics, "Risk summary.")):
        monkeypatch.setattr(module, "_dcache_get", _get)
        monkeypatch.setattr(module, "_dcache_set", _set)
        monkeypatch.setattr(module, "has_active_consent", lambda *_a: True)
        llms[module.__name__] = MagicMock(return_value=reply)
        monkeypatch.setattr(module, "_deepseek_chat", llms[module.__name__])
    monkeypatch.setattr(llm_budget, "guard", lambda *_a: None)
    monkeypatch.setattr(portfolio_analytics, "_get_asm_gsm_lists", lambda: {"ASM": set(), "GSM": set()})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    return llms


def _user():
    uid = random.randint(50_000_000, 59_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"llmcache_{uid}", password_hash="x", display_name="Cache Test"))
        session.commit()
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def test_daily_action_calls_llm_once_per_day(client, env):
    uid, headers = _user()

    first = client.get(f"/daily-action/{uid}", headers=headers)
    second = client.get(f"/daily-action/{uid}", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["action"] == second.json()["action"] == "Do X"
    assert env["routers.analysis"].call_count == 1


def test_red_flags_summary_calls_llm_once(client, env):
    uid, headers = _user()
    ticker = f"RFC{uid % 100000}"
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker=ticker, company_name=ticker, shares=1,
                              buy_price=100.0, group_name="holdings"))
        session.add(AnalysisHistory(ticker=ticker, analysis_date="2026-10-01", signal="HOLD",
                                    full_json=json.dumps({"fundamentals_snapshot": {"promoter_pledged_pct": 45.0}})))
        session.commit()

    first = client.get(f"/portfolio/red-flags/{uid}", headers=headers)
    second = client.get(f"/portfolio/red-flags/{uid}", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["total_flags"] >= 1
    assert first.json()["summary"] == second.json()["summary"] == "Risk summary."
    assert env["routers.portfolio_analytics"].call_count == 1

