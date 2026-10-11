"""FINSEC-04: no portfolio data reaches an LLM processor (DeepSeek/Anthropic)
without the opt-in 'ai_processing' consent; the newest consent row wins.

Hermetic: conftest's test DB, LLM clients mocked, yfinance replaced per test.
"""
import asyncio
import random
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

import database
from models.db_models import Portfolio, User
from services import portfolio_snapshot
from services.kyc_consent_service import (
    AI_PROCESSING_CONSENT,
    has_active_consent,
    record_consent,
    revoke_consent,
)


def _user_with_holding() -> int:
    """A user holding 10 RELIANCE bought at 2500, with a company name unique to it."""
    uid = random.randint(10_000_000, 99_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"consent_{uid}", password_hash="x", display_name="Consent Test"))
        session.add(Portfolio(user_id=uid, ticker="RELIANCE", company_name=f"Consent Probe {uid}",
                              shares=10, buy_price=2500.0, group_name="holdings"))
        session.commit()
    return uid


def test_has_active_consent_newest_row_wins():
    uid = _user_with_holding()
    assert has_active_consent(uid, AI_PROCESSING_CONSENT) is False

    record_consent(uid, "data_sharing", True)  # another consent type does not count
    assert has_active_consent(uid, AI_PROCESSING_CONSENT) is False

    record_consent(uid, AI_PROCESSING_CONSENT, True)
    assert has_active_consent(uid, AI_PROCESSING_CONSENT) is True
    record_consent(uid, AI_PROCESSING_CONSENT, False)  # what the iOS toggle sends to withdraw
    assert has_active_consent(uid, AI_PROCESSING_CONSENT) is False
    record_consent(uid, AI_PROCESSING_CONSENT, True)
    assert has_active_consent(uid, AI_PROCESSING_CONSENT) is True
    revoke_consent(uid, AI_PROCESSING_CONSENT)  # DELETE /api/kyc/consents/{type}
    assert has_active_consent(uid, AI_PROCESSING_CONSENT) is False


def test_pregen_skips_users_without_ai_consent(monkeypatch):
    uid = _user_with_holding()
    marker = f"Consent Probe {uid}"  # only prompts built for this user contain it

    llm = MagicMock(return_value='{"summary": "• x", "movers": [], "mood": "positive"}')
    monkeypatch.setattr("services.llm_utils.deepseek_chat", llm)
    ticker = SimpleNamespace(history=lambda period="2d": pd.DataFrame({"Close": [2600.0, 2652.0]}))
    monkeypatch.setattr(portfolio_snapshot, "yf", SimpleNamespace(Ticker=lambda symbol: ticker))

    def sent_for_user():
        # Assert on calls only (not on the awaited result), so this stays valid
        # whatever shape the LLM call takes.
        return [str(c) for c in llm.call_args_list if marker in str(c)]

    asyncio.run(portfolio_snapshot.pregen_morning_briefs_all_users())
    assert sent_for_user() == []

    record_consent(uid, AI_PROCESSING_CONSENT, True)
    asyncio.run(portfolio_snapshot.pregen_morning_briefs_all_users())
    sent = sent_for_user()
    assert len(sent) == 1
    assert "+6.1%" in sent[0]  # overall P&L %: (10*2652 - 10*2500) / 25000
    assert "₹" not in sent[0]  # minimised: no price or rupee P&L (both were ₹-prefixed)

    record_consent(uid, AI_PROCESSING_CONSENT, False)
    asyncio.run(portfolio_snapshot.pregen_morning_briefs_all_users())
    assert len(sent_for_user()) == 1


def test_morning_summary_no_llm_without_consent(client, auth_headers, test_user_id, monkeypatch):
    import anthropic

    record_consent(test_user_id, AI_PROCESSING_CONSENT, False)  # newest row: not consented
    fake_anthropic = MagicMock()
    monkeypatch.setattr(anthropic, "Anthropic", fake_anthropic)

    resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 200
    assert "AI processing" in resp.json()["summary"]
    fake_anthropic.assert_not_called()


def test_copilot_portfolio_intent_without_consent(monkeypatch):
    import services.copilot_service as copilot

    uid = _user_with_holding()
    monkeypatch.setattr(copilot, "deepseek_chat", MagicMock(return_value="PORTFOLIO"))
    haiku = MagicMock(return_value="should not be reached")
    monkeypatch.setattr(copilot, "claude_haiku", haiku)

    for user_id in (uid, None):  # no consent on file / unauthenticated
        res = copilot.process_copilot_request("How is my portfolio doing?", [], {}, user_id)
        assert "AI processing" in res["reply"]
    haiku.assert_not_called()
