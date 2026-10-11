"""LLM-V1: POST /analyze serves only same-day cached reports, and a cache hit keeps the
date it was generated on instead of being relabelled with today's date."""
import json
import sys
import types
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import database
from core.timeutil import ist_today
from models.db_models import AnalysisHistory


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
    monkeypatch.setattr(orchestrator, "_inject_live_data", lambda result, ticker: result)
    return orchestrator


def _insert_row(ticker: str, analysis_date: str) -> None:
    body = {"ticker": ticker, "signal": "BULLISH", "confidence_pct": 70, "analysis_date": analysis_date}
    with database.get_session() as session:
        session.add(AnalysisHistory(
            user_id=None, ticker=ticker, analysis_date=analysis_date, signal="BULLISH",
            confidence_pct=70, full_json=json.dumps(body), scan_type="standard",
        ))
        session.commit()


def test_stale_cached_report_spawns_a_fresh_job(client, spawned_jobs, orch):
    old = (ist_today() - timedelta(days=30)).isoformat()
    _insert_row("FRESHOLD", old)

    resp = client.post("/analyze", json={"ticker": "FRESHOLD", "exchange": "NSE"})

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body.get("_cache_type") != "CACHE HIT"
    assert body["job_id"]
    assert len(spawned_jobs) == 1


def test_same_day_cached_report_is_a_cache_hit(client, spawned_jobs, orch):
    today = ist_today().isoformat()
    _insert_row("FRESHNEW", today)

    resp = client.post("/analyze", json={"ticker": "FRESHNEW", "exchange": "NSE"})

    body = resp.json()
    assert body["_cache_type"] == "CACHE HIT", resp.text
    assert body["analysis_date"] == today
    assert "job_id" not in body
    assert spawned_jobs == []


def test_normalize_keeps_stored_date_and_fills_missing(orch):
    assert orch._normalize_response({"analysis_date": "2026-06-04", "signal": "HOLD"})["analysis_date"] == "2026-06-04"
    today = ist_today().strftime("%Y-%m-%d")
    assert orch._normalize_response({"signal": "HOLD"})["analysis_date"] == today
    assert orch._normalize_response({"analysis_date": "June 4", "signal": "HOLD"})["analysis_date"] == today
