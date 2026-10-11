"""LLM-09 / OPS-08: LLM spend telemetry prices every logged call per model (including
prompt-cache tokens), buckets by IST day, and logs the agent graph's LangChain calls."""
import ast
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import core.dashboard_state as ds
import routers.analysis as analysis_router


def _write_log(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


@pytest.fixture
def as_admin(monkeypatch):
    monkeypatch.setattr(analysis_router, "require_admin", lambda *_a, **_k: 1)


def test_token_stats_prices_by_model_and_ist_day(client, as_admin, tmp_path, monkeypatch):
    log = tmp_path / "token_log.jsonl"
    _write_log(log, [
        # Sonnet 4.6: 1M input = $3.00, plus 1M cache reads ($0.30) and 1M cache writes ($3.75)
        {"ts": "2026-10-09T10:00:00+00:00", "endpoint": "reformat", "model": "claude-sonnet-4-6",
         "input_tokens": 1_000_000, "output_tokens": 0,
         "cache_read_input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000},
        # 20:00 UTC on the 9th is 01:30 IST on the 10th. DeepSeek: $0.14 in + $0.28 out.
        {"ts": "2026-10-09T20:00:00+00:00", "endpoint": "graph_standard", "model": "deepseek-chat",
         "input_tokens": 1_000_000, "output_tokens": 1_000_000},
        # No model: counted, never priced.
        {"ts": "2026-10-10T05:00:00+00:00", "endpoint": "legacy", "input_tokens": 500, "output_tokens": 5},
        "not-a-dict",
    ])
    with open(log, "a") as f:
        f.write("{broken json\n")
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(log))
    monkeypatch.setenv("USD_INR_RATE", "90")

    resp = client.get("/token-stats")
    assert resp.status_code == 200
    data = resp.json()

    expected = 3.0 + 0.30 + 3.75 + 0.14 + 0.28
    assert data["total_cost_usd"] == pytest.approx(expected, rel=0.01)
    assert data["total_cost_inr"] == pytest.approx(expected * 90, rel=0.01)
    assert data["total_calls"] == 3
    assert data["unpriced_calls"] == 1
    assert data["cost_by_model"]["claude-sonnet-4-6"] == pytest.approx(7.05, rel=0.01)
    assert data["cost_by_model"]["deepseek-chat"] == pytest.approx(0.42, rel=0.01)
    assert data["most_expensive_endpoint"] == "reformat"
    days = {d["date"]: d for d in data["last_7_days"]}
    assert set(days) == {"2026-10-09", "2026-10-10"}
    assert days["2026-10-09"]["cost_usd"] == pytest.approx(7.05, rel=0.01)
    assert days["2026-10-10"]["calls"] == 2
    assert data["estimated_monthly_usd"] == pytest.approx(expected / 2 * 30, rel=0.01)
    # cache share of prompt tokens: 1M cached of 3,000,500 prompt tokens, never above 100%
    assert data["cache_hit_rate_pct"] == pytest.approx(1_000_000 / 3_000_500 * 100, rel=0.01)


def test_token_usage_summary_without_log_is_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(tmp_path / "missing.jsonl"))
    s = ds.token_usage_summary()
    assert s["total_cost_usd"] == 0.0
    assert s["total_calls"] == 0
    assert s["last_7_days"] == []
    assert s["estimated_monthly_usd"] == 0.0
    assert s["by_vendor"]["unknown"]["cost_usd"] is None


def test_main_has_no_duplicate_token_logger():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name)}
    assert "_log_token_usage" not in defined
    assert "_token_stats" not in assigned


def test_graph_usage_is_logged(tmp_path, monkeypatch):
    tools_mod = types.ModuleType("langchain_core.tools")
    setattr(tools_mod, "tool", lambda fn=None, **kwargs: fn if fn is not None else (lambda wrapped: wrapped))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "langchain_community", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_openai", MagicMock())
    import services.orchestrator as orchestrator

    class _Handler:
        def __init__(self):
            # LangChain's input_tokens include the cached prompt tokens.
            self.usage_metadata = {
                "deepseek-chat": {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500,
                                  "input_token_details": {"cache_read": 200}},
            }

    callbacks_mod = types.ModuleType("langchain_core.callbacks")
    setattr(callbacks_mod, "UsageMetadataCallbackHandler", _Handler)
    monkeypatch.setitem(sys.modules, "langchain_core.callbacks", callbacks_mod)

    seen = {}

    class _FakeGraph:
        def __init__(self, *args, **kwargs):
            seen["callbacks"] = kwargs.get("callbacks")

        def propagate(self, ticker, date):
            return {}, "HOLD"

    monkeypatch.setattr(orchestrator, "DEFAULT_CONFIG", {})
    monkeypatch.setattr(orchestrator, "OptimizedTradingAgentsGraph", _FakeGraph)
    log = tmp_path / "token_log.jsonl"
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(log))

    orchestrator.run_trading_agents("GRAPHTEST.NS", "2026-10-10", "standard")

    assert len(seen["callbacks"]) == 1
    entry = json.loads(log.read_text().strip())
    assert entry["endpoint"] == "graph_standard"
    assert entry["model"] == "deepseek-chat"
    assert entry["input_tokens"] == 1000
    assert entry["cache_read_input_tokens"] == 200
    assert entry["output_tokens"] == 300
