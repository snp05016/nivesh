"""services/model_canary outcome matrix; no real LLM call is ever made."""
import pytest

from services import llm_utils, model_canary
from services.model_canary import CanaryFailure


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("CANARY_ENABLED", raising=False)
    monkeypatch.delenv("CANARY_EXTRA_MODELS", raising=False)


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(llm_utils, "deepseek_chat", lambda messages, **kw: seen.append(("deepseek", kw)) or "x")
    monkeypatch.setattr(llm_utils, "claude_messages", lambda **kw: seen.append(("claude", kw)))
    return seen


def test_disabled_makes_no_calls(keys, calls, monkeypatch):
    monkeypatch.setenv("CANARY_ENABLED", "0")
    assert model_canary.run_model_canary() == {"skipped": "disabled"}
    assert calls == []


def test_all_providers_pinged_with_one_token(keys, calls, monkeypatch):
    monkeypatch.setenv("CANARY_EXTRA_MODELS", "claude-extra-1, ")
    out = model_canary.run_model_canary()
    assert set(out["models"].values()) == {"ok"}
    assert llm_utils.DEEPSEEK_MODEL in out["models"] and "claude-extra-1" in out["models"]
    assert calls and all(kw["max_tokens"] == 1 for _p, kw in calls)
    assert {p for p, _ in calls} == {"deepseek", "claude"}


def test_missing_key_skipped(keys, calls, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    out = model_canary.run_model_canary()
    assert out["models"][llm_utils.HAIKU_MODEL] == "skipped_no_key"
    assert out["models"][llm_utils.DEEPSEEK_MODEL] == "ok"
    assert {p for p, _ in calls} == {"deepseek"}


def test_budget_exceeded_is_not_a_failure(keys, monkeypatch):
    def over(**_kw):
        raise model_canary.LlmBudgetExceeded("cap")

    monkeypatch.setattr(llm_utils, "deepseek_chat", lambda *a, **k: "x")
    monkeypatch.setattr(llm_utils, "claude_messages", over)
    out = model_canary.run_model_canary()
    assert out["models"][llm_utils.SONNET_MODEL] == "skipped_budget"


def test_failing_model_raises_naming_it(keys, monkeypatch):
    def gone(**_kw):
        raise RuntimeError("model not found")

    monkeypatch.setattr(llm_utils, "deepseek_chat", lambda *a, **k: "x")
    monkeypatch.setattr(llm_utils, "claude_messages", gone)
    with pytest.raises(CanaryFailure) as exc:
        model_canary.run_model_canary()
    assert llm_utils.HAIKU_MODEL in str(exc.value) and "model not found" not in str(exc.value)
