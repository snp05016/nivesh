"""Copilot v2 (spec_ai 3.2): computed portfolio answers, history scrub, advice backstop, provenance."""
import json
import pathlib
import random
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func

import database
from helpers import _ban_western_scale
from models.db_models import LlmUsage, Portfolio, User
from services import advisory_guard, copilot_service, llm_budget
from services.copilot_service import COMPUTED_REPLY_FOOTER, process_copilot_request

FIXTURES = json.loads((pathlib.Path(__file__).parent / "fixtures" / "copilot_replies.json").read_text())


def _make_user(rows):
    uid = random.randint(50_000_000, 59_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"copilot_v2_{uid}", password_hash="x", display_name="V2"))
        session.commit()
        for ticker, shares, price, group in rows:
            session.add(Portfolio(user_id=uid, ticker=ticker, company_name=ticker, shares=shares,
                                  buy_price=price, group_name=group))
        session.commit()
    return uid


@pytest.fixture
def make_user():
    created = []

    def make(rows):
        uid = _make_user(rows)
        created.append(uid)
        return uid

    yield make
    with database.get_session() as session:
        for uid in created:
            session.query(Portfolio).filter(Portfolio.user_id == uid).delete()
            session.query(User).filter(User.id == uid).delete()
        session.commit()


@pytest.fixture
def llm(monkeypatch):
    deepseek = MagicMock()
    haiku = MagicMock(return_value="haiku")
    monkeypatch.setattr(copilot_service, "deepseek_chat", deepseek)
    monkeypatch.setattr(copilot_service, "claude_haiku", haiku)
    return deepseek, haiku


def _prices(monkeypatch, table):
    monkeypatch.setattr(copilot_service, "_yf_price", lambda sym: (table.get(sym.replace(".NS", "")), None))


def test_exact_totals_and_watchlist_excluded(make_user, llm, monkeypatch):
    deepseek, haiku = llm
    uid = make_user([("TCS", 5, 3500, "holdings"), ("INFY", 10, 1500, "holdings"), ("WIPRO", 1, 400, "watchlist")])
    _prices(monkeypatch, {"TCS": 4000, "INFY": 1400})
    res = process_copilot_request("How is my portfolio doing?", [], {}, uid)
    reply = res["reply"]
    for expected in ("You hold 2 stocks", "₹32,500", "₹34,000", "+₹1,500", "(+4.6%)", "TCS 58.8%"):
        assert expected in reply
    assert "WIPRO" not in reply
    assert reply.endswith(COMPUTED_REPLY_FOOTER)
    assert res["reply_source"] == "computed"
    deepseek.assert_not_called()
    haiku.assert_not_called()


def test_two_lots_merge(make_user, llm, monkeypatch):
    uid = make_user([("TCS.NS", 3, 3400, "holdings"), ("TCS", 2, 3650, "holdings")])
    _prices(monkeypatch, {"TCS": 4000})
    reply = process_copilot_request("show my holdings", [], {}, uid)["reply"]
    assert "You hold 1 stock." in reply
    assert "Amount invested: ₹17,500" in reply
    assert "Largest by current value: TCS 100.0%." in reply
    assert reply.count("TCS") == 1


def test_intent_routed_portfolio_makes_one_llm_call(make_user, llm, monkeypatch):
    deepseek, haiku = llm
    deepseek.return_value = "PORTFOLIO"
    uid = make_user([("TCS", 5, 3500, "holdings")])
    _prices(monkeypatch, {"TCS": 4000})
    res = process_copilot_request("How am I doing overall?", [], {}, uid)
    assert res["reply_source"] == "computed"
    assert "You hold 1 stock." in res["reply"]
    assert deepseek.call_count == 1
    haiku.assert_not_called()


def test_no_holdings(make_user, llm):
    uid = make_user([])
    reply = process_copilot_request("my portfolio?", [], {}, uid)["reply"]
    assert reply == "You have no holdings in Nivesh yet. Add one from the Portfolio tab to see a summary here."


