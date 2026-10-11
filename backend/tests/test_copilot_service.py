"""Copilot intents: PORTFOLIO reads real columns (REL-24); DEEP_ANALYSIS never spawns (REL-22)."""
import random

import pytest


@pytest.fixture
def portfolio_user():
    import database
    from models.db_models import Portfolio, User

    uid = random.randint(40_000_000, 49_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"test_copilot_{uid}", password_hash="x",
                         display_name="Copilot Test"))
        session.commit()
        session.add_all([
            Portfolio(user_id=uid, ticker="TCS", company_name="TCS", shares=5,
                      buy_price=3500, group_name="holdings"),
            Portfolio(user_id=uid, ticker="INFY", company_name="Infosys", shares=0,
                      buy_price=0, group_name="watchlist"),
        ])
        session.commit()
    yield uid
    with database.get_session() as session:
        session.query(Portfolio).filter(Portfolio.user_id == uid).delete()
        session.query(User).filter(User.id == uid).delete()
        session.commit()


def test_portfolio_intent_uses_shares(monkeypatch, portfolio_user):
    from services import copilot_service

    captured = []
    monkeypatch.setattr(copilot_service, "deepseek_chat", lambda messages: "PORTFOLIO")
    # FINSEC-04 gate: holdings reach the LLM only with AI-processing consent.
    monkeypatch.setattr(copilot_service, "has_active_consent", lambda *_a, **_k: True)
    monkeypatch.setattr(copilot_service, "claude_haiku",
                        lambda messages: captured.append(messages) or "ok")

    res = copilot_service.process_copilot_request("how is my portfolio", [], {}, portfolio_user)

    assert res["reply"] == "ok"
    prompt = captured[0][-1]["content"]
    assert "TCS (5 shares" in prompt
    assert "INFY" not in prompt


def test_deep_analysis_does_not_spawn(monkeypatch):
    import multiprocessing

    from services import copilot_service

    def no_process(*_args, **_kwargs):
        raise AssertionError("copilot must not spawn an analysis process")

    replies = iter(["DEEP_ANALYSIS", "TCS"])
    monkeypatch.setattr(copilot_service, "deepseek_chat", lambda messages: next(replies))
    monkeypatch.setattr(copilot_service, "claude_haiku",
                        lambda messages: pytest.fail("no LLM synthesis expected"))
    monkeypatch.setattr(multiprocessing, "Process", no_process)

    res = copilot_service.process_copilot_request("analyse TCS", [], {}, 5)

    assert "TCS" in res["reply"]
    assert res["context_cards"] == [{"type": "open_analysis", "ticker": "TCS"}]
