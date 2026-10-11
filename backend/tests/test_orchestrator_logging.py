"""LLM-01: every analyze() path logged through `logging` without importing it (NameError), and
the debug graph run called a nonexistent `.pretty_logging` on each streamed message."""
import ast
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def orchestrator(monkeypatch):
    tools_mod = types.ModuleType("langchain_core.tools")
    setattr(tools_mod, "tool", lambda fn=None, **kwargs: fn if fn is not None else (lambda wrapped: wrapped))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "langchain_community", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_openai", MagicMock())
    import services.orchestrator as orch
    return orch


def _stub_sources(monkeypatch, orch, cached=None):
    monkeypatch.setattr(orch, "get_analysis_for_date", lambda *a, **k: cached)
    monkeypatch.setattr(orch, "get_all_ticker_history", lambda *a, **k: [])
    monkeypatch.setattr(orch, "_inject_piotroski", lambda *a, **k: None)
    monkeypatch.setattr(orch, "_inject_live_data", lambda result, ticker: result)


def test_orchestrator_binds_logging_at_module_scope():
    tree = ast.parse((BACKEND / "services" / "orchestrator.py").read_text())
    assert any(isinstance(n, ast.Import) and any(a.name == "logging" for a in n.names) for n in tree.body)
    # A function-local `import logging` makes the name local to the whole function, so any
    # logging call above it raises UnboundLocalError.
    local = [
        n.lineno
        for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
        for n in ast.walk(f) if isinstance(n, ast.Import) and any(a.name == "logging" for a in n.names)
    ]
    assert local == []


def test_analyze_cache_miss_runs_without_nameerror(orchestrator, monkeypatch):
    _stub_sources(monkeypatch, orchestrator)
    monkeypatch.setattr(orchestrator, "_yf_fetch_info", lambda *a, **k: {})
    monkeypatch.setattr(orchestrator.yf, "Ticker", lambda *a, **k: types.SimpleNamespace(major_holders=""))
    monkeypatch.setattr(orchestrator, "run_trading_agents", lambda *a, **k: ("RAW", [], {}))
    monkeypatch.setattr(orchestrator, "_run_calibration_pipeline", lambda ticker, final_state, raw, *_a: raw)
    monkeypatch.setattr(orchestrator, "reformat_with_deepseek", lambda *a, **k: {"signal": "HOLD", "confidence_pct": 50})

    class _FailingQuantEngine:  # its except handler logs as well
        def __init__(self, ticker):
            raise RuntimeError("quant engine down")

    quant_mod = types.ModuleType("services.quant_engine")
    setattr(quant_mod, "QuantitativeEngine", _FailingQuantEngine)
    monkeypatch.setitem(sys.modules, "services.quant_engine", quant_mod)

    result = orchestrator.analyze("LOGMISS", "NSE", user_id=None)

    assert result["_cache_type"] == "FULL AI"
    assert result["signal"] == "HOLD"


def test_analyze_cache_hit_path(orchestrator, monkeypatch):
    _stub_sources(monkeypatch, orchestrator, cached={"signal": "HOLD", "confidence_pct": 50})

    result = orchestrator.analyze("LOGHIT", "NSE", user_id=None)

    assert result["_cache_type"] == "CACHE HIT"
    assert result["signal"] == "HOLD"


def test_run_trading_agents_uses_debug_false(orchestrator, monkeypatch):
    class _Handler:
        usage_metadata = {}

    callbacks_mod = types.ModuleType("langchain_core.callbacks")
    setattr(callbacks_mod, "UsageMetadataCallbackHandler", _Handler)
    monkeypatch.setitem(sys.modules, "langchain_core.callbacks", callbacks_mod)
    seen = {}

    class _FakeGraph:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)

        def propagate(self, ticker, date):
            return {}, "HOLD"

    monkeypatch.setattr(orchestrator, "DEFAULT_CONFIG", {})
    monkeypatch.setattr(orchestrator, "OptimizedTradingAgentsGraph", _FakeGraph)

    orchestrator.run_trading_agents("LOGDBG.NS", "2026-10-10", "standard")

    assert seen["debug"] is False


def test_vendored_graph_has_no_pretty_logging():
    src = (BACKEND / "tradingagents-core" / "tradingagents" / "graph" / "trading_graph.py").read_text()
    assert "pretty_logging" not in src