def test_unpriced_holding_noted_and_excluded(make_user, llm, monkeypatch):
    uid = make_user([("TCS", 5, 3500, "holdings"), ("INFY", 10, 1500, "holdings")])
    _prices(monkeypatch, {"TCS": 4000})
    reply = process_copilot_request("my portfolio", [], {}, uid)["reply"]
    assert "Prices were unavailable for 1 holding (INFY)" in reply
    assert "Amount invested: ₹32,500" in reply
    assert "Current value of the 1 with a price: ₹20,000, against ₹17,500 invested" in reply


def test_advice_reply_is_replaced(llm):
    deepseek, _ = llm
    deepseek.side_effect = ["GENERAL", "You should buy RELIANCE now."]
    res = process_copilot_request("thoughts?", [], {}, 1)
    assert res["reply"] == advisory_guard.ADVICE_REFUSAL_TEXT
    assert res["reply_source"] == "ai"


@pytest.mark.parametrize("case", FIXTURES, ids=[c["id"] for c in FIXTURES])
def test_advice_fixtures(case):
    assert len(FIXTURES) == 33
    assert bool(advisory_guard.find_advice(case["text"])) == (case["expect"] == "block")


def test_computed_reply_passes_western_scale_check(make_user, llm, monkeypatch):
    uid = make_user([("TCS", 500, 3500, "holdings")])
    _prices(monkeypatch, {"TCS": 4000})
    reply = process_copilot_request("my portfolio", [], {}, uid)["reply"]
    assert "Lakhs" in reply or "Crores" in reply
    assert _ban_western_scale(reply) == reply


def test_scrub_history_drops_computed_reply_and_its_question():
    history = [
        {"role": "user", "content": "what is a stock"},
        {"role": "assistant", "content": "A share of a company."},
        {"role": "user", "content": "how is my portfolio"},
        {"role": "assistant", "content": "You hold 1 stock. " + COMPUTED_REPLY_FOOTER},
        {"role": "user", "content": "thanks"},
    ]
    assert copilot_service._scrub_history(history) == [history[0], history[1], history[4]]


def test_computed_reply_in_history_never_reaches_an_llm(llm):
    deepseek, haiku = llm
    deepseek.side_effect = ["GENERAL", "A fine answer."]
    history = [
        {"role": "user", "content": "how is my portfolio"},
        {"role": "assistant", "content": "You hold 1 stock. Amount invested: ₹17,500. "
                                         "Largest by current value: TCS 100.0%. " + COMPUTED_REPLY_FOOTER},
    ]
    process_copilot_request("explain inflation", history, {}, 1)
    sent = json.dumps([c.args for c in deepseek.call_args_list] + [c.args for c in haiku.call_args_list], default=str)
    assert "TCS" not in sent and "17,500" not in sent and COMPUTED_REPLY_FOOTER not in sent


def test_route_portfolio_works_over_cap_and_hello_gets_429(client, auth_headers, test_user_id, llm, monkeypatch):
    deepseek, _ = llm
    monkeypatch.setattr(llm_budget, "_global_cache", None)
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "1000000")
    for tier in ("FREE", "PRO", "SUPER_PRO"):
        monkeypatch.setenv(f"LLM_USER_DAILY_BUDGET_USD_{tier}", "1")
    monkeypatch.setattr(copilot_service, "_yf_price", lambda _sym: (None, None))
    with database.get_session() as session:
        start_id = session.query(func.max(LlmUsage.id)).scalar() or 0
        session.add(LlmUsage(user_id=test_user_id, feature="test", model="claude-sonnet-4-6", cost_usd=5.0))
        session.commit()
    try:
        ok = client.post("/api/v1/copilot/chat", json={"user_message": "How is my portfolio doing?"},
                         headers=auth_headers)
        assert ok.status_code == 200
        assert ok.json()["reply_source"] == "computed"
        blocked = client.post("/api/v1/copilot/chat", json={"user_message": "hello"}, headers=auth_headers)
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["error_code"] == "AI_QUOTA_EXCEEDED"
        deepseek.assert_not_called()
        assert client.post("/api/v1/copilot/chat", json={"user_message": "hello"}).status_code == 401
    finally:
        with database.get_session() as session:
            session.query(LlmUsage).filter(LlmUsage.id > start_id).delete()
            session.commit()
