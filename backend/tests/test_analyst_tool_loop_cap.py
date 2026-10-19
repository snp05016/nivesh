"""LLM-18: analyst_tool_loop_cap is enforced and output_language reaches the vendored agents.

Before the fix nothing read either key: an analyst that kept calling tools looped until
LangGraph's recursion limit, and the agents never saw the requested language.
"""
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def orch(monkeypatch):
    """services.orchestrator imported with its optional LangChain deps stubbed."""
    tools_mod = types.ModuleType("langchain_core.tools")
    setattr(tools_mod, "tool", lambda fn=None, **kwargs: fn if fn is not None else (lambda wrapped: wrapped))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "langchain_community", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_openai", MagicMock())
    import services.orchestrator as orchestrator
    return orchestrator


class _FakePrompt:
    def __or__(self, other):
        return other  # prompt | llm -> llm, so chain.invoke is the model's invoke


class _FakeLLM:
    def __init__(self):
        self.bound = 0

    def bind_tools(self, tools):
        self.bound += 1
        return SimpleNamespace(invoke=lambda _msgs: SimpleNamespace(tool_calls=[{"name": "x"}], content=""))

    def invoke(self, _msgs):
        return SimpleNamespace(tool_calls=[], content="REPORT")


@pytest.fixture
def node_env(orch, monkeypatch):
    human = []
    monkeypatch.setattr(orch, "ChatPromptTemplate", SimpleNamespace(from_messages=lambda _m: _FakePrompt()))
    monkeypatch.setattr(orch, "HumanMessage", lambda content: human.append(content) or content)
    monkeypatch.setattr(orch, "get_instrument_context_from_state", lambda _s: "")
    return orch, human


def _state(prior_tool_rounds):
    tool_round = SimpleNamespace(tool_calls=[{"name": "get_stock_data"}], content="")
    return {"messages": [tool_round] * prior_tool_rounds, "trade_date": "2026-01-01"}


def test_analyst_writes_report_once_tool_budget_is_spent(node_env):
    orch, human = node_env
    llm = _FakeLLM()
    node = orch.create_optimized_analyst_node(llm, "persona", "market", [], tool_loop_cap=2)

    out = node(_state(2))

    assert llm.bound == 0  # no tools bound, so the model cannot ask for another round
    assert out["market_report"] == "REPORT"
    assert "Tool budget exhausted" in human[-1]


def test_analyst_keeps_tools_under_the_cap(node_env):
    orch, human = node_env
    llm = _FakeLLM()
    node = orch.create_optimized_analyst_node(llm, "persona", "market", [], tool_loop_cap=2)

    out = node(_state(1))

    assert llm.bound == 1
    assert out["market_report"] == ""  # still mid tool loop
    assert "Tool budget exhausted" not in human[-1]


def test_build_ta_config_uses_the_keys_the_graph_reads(orch, monkeypatch):
    monkeypatch.setattr(orch, "DEFAULT_CONFIG", {})
    config = orch.build_ta_config(language="Hindi")
    assert config["output_language"] == "Hindi"
    assert "response_language" not in config
    assert config["max_tokens"] == 2000
    assert config["analyst_tool_loop_cap"] == 2
    assert orch.build_ta_config("extreme")["analyst_tool_loop_cap"] == 3
