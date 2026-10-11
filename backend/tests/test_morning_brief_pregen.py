"""REL-07: morning-brief pre-generation calls deepseek_chat with its real signature.

It used to `await deepseek_chat(prompt_str)`: the API rejected the string, the
retries slept 6 s, and every user ended in errors with no brief cached. This test
goes through the real deepseek_chat with only the OpenAI client faked.
"""
import asyncio
import random
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

import database
import services.disk_cache as disk_cache
import services.llm_utils as llm_utils
from models.db_models import Portfolio, User
from services import portfolio_snapshot
from services.kyc_consent_service import AI_PROCESSING_CONSENT, record_consent


def test_pregen_generates_with_real_client_signature(monkeypatch):
    uid = random.randint(10_000_000, 99_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"pregen_{uid}", password_hash="x", display_name="Pregen Test"))
        session.add(Portfolio(user_id=uid, ticker="TCS", company_name="TCS", shares=5,
                              buy_price=3000.0, group_name="holdings"))
        session.commit()
    record_consent(uid, AI_PROCESSING_CONSENT, True)

    sent_messages = []

    def _create(**kwargs):
        sent_messages.append(kwargs["messages"])
        msg = SimpleNamespace(content='{"summary":"• ok","movers":[],"mood":"positive"}',
                              reasoning_content=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])  # no usage: no token log

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = _create
    monkeypatch.setattr(llm_utils._openai_lib, "OpenAI", MagicMock(return_value=fake_client))
    monkeypatch.setattr(llm_utils._time, "sleep", lambda _s: None)  # a failing retry must not slow the test

    ticker = SimpleNamespace(history=lambda period="2d": pd.DataFrame({"Close": [3000.0, 3090.0]}))
    monkeypatch.setattr(portfolio_snapshot, "yf", SimpleNamespace(Ticker=lambda _sym: ticker))

    cached = {}
    monkeypatch.setattr(disk_cache, "set",
                        lambda ns, key, value, ttl=None: cached.__setitem__((ns, key), value))

    result = asyncio.run(portfolio_snapshot.pregen_morning_briefs_all_users())

    assert result["generated"] >= 1, result
    assert sent_messages and all(isinstance(m, list) for m in sent_messages)
    brief = cached.get(("morning_brief", str(uid)))
    assert brief is not None, f"no brief cached for {uid}: {result}"
    assert brief["summary"] == "• ok"
    assert brief["pregen"] is True
