"""LLM-16: the smart-cache gate reuses a prior report only on an exact "NO", only
from the requested tier, only within SMART_CACHE_MAX_AGE_DAYS, and never re-dates it."""
import json
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

TICKER = "GATEFIX"


@pytest.mark.parametrize("answer, reuse", [
    ("NO", True),
    ("no.", True),
    ('"NO"', True),
    ("  No  ", True),
    ("YES", False),
    ("YES, NEW ANNOUNCEMENT", False),
    ("YES - QUARTERLY RESULTS ANNOUNCEMENT", False),
    ("UNKNOWN", False),
    ("NOT CLEAR", False),
    ("ECONOMIC SHOCK", False),
    ("", False),
    (None, False),
])
def test_gate_parser_needs_exact_no(orch, answer, reuse):
    assert orch._smart_cache_says_no_change(answer) is reuse


class _Stop(Exception):
    """Raised when analyze() falls through to a full run."""


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
def gate(orch, monkeypatch):
    """analyze() stubbed up to the smart-cache gate; returns (orch, captured, set_prior_age)."""
    captured: dict = {"history_kwargs": None, "saved": [], "gate_calls": 0}
    today = datetime.strptime(orch.ist_today().strftime("%Y-%m-%d"), "%Y-%m-%d")
    prior: list = []

    def set_prior_age(days: int) -> str:
        date_str = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        prior[:] = [{"ticker": TICKER, "exchange": "NSE", "company_name": TICKER,
                     "analysis_date": date_str, "signal": "HOLD", "confidence_pct": 55}]
        return date_str

    def _history(*args, **kwargs):
        captured["history_kwargs"] = kwargs
        return list(prior)

    def _save(session, user_id, ticker, result, raw_output=None, scan_type="standard"):
        captured["saved"].append(scan_type)
        return result

    def _chat(*args, **kwargs):
        if kwargs.get("log_endpoint") == "smart_cache":
            captured["gate_calls"] += 1
        return "NO"

    def _full_run(*args, **kwargs):
        raise _Stop()

    class _FailingQuantEngine:
        def __init__(self, ticker):
            raise RuntimeError("quant engine disabled in this test")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "placeholder")
    monkeypatch.setattr(orch, "get_analysis_for_date", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch, "get_all_ticker_history", _history)
    monkeypatch.setattr(orch, "save_analysis", _save)
    monkeypatch.setattr(orch, "_deepseek_chat", _chat)
    monkeypatch.setattr(orch, "_inject_live_data", lambda result, ticker: result)
    monkeypatch.setattr(orch, "run_trading_agents", _full_run)
    monkeypatch.setattr(orch, "_yf_fetch_info", lambda *args, **kwargs: {})
    monkeypatch.setattr("services.quant_engine.QuantitativeEngine", _FailingQuantEngine)
    monkeypatch.setattr(
        orch.yf, "Ticker",
        lambda *args, **kwargs: type("T", (), {"major_holders": "", "news": [{"title": "Board meeting scheduled"}]})(),
    )
    return orch, captured, set_prior_age, today.strftime("%Y-%m-%d")


def test_deep_reuse_stays_deep_and_keeps_its_date(gate):
    orch, captured, set_prior_age, today = gate
    yesterday = set_prior_age(1)

    result = orch.analyze(TICKER, "NSE", scan_type="deep")

    assert captured["history_kwargs"].get("scan_type") == "deep"
    assert captured["gate_calls"] == 1
    assert captured["saved"] == ["deep"]
    assert result["analysis_date"] == yesterday
    assert result["reused_from"] == yesterday
    assert result["checked_at"] == today
    assert result["deep_scan_used"] is True


def test_prior_older_than_max_age_is_regenerated(gate):
    orch, captured, set_prior_age, _ = gate
    set_prior_age(orch.SMART_CACHE_MAX_AGE_DAYS + 3)

    with pytest.raises(_Stop):
        orch.analyze(TICKER, "NSE", scan_type="standard")

    assert captured["gate_calls"] == 0
    assert captured["saved"] == []


def test_history_can_filter_by_scan_type():
    from models.db_models import AnalysisHistory, Base, User  # pyright: ignore[reportMissingImports]
    from repositories.analysis_repo import get_all_ticker_history

    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="gate_user", password_hash="hash", display_name="Gate User")
        session.add(user)
        session.commit()
        start = datetime(2026, 1, 1, 10, 0, 0)
        for i, tier in enumerate(["standard", "deep", "standard", "deep", "standard"]):
            session.add(AnalysisHistory(
                user_id=user.id, ticker=TICKER, analysis_date=(start + timedelta(days=i)).date().isoformat(),
                signal="HOLD", full_json=json.dumps({"n": i}), created_at=start + timedelta(days=i), scan_type=tier,
            ))
        session.commit()

        deep = get_all_ticker_history(session, TICKER, scan_type="deep")
        every = get_all_ticker_history(session, TICKER)
    finally:
        session.close()
        engine.dispose()

    assert [r["n"] for r in deep] == [1, 3]
    assert [r["n"] for r in every] == [0, 1, 2, 3, 4]
