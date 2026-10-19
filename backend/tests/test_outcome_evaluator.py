"""LLM-14: the AnalysisHistory outcome loop records outcomes, once per row, and every
reader of a stored report's entry price goes through report_entry_price (live quote only)."""
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import AnalysisHistory, Base
from repositories.analysis_repo import report_entry_price
from services import outcome_labels
from services.advisor_harvester import evaluate_analysis_outcomes
from services.feedback_injector import get_feedback_block


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _row(session, ticker, signal, report, days_ago=35):
    created = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    row = AnalysisHistory(ticker=ticker, analysis_date=created.strftime("%Y-%m-%d"), signal=signal,
                          full_json=json.dumps(report), created_at=created)
    session.add(row)
    session.commit()
    return row


def _outcome(session, row_id):
    """(was_correct, outcome_delta_pct, outcome_checked_at) as plain values."""
    return session.query(AnalysisHistory.was_correct, AnalysisHistory.outcome_delta_pct,
                         AnalysisHistory.outcome_checked_at).filter(AnalysisHistory.id == row_id).one()


def _history(anchor_close, exit_close, days_ago=35):
    anchor = pd.Timestamp((datetime.now(timezone.utc) - timedelta(days=days_ago)).date())
    return pd.DataFrame({"Close": [anchor_close, exit_close]},
                        index=pd.DatetimeIndex([anchor - pd.Timedelta(days=1), anchor + pd.Timedelta(days=31)]))


@pytest.fixture
def prices(monkeypatch):
    """ticker -> (entry close, exit close); every fetch is recorded."""
    table, calls = {}, []

    def fake_fetch(symbol, **_kwargs):
        calls.append(symbol)
        return _history(*table[symbol]) if symbol in table else None

    monkeypatch.setattr(outcome_labels, "fetch_adjusted_history", fake_fetch)
    return table, calls


LIVE = {"signal": "BULLISH", "current_price_inr": 100.0, "current_price_source": "live_quote"}


def test_bullish_row_is_scored_once(session, prices):
    table, calls = prices
    table["EVALBUY"] = (100.0, 110.0)
    row = _row(session, "EVALBUY", "BULLISH", LIVE)

    assert evaluate_analysis_outcomes(session) == 1
    was_correct, delta, checked_at = _outcome(session, row.id)
    assert was_correct is True
    assert delta == pytest.approx(10.0)
    assert checked_at is not None

    calls.clear()
    assert evaluate_analysis_outcomes(session) == 0  # not re-selected
    assert calls == []


def test_hold_is_checked_but_abstains(session, prices):
    table, _ = prices
    table["EVALHOLD"] = (100.0, 102.0)
    row = _row(session, "EVALHOLD", "HOLD", {**LIVE, "signal": "HOLD"})

    evaluate_analysis_outcomes(session)
    was_correct, delta, checked_at = _outcome(session, row.id)
    assert was_correct is None  # ML-15: HOLD/NEUTRAL abstain
    assert delta == pytest.approx(2.0)
    assert checked_at is not None


def test_rows_inside_horizon_are_not_selected(session, prices):
    _, calls = prices
    _row(session, "EVALNEW", "BULLISH", LIVE, days_ago=5)
    assert evaluate_analysis_outcomes(session) == 0
    assert calls == []


@pytest.mark.parametrize("report, expected", [
    ({"current_price_inr": 100, "current_price_source": "live_quote"}, 100.0),
    ({"current_price_inr": "2450.5", "current_price_source": "live_quote"}, 2450.5),
    ({"current_price_inr": 100}, None),                                     # legacy: LLM-written price
    ({"current_price": 100, "price": 100}, None),                           # keys the old readers used
    ({"current_price_inr": 0.0, "current_price_source": "unavailable"}, None),
    ({"current_price_inr": 0.0, "current_price_source": "live_quote"}, None),
    ({"current_price_inr": "n/a", "current_price_source": "live_quote"}, None),
    (None, None),
])
def test_report_entry_price(report, expected):
    assert report_entry_price(report) == expected


def test_feedback_block_quotes_only_the_live_entry_price(session):
    _row(session, "FBLIVE", "BULLISH", LIVE, days_ago=10)
    _row(session, "FBLEGACY", "BULLISH", {"signal": "BULLISH", "current_price_inr": 999.0}, days_ago=10)

    live = get_feedback_block("FBLIVE", db_session=session)
    legacy = get_feedback_block("FBLEGACY", db_session=session)

    assert "Previous signal:     BULLISH" in live
    assert "Previous price:      ₹100.0" in live
    assert "EPISTEMIC FEEDBACK" in legacy
    assert "Previous price" not in legacy and "999" not in legacy
