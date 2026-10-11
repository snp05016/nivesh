"""SILENT-21: failures must not answer 200 with an empty or canned body.

The screener counts per-candidate failures (and feeds the yfinance breaker) instead
of returning [] as "no matches"; daily-action, nifty-history and the experts
services surface their failures as non-2xx.
"""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import HTTPException

import helpers
import routers.analysis as analysis_router
import routers.market as market_router
from database import AnalysisHistory, get_session
from services import user_service

_TICKERS = ("SILENT21A", "SILENT21B")


def _boom(*_args, **_kwargs):
    raise RuntimeError("upstream down")


@pytest.fixture
def bullish_rows():
    """Two recent BULLISH analyses so the DB-driven presets have candidates to look up."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_session() as session:
        for ticker in _TICKERS:
            session.add(AnalysisHistory(
                ticker=ticker, analysis_date=today, signal="BULLISH",
                confidence_pct=100, full_json=json.dumps({}),
            ))
        session.commit()
    yield
    with get_session() as session:
        session.query(AnalysisHistory).filter(AnalysisHistory.ticker.in_(_TICKERS)).delete(
            synchronize_session=False)
        session.commit()


@pytest.mark.parametrize("preset", ["ghar_ghar_modi", "institutional_capitulation"])
@pytest.mark.parametrize("fetch_info", [_boom, lambda _sym: {}], ids=["raises", "no_data"])
def test_screener_all_lookups_failing_is_503_and_feeds_breaker(client, monkeypatch, bullish_rows, fetch_info, preset):
    failures, successes = MagicMock(), MagicMock()
    monkeypatch.setattr(analysis_router, "_yf_circuit_is_open", lambda: False)
    monkeypatch.setattr(analysis_router, "_yf_circuit_record_failure", failures)
    monkeypatch.setattr(analysis_router, "_yf_circuit_record_success", successes)
    monkeypatch.setattr(analysis_router, "_yf_fetch_info", fetch_info)

    resp = client.get("/screener", params={"preset": preset})

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Market data temporarily unavailable"
    failures.assert_called_once()
    successes.assert_not_called()  # the old blanket success reset the breaker here


def test_screener_unknown_preset_400(client):
    resp = client.get("/screener", params={"preset": "no_such_preset"})
    assert resp.status_code == 400


def test_daily_action_failure_is_503_not_canned_tip(monkeypatch):
    monkeypatch.setattr(helpers, "get_session", _boom)
    with pytest.raises(HTTPException) as exc:
        analysis_router.daily_action_endpoint(user_id=1, _caller=1)
    assert exc.value.status_code == 503


def test_token_stats_error_propagates(monkeypatch):
    import core.dashboard_state as dashboard_state
    monkeypatch.setattr(analysis_router, "require_admin", lambda _auth: None)
    monkeypatch.setattr(dashboard_state, "token_usage_summary", _boom)
    with pytest.raises(RuntimeError):
        analysis_router.token_stats_endpoint(authorization="Bearer x")


def test_nifty_history_empty_is_503(monkeypatch):
    monkeypatch.setattr(market_router, "_dcache_get", lambda *_a: None)
    empty = SimpleNamespace(history=lambda **_k: pd.DataFrame())
    monkeypatch.setattr(market_router, "yf", SimpleNamespace(Ticker=lambda _sym: empty))
    with pytest.raises(HTTPException) as exc:
        market_router.nifty_history_endpoint(days=30)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("fn", [user_service.get_experts_service, user_service.get_expert_posts_service])
def test_experts_failure_raises_not_empty_list(monkeypatch, fn):
    monkeypatch.setattr(user_service, "get_session", _boom)
    with pytest.raises(RuntimeError):
        fn()
