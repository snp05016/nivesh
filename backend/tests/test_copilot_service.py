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

    monkeypatch.setattr(copilot_service, "deepseek_chat", lambda messages: "PORTFOLIO")
    monkeypatch.setattr(copilot_service, "claude_haiku",
                        lambda messages: pytest.fail("the portfolio answer is computed, no LLM"))
    monkeypatch.setattr(copilot_service, "_yf_price", lambda _sym: (4000.0, None))

    res = copilot_service.process_copilot_request("how am I doing", [], {}, portfolio_user)

    assert res["reply_source"] == "computed"
    assert "You hold 1 stock." in res["reply"]
    assert "₹17,500" in res["reply"]      # 5 shares @ 3500
    assert "₹20,000" in res["reply"]      # 5 shares @ 4000
    assert "INFY" not in res["reply"]     # the watchlist row is excluded


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
