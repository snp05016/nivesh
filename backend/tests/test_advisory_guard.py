"""REG-02: no price targets or buy/sell instructions leave the server by default.

Nivesh is not a SEBI-registered Research Analyst or Investment Adviser. Report targets,
upside and target bands are zeroed unless ADVISORY_OUTPUT_ENABLED is set, and the
prompts that write user-facing text carry NON_ADVISORY_RULES instead of an advisor persona.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.advisory_guard import NON_ADVISORY_RULES, TARGETS_WITHHELD_NOTE

_BACKEND = Path(__file__).resolve().parent.parent
_ADVISORY_PHRASES = (
    "market advisor", "wealth advisor", "financial advisor for", "name the ticker",
    "overall recommendation", "buy/sell recommendation",
)
_QUANT = {"conformal_target_upper_3m": 520.0, "conformal_target_lower_3m": 380.0}


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


def _report() -> dict:
    return {
        "ticker": "TCS",
        "company_name": "Tata Consultancy Services",
        "signal": "BULLISH",
        "confidence_pct": 60,
        "governance_score": 80,
        "current_price_inr": 400.0,
        "target_prices": {"short_term_3m": 500, "medium_term_12m": 600, "long_term_36m": 900},
        "upside_downside_pct": {"short_term": 25.0, "medium_term": 50.0, "long_term": 125.0},
        "target_price_bounds": {
            "medium_term_12m": {"lower": 550, "mid": 600, "upper": 650, "coverage_pct": 90},
        },
        "disclaimer": "AI-generated analysis.",
    }


def test_targets_stripped_by_default(orch, monkeypatch):
    monkeypatch.delenv("ADVISORY_OUTPUT_ENABLED", raising=False)

    r = orch._normalize_response(_report(), quant_payload=_QUANT)

    assert r["target_prices"] == {"short_term_3m": 0.0, "medium_term_12m": 0.0, "long_term_36m": 0.0}
    assert r["upside_downside_pct"] == {"short_term": 0.0, "medium_term": 0.0, "long_term": 0.0}
    for band in r["target_price_bounds"].values():
        assert (band["lower"], band["mid"], band["upper"]) == (0.0, 0.0, 0.0)
    assert r["conformal_target_upper_3m"] is None
    assert r["conformal_target_lower_3m"] is None
    # Re-normalizing (cache hits) keeps one note, not one per pass.
    again = orch._normalize_response(dict(r), quant_payload=_QUANT)
    assert again["disclaimer"].count(TARGETS_WITHHELD_NOTE) == 1


def test_targets_kept_when_enabled(orch, monkeypatch):
    monkeypatch.setenv("ADVISORY_OUTPUT_ENABLED", "true")

    r = orch._normalize_response(_report(), quant_payload=_QUANT)

    assert r["target_prices"] == {"short_term_3m": 500.0, "medium_term_12m": 600.0, "long_term_36m": 900.0}
    assert r["upside_downside_pct"]["medium_term"] == 50.0
    assert r["target_price_bounds"]["medium_term_12m"]["mid"] == 600.0
    assert r["conformal_target_upper_3m"] == 520.0
    assert TARGETS_WITHHELD_NOTE not in r["disclaimer"]


def _extreme_report() -> dict:
    r = _report()
    r["scenarios"] = {
        "bull": {"price_3m": 3100, "price_12m": 3600, "price_36m": 4500, "probability_pct": 25},
        "base": {"price_3m": 2950, "price_12m": 3200, "price_36m": 3800, "probability_pct": 50},
        "bear": {"price_3m": 2600, "price_12m": 2400, "price_36m": 2000, "probability_pct": 25},
    }
    r["valuation_bands"] = {"current_price": 2850, "fair_value": 3100, "bull_value": 3600,
                            "bear_value": 2400, "method": "DCF", "pe_band": {"low": 22, "mid": 28}}
    return r


def test_extreme_scenarios_and_fair_value_stripped_by_default(orch, monkeypatch):
    monkeypatch.delenv("ADVISORY_OUTPUT_ENABLED", raising=False)

    r = orch._normalize_response(_extreme_report(), "extreme")

    # iOS hides SCENARIO ANALYSIS when bull/base/bear decode as nil.
    assert r["scenarios"] == {}
    bands = r["valuation_bands"]
    assert (bands["fair_value"], bands["bull_value"], bands["bear_value"]) == (None, None, None)
    assert bands["current_price"] == 2850
    assert bands["method"] == "DCF"
    assert bands["pe_band"] == {"low": 22, "mid": 28}
    # A standard scan never gains the extreme-only keys.
    std = orch._normalize_response(_report(), "standard")
    assert "scenarios" not in std and "valuation_bands" not in std


def test_extreme_scenarios_and_fair_value_kept_when_enabled(orch, monkeypatch):
    monkeypatch.setenv("ADVISORY_OUTPUT_ENABLED", "true")

    r = orch._normalize_response(_extreme_report(), "extreme")

    assert r["scenarios"]["bull"]["price_12m"] == 3600
    assert r["scenarios"]["base"]["price_3m"] == 2950
    assert r["valuation_bands"]["fair_value"] == 3100
    assert r["valuation_bands"]["bear_value"] == 2400


def test_excel_history_has_no_target_columns_by_default(monkeypatch):
    """openpyxl is a MagicMock in conftest, so check the header builder directly."""
    import routers.portfolio_exports as exports

    monkeypatch.delenv("ADVISORY_OUTPUT_ENABLED", raising=False)
    headers = exports._history_headers()
    assert not any("target" in h.lower() for h in headers)
    assert exports._history_row(("2026-10-01", "TCS", "BULLISH", 60, 500, 600, 900)) == [
        "2026-10-01", "TCS", "BULLISH", 60]

    monkeypatch.setenv("ADVISORY_OUTPUT_ENABLED", "true")
    assert sum("Target" in h for h in exports._history_headers()) == 3
    assert exports._history_row(("2026-10-01", "TCS", "BULLISH", 60, 500, 600, 900))[-1] == 900


def test_no_advisory_persona_in_prompts():
    hits = []
    for folder in ("routers", "services"):
        for path in (_BACKEND / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            hits += [f"{path.relative_to(_BACKEND)}: {p}" for p in _ADVISORY_PHRASES if p in text]
    assert hits == []


def test_daily_action_prompt_non_advisory(client, auth_headers, test_user_id, monkeypatch):
    import routers.analysis as analysis

    prompts = []

    def _fake_chat(messages, **_kwargs):
        prompts.append(messages[-1]["content"])
        return "No holdings had alerts or signal changes today."

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(analysis, "has_active_consent", lambda *_a, **_k: True)
    monkeypatch.setattr(analysis.llm_budget, "guard", lambda *_a, **_k: None)
    monkeypatch.setattr(analysis, "_deepseek_chat", _fake_chat)

    resp = client.get(f"/daily-action/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert len(prompts) == 1
    assert NON_ADVISORY_RULES in prompts[0]
    assert "should do" not in prompts[0].lower()
    assert "name the ticker" not in prompts[0].lower()
    assert resp.json()["action"] == "No holdings had alerts or signal changes today"


def test_copilot_answers_buy_sell_requests_without_advice(monkeypatch):
    from services import copilot_service

    calls = []

    def _intent_only(messages):
        calls.append(messages)
        return "ADVICE"

    monkeypatch.setattr(copilot_service, "deepseek_chat", _intent_only)
    monkeypatch.setattr(copilot_service, "claude_haiku", lambda messages: pytest.fail("no LLM answer expected"))

    res = copilot_service.process_copilot_request("Should I buy TCS today?", [], {}, 5)

    assert res["reply"] == copilot_service.NOT_ADVICE_REPLY
    assert len(calls) == 1  # the intent router only; no model writes the answer
