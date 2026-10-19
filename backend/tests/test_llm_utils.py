from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services import llm_utils
from services.llm_utils import contains_devanagari


def test_contains_devanagari_detects_hindi_text():
    assert contains_devanagari("प्रातःकालीन सारांश")


def test_contains_devanagari_allows_english_text():
    assert not contains_devanagari("Morning brief: market data loaded.")


# ── LLM-17: one SDK call, no stacked retries, caller's budget, no reasoning leak ──


class BadRequestError(Exception):
    """Stands in for openai.BadRequestError (the openai module is mocked in tests)."""


def _response(content="ok", reasoning=None):
    message = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=message, finish_reason="stop")])


@pytest.fixture
def ds_client(monkeypatch):
    client = MagicMock()
    client.chat.completions.create.return_value = _response()
    monkeypatch.setattr(llm_utils, "get_deepseek_client", lambda: client)
    sleep = MagicMock()
    monkeypatch.setattr(llm_utils, "_time", SimpleNamespace(sleep=sleep))
    return client, sleep


def test_bad_request_not_retried(ds_client):
    client, sleep = ds_client
    client.chat.completions.create.side_effect = BadRequestError("context length exceeded")

    with pytest.raises(BadRequestError):
        llm_utils.deepseek_chat([{"role": "user", "content": "hi"}])

    assert client.chat.completions.create.call_count == 1
    sleep.assert_not_called()


def test_max_tokens_passthrough(ds_client):
    client, _ = ds_client
    llm_utils.deepseek_chat([{"role": "user", "content": "hi"}], max_tokens=300)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["max_tokens"] == 300
    assert kwargs["model"] == llm_utils.DEEPSEEK_MODEL


def test_reasoner_headroom(ds_client):
    client, _ = ds_client
    llm_utils.deepseek_chat([{"role": "user", "content": "hi"}], max_tokens=1000,
                            model=llm_utils.DEEPSEEK_REASONER_MODEL)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["max_tokens"] == 9000
    assert "temperature" not in kwargs


def test_empty_content_returns_empty_not_reasoning(ds_client):
    client, _ = ds_client
    client.chat.completions.create.return_value = _response(content="", reasoning="chain of thought")
    assert llm_utils.deepseek_chat([{"role": "user", "content": "hi"}]) == ""


def test_client_singleton(monkeypatch):
    ctor = MagicMock()
    monkeypatch.setattr(llm_utils._openai_lib, "OpenAI", ctor)
    llm_utils.get_deepseek_client.cache_clear()

    assert llm_utils.get_deepseek_client() is llm_utils.get_deepseek_client()
    assert ctor.call_count == 1
    assert ctor.call_args.kwargs["max_retries"] == 2


@pytest.fixture
def reformat(monkeypatch, tmp_path):
    from services import orchestrator
    monkeypatch.chdir(tmp_path)  # dead-letter file lands in tmp
    claude = MagicMock(return_value={"signal": "HOLD", "from": "claude"})
    monkeypatch.setattr(orchestrator, "reformat_with_claude", claude)
    monkeypatch.setattr("time.sleep", MagicMock(side_effect=AssertionError("no sleeps")))
    return orchestrator, claude


def test_reformat_api_error_goes_straight_to_claude(reformat, monkeypatch):
    orchestrator, claude = reformat
    ds = MagicMock(side_effect=RuntimeError("503"))
    monkeypatch.setattr(orchestrator, "_deepseek_chat", ds)

    assert orchestrator.reformat_with_deepseek("RAW", "INFY.NS", "NSE")["from"] == "claude"
    assert ds.call_count == 1
    claude.assert_called_once()


def test_reformat_parse_failure_retried_once(reformat, monkeypatch):
    orchestrator, claude = reformat
    ds = MagicMock(return_value="not json at all")
    monkeypatch.setattr(orchestrator, "_deepseek_chat", ds)

    assert orchestrator.reformat_with_deepseek("RAW", "INFY.NS", "NSE")["from"] == "claude"
    assert ds.call_count == 2
    assert ds.call_args.kwargs["max_tokens"] == 4000
    claude.assert_called_once()


def test_reformat_wrong_shape_falls_back_to_claude(reformat, monkeypatch):
    orchestrator, claude = reformat
    ds = MagicMock(return_value='{"signal": 1}')  # parses, but .strip() on int raises
    monkeypatch.setattr(orchestrator, "_deepseek_chat", ds)

    assert orchestrator.reformat_with_deepseek("RAW", "INFY.NS", "NSE")["from"] == "claude"
    assert ds.call_count == 2
    claude.assert_called_once()
