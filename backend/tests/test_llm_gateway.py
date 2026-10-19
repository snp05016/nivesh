"""ARCH-03: services/llm_utils is the only LLM client factory, and every call is token-logged."""
import asyncio
import random
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

import database
import helpers
from models.db_models import Portfolio, User
from services import copilot_service, llm_utils, portfolio_snapshot
from services.kyc_consent_service import AI_PROCESSING_CONSENT, record_consent

_BACKEND = Path(__file__).resolve().parent.parent
_SKIP_DIRS = {"tradingagents-core", "tests", "venv", ".venv", "__pycache__", "node_modules"}
_CLIENT_CTOR = re.compile(r"\banthropic\.Anthropic\(|\bOpenAI\(")


def test_llm_clients_constructed_only_in_llm_utils():
    offenders = []
    for path in _BACKEND.rglob("*.py"):
        rel = path.relative_to(_BACKEND)
        if _SKIP_DIRS & set(rel.parts) or (len(rel.parts) == 1 and rel.name.startswith("test_")):
            continue
        if rel.as_posix() != "services/llm_utils.py" and _CLIENT_CTOR.search(path.read_text(errors="ignore")):
            offenders.append(rel.as_posix())
    assert offenders == [], f"Build LLM clients via services/llm_utils: {offenders}"


def test_claude_messages_logs_usage_and_retries(monkeypatch):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    resp = SimpleNamespace(usage=usage, content=[SimpleNamespace(text="ok")])
    client = MagicMock()
    client.messages.create.side_effect = [RuntimeError("transient"), resp]
    monkeypatch.setattr(llm_utils, "get_anthropic_client", lambda: client)
    monkeypatch.setattr(llm_utils, "_time", SimpleNamespace(sleep=lambda _s: None))
    log = MagicMock()
    monkeypatch.setattr(helpers, "_log_token_usage", log)

    out = llm_utils.claude_messages(model="m", messages=[{"role": "user", "content": "hi"}],
                                    max_tokens=10, feature="x", system="s")

    assert out is resp
    assert client.messages.create.call_count == 2
    assert client.messages.create.call_args.kwargs["system"] == "s"
    log.assert_called_once_with("x", usage, "m")


def test_deepseek_chat_logs_without_endpoint(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=3, completion_tokens=2)
    message = SimpleNamespace(content="hello", reasoning_content=None)
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=message)])
    monkeypatch.setattr(llm_utils, "get_deepseek_client", lambda: client)
    log = MagicMock()
    monkeypatch.setattr(helpers, "_log_token_usage", log)

    assert llm_utils.deepseek_chat([{"role": "user", "content": "hi"}]) == "hello"
    log.assert_called_once_with("deepseek_unlabelled", usage, llm_utils.DEEPSEEK_MODEL)


def test_copilot_haiku_goes_through_gateway(monkeypatch):
    gateway = MagicMock(return_value=SimpleNamespace(content=[SimpleNamespace(text="reply")]))
    monkeypatch.setattr(copilot_service, "claude_messages", gateway)

    reply = copilot_service.claude_haiku([{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}])

    assert reply == "reply"
    kwargs = gateway.call_args.kwargs
    assert kwargs["feature"] == "copilot_haiku"
    assert kwargs["system"] == copilot_service._SYSTEM_PROMPT  # LLM-13: never message-supplied
    assert kwargs["messages"] == [{"role": "user", "content": "q"}]


def test_pregen_morning_brief_passes_messages_list(monkeypatch):
    uid = random.randint(40_000_000, 49_999_999)
    marker = f"Gateway Probe {uid}"
    with database.get_session() as session:
        session.add(User(id=uid, username=f"gateway_{uid}", password_hash="x", display_name="Gateway Test"))
        session.add(Portfolio(user_id=uid, ticker="RELIANCE", company_name=marker,
                              shares=10, buy_price=2500.0, group_name="holdings"))
        session.commit()
    record_consent(uid, AI_PROCESSING_CONSENT, True)

    llm = MagicMock(return_value='{"summary": "• x", "movers": [], "mood": "positive"}')
    monkeypatch.setattr("services.llm_utils.deepseek_chat", llm)
    ticker = SimpleNamespace(history=lambda period="2d": pd.DataFrame({"Close": [2600.0, 2652.0]}))
    monkeypatch.setattr(portfolio_snapshot, "yf", SimpleNamespace(Ticker=lambda symbol: ticker))

    asyncio.run(portfolio_snapshot.pregen_morning_briefs_all_users())

    calls = [c for c in llm.call_args_list if marker in str(c)]
    assert len(calls) == 1
    messages = calls[0].args[0]
    assert isinstance(messages, list) and messages[0]["role"] == "user"
    assert calls[0].kwargs["log_endpoint"] == "morning_brief_pregen"
