"""LLM-04: the reformatter sees the agents' reports and the live market data, and the
price a report shows and logs is the live quote, never an LLM number.

Before the fix run_trading_agents kept only the graph's one-word rating and the
reformatter got the last 2,000 characters of its input (quant JSON + pledging).
"""
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

import database
from models.db_models import AnalysisPrediction

_BACKEND = Path(__file__).resolve().parent.parent
_WITHHELD = "Target withheld: inconsistent with signal"


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


@pytest.fixture
def full_run(orch, monkeypatch):
    """analyze() through the real run_trading_agents and reformat_with_deepseek; the agent
    graph, data layer and DeepSeek are stubbed. Returns run(ticker) -> (result, captured)."""

    class _UsageHandler:
        def __init__(self):
            self.usage_metadata = {}

    callbacks_mod = types.ModuleType("langchain_core.callbacks")
    setattr(callbacks_mod, "UsageMetadataCallbackHandler", _UsageHandler)
    monkeypatch.setitem(sys.modules, "langchain_core.callbacks", callbacks_mod)

    class _FakeGraph:
        def __init__(self, *args, **kwargs):
            pass

        def propagate(self, ticker, date):
            final_state = {
                "final_trade_decision": "FTD ROE 17.3% SENTINEL",
                "fundamentals_report": "FUND SENTINEL",
            }
            return final_state, "Hold"  # the vendored graph's decision is one word

    class _FakeQuantEngine:
        def __init__(self, ticker):
            pass

        async def run_full_pipeline(self):
            # Long enough that a 2,000-char tail of the input is quant JSON + pledging only.
            return {"market_regime": "Stable", "calibrated_confidence": 0.5, "notes": "q" * 3000}

    captured: dict = {}

    def _fake_deepseek_chat(messages, **kwargs):
        captured["user"] = messages[-1]["content"]
        return json.dumps({
            "signal": "BULLISH",
            "confidence_pct": 70,
            "governance_score": 80,  # below 40 the hierarchy cap turns BULLISH into HOLD
            "current_price_inr": 999,  # invented by the LLM
            "target_prices": {"short_term_3m": 1100, "medium_term_12m": 1400, "long_term_36m": 0},
            "upside_downside_pct": {"short_term": 10.1, "medium_term": 40.1, "long_term": 0},
            "what_to_watch": [],
        })

    monkeypatch.setattr(orch, "DEFAULT_CONFIG", {})
    monkeypatch.setattr(orch, "OptimizedTradingAgentsGraph", _FakeGraph)
    monkeypatch.setattr("services.quant_engine.QuantitativeEngine", _FakeQuantEngine)
    monkeypatch.setattr(orch, "_deepseek_chat", _fake_deepseek_chat)
    monkeypatch.setattr(orch, "_yf_price", lambda sym: (1234.5, None))
    monkeypatch.setattr(orch, "_yf_fetch_info", lambda *args, **kwargs: {})
    # The prefetch fails fast (no history / fast_info), so the live price comes from _yf_price.
    monkeypatch.setattr(orch.yf, "Ticker", lambda *args, **kwargs: type("T", (), {"major_holders": ""})())
    monkeypatch.setattr(orch, "get_analysis_for_date", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch, "get_all_ticker_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(orch, "_run_calibration_pipeline", lambda ticker, fs, raw: raw)
    monkeypatch.setattr(orch, "_inject_piotroski", lambda *args, **kwargs: None)
    # Identity: the result is what was persisted, not the final live refresh.
    monkeypatch.setattr(orch, "_inject_live_data", lambda result, ticker: result)

    def run(ticker: str):
        return orch.analyze(ticker, "NSE", scan_type="standard"), captured

    return run


def test_reformatter_receives_agent_reports(full_run):
    _, captured = full_run("LLMFOURA")
    prompt = captured["user"]
    assert "FTD ROE 17.3% SENTINEL" in prompt
    assert "FUND SENTINEL" in prompt
    assert "RATING:\nHold" in prompt
    assert "LIVE MARKET DATA" in prompt and "Last price (INR): 1234.50" in prompt


def test_prediction_entry_price_is_live_quote(full_run, monkeypatch):
    # Target grounding only applies when targets are served (REG-02 strips them by default).
    monkeypatch.setenv("ADVISORY_OUTPUT_ENABLED", "true")
    result, _ = full_run("LLMFOURB")
    assert result["current_price_inr"] == 1234.5
    assert result["current_price_source"] == "live_quote"
    # BULLISH with a 3M target below the live price: withheld, not shown as upside.
    assert result["target_prices"]["short_term_3m"] == 0.0
    assert _WITHHELD in result["what_to_watch"]
    assert result["upside_downside_pct"]["medium_term"] == round((1400 / 1234.5 - 1) * 100, 2)
    with database.get_session() as session:
        row: Any = (
            session.query(AnalysisPrediction)
            .filter(AnalysisPrediction.symbol == "LLMFOURB")
            .order_by(AnalysisPrediction.id.desc())
            .first()
        )
        assert row is not None
        assert row.entry_price == 1234.5


def test_ground_numbers_rejects_contradicting_target(orch):
    bull = orch._ground_numbers({"signal": "BULLISH", "target_prices": {"short_term_3m": 90}}, 100)
    assert bull["target_prices"]["short_term_3m"] == 0.0
    assert bull["upside_downside_pct"]["short_term"] == 0.0
    assert bull["what_to_watch"] == [_WITHHELD]

    bear = orch._ground_numbers({"signal": "BEARISH", "target_prices": {"medium_term_12m": 120}}, 100)
    assert bear["target_prices"]["medium_term_12m"] == 0.0
    assert bear["upside_downside_pct"]["medium_term"] == 0.0
    assert bear["what_to_watch"] == [_WITHHELD]


def test_upside_recomputed_from_live_price(orch):
    given = {
        "signal": "BULLISH",
        "current_price_inr": 55.0,
        "target_prices": {"medium_term_12m": 110},
        "upside_downside_pct": {"medium_term": 99.0},
    }
    out = orch._ground_numbers(dict(given), 100)
    assert out["current_price_inr"] == 100.0
    assert out["current_price_source"] == "live_quote"
    assert out["upside_downside_pct"]["medium_term"] == 10.0
    assert out["what_to_watch"] == []
    assert given["upside_downside_pct"] == {"medium_term": 99.0}  # nested input untouched


def test_no_live_price_means_no_price_or_upside(orch):
    out = orch._ground_numbers({
        "signal": "HOLD",
        "current_price_inr": 3412.0,
        "target_prices": {"medium_term_12m": 3900},
        "upside_downside_pct": {"medium_term": 14.3},
    }, None)
    assert out["current_price_inr"] == 0.0
    assert out["current_price_source"] == "unavailable"
    assert out["upside_downside_pct"]["medium_term"] == 0.0


def test_live_refresh_regrounds_cached_report(orch, monkeypatch):
    """Cache hits get a fresh price from _inject_live_data; upside must follow it."""
    monkeypatch.setattr(orch, "_yf_price", lambda sym: (200.0, None))
    cached = {
        "signal": "BULLISH",
        "current_price_inr": 150.0,
        "target_prices": {"medium_term_12m": 220.0},
        "upside_downside_pct": {"medium_term": 46.7},
    }
    out = orch._inject_live_data(cached, "TCS")
    assert out["current_price_inr"] == 200.0
    assert out["current_price_source"] == "live_quote"
    assert out["upside_downside_pct"]["medium_term"] == 10.0
    assert cached["current_price_inr"] == 150.0  # caller's dict untouched (task 53)
    assert cached["upside_downside_pct"]["medium_term"] == 46.7


def test_live_block_marks_missing_values_unavailable(orch, monkeypatch):
    fast_info = SimpleNamespace(last_price=2500.0, year_high=3000.0, year_low=None, market_cap=1.5e12)
    price, block = orch._live_market_data(fast_info, "TCS")
    assert price == 2500.0
    assert "Last price (INR): 2500.00" in block
    assert "52-week high (INR): 3000.00" in block
    assert "52-week low (INR): unavailable" in block
    assert "Market cap: ₹150,000.00 Crores" in block

    monkeypatch.setattr(orch, "_yf_price", lambda sym: (777.0, None))
    price, block = orch._live_market_data(None, "TCS")  # no prefetch: price from _yf_price
    assert price == 777.0
    assert "Market cap: unavailable" in block


def test_prompt_takes_numbers_only_from_data():
    # conftest mocks the prompts module, so read the real source from disk.
    base = (_BACKEND / "prompts.py").read_text(encoding="utf-8").split("EXTREME_ADDENDUM", 1)[0]
    assert "NAME & NUMBER CONSTRAINT" not in base
    assert "Only cite numbers that appear verbatim in the provided data blocks" in base
    assert 'copy "Last price" from LIVE MARKET DATA' in base
