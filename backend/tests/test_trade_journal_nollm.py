"""C16: trade-journal stats no longer call a paid LLM; patterns is always []."""
import random

import pytest

import database
from models.db_models import TradeJournal, User


def _user():
    uid = random.randint(60_000_000, 69_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"tjnollm_{uid}", password_hash="x", display_name="TJ"))
        session.commit()
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def test_stats_never_calls_llm(client, monkeypatch):
    import services.llm_utils as llm_utils

    calls = []
    monkeypatch.setattr(llm_utils, "deepseek_chat", lambda *a, **k: calls.append(1) or "[]")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    uid, headers = _user()
    with database.get_session() as session:
        session.add(TradeJournal(user_id=uid, ticker="TCS", action="BUY", price_at_time=3000.0,
                                 reason_text="Bought on results momentum"))
        session.commit()

    response = client.get(f"/trade-journal/{uid}/stats", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert calls == []
    assert body["patterns"] == []
    assert body["total_entries"] == 1
    assert body["action_breakdown"]["BUY"] == 1
    assert all(set(k) == {"word", "count"} for k in body["top_keywords"])


def test_router_has_no_llm_imports():
    import routers.trade_journal as tj

    assert not hasattr(tj, "_deepseek_chat")
    assert not hasattr(tj, "_extract_json_from_text")


def test_other_users_stats_rejected(client):
    uid, headers = _user()
    other, _ = _user()
    assert client.get(f"/trade-journal/{other}/stats", headers=headers).status_code == 403
    assert client.get(f"/trade-journal/{uid}/stats").status_code in (401, 403)
