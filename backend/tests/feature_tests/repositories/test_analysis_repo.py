import pytest
from unittest.mock import MagicMock, patch
import json
from datetime import date, datetime, timezone

from repositories.analysis_repo import (
    save_analysis,
    get_recent_analyses,
    get_analysis_for_date,
    get_all_ticker_history,
)

@pytest.fixture
def mock_session():
    return MagicMock()

def test_save_analysis_new(mock_session):
    # Mock no previous analysis
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    result = {
        "signal": "BULLISH",
        "confidence_pct": 85,
        "target_prices": {"short_term_3m": 120}
    }
    
    res = save_analysis(mock_session, 1, "RELIANCE", result, "raw_out", "standard")
    
    assert mock_session.add.called
    assert mock_session.commit.called
    assert res["signal_changed"] is False
    assert res["previous_signal"] is None

def test_save_analysis_signal_changed(mock_session):
    # Mock previous analysis with different signal
    prev_row = MagicMock(signal="HOLD", promoter_pledged_pct=10.0)
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = prev_row
    
    result = {
        "signal": "BULLISH",
        "fundamentals_snapshot": {"promoter_pledged_pct": 11.0},
        "analysis_date": "2026-06-30"
    }
    
    res = save_analysis(mock_session, 1, "RELIANCE", result, "raw", "standard")
    
    assert res["signal_changed"] is True
    assert res["previous_signal"] == "HOLD"
    # Should add a SignalEvent and AnalysisHistory
    assert mock_session.add.call_count == 2

def test_get_recent_analyses(mock_session):
    row1 = MagicMock(full_json=json.dumps({"signal": "BULLISH"}))
    row2 = MagicMock(full_json=json.dumps({"signal": "HOLD"}))
    # Mock the chain: query().filter().filter().order_by().limit().all()
    mock_query = mock_session.query.return_value
    mock_filter1 = mock_query.filter.return_value
    mock_filter2 = mock_filter1.filter.return_value
    mock_order = mock_filter2.order_by.return_value
    mock_limit = mock_order.limit.return_value
    mock_limit.all.return_value = [row1, row2]
    
    res = get_recent_analyses(mock_session, 1, "RELIANCE", limit=2)
    assert len(res) == 2
    # The function reverses the result, so row2 then row1
    assert res[0]["signal"] == "HOLD"
    assert res[1]["signal"] == "BULLISH"

@patch("services.staleness.compute_staleness")
def test_get_analysis_for_date(mock_compute_staleness, mock_session):
    mock_compute_staleness.return_value = {"score": 50, "urgency": "Stale", "reason": "Time"}
    
    row = MagicMock(
        full_json=json.dumps({"signal": "BULLISH"}),
        confidence_math_breakdown={},
        raw_output="raw",
        created_at=datetime(2026, 6, 29, tzinfo=timezone.utc)
    )
    # Mock the chain: query().filter(ticker, scan_type).filter(analysis_date).order_by().first()
    mock_query = mock_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_date_filter = mock_filter.filter.return_value
    mock_date_filter.order_by.return_value.first.return_value = row

    res = get_analysis_for_date(mock_session, "RELIANCE", "2026-06-30")

    assert res is not None
    assert res["signal"] == "BULLISH"
    assert res["_staleness_score"] == 50
    # LLM-V1: the target date is a real filter, not ignored.
    (date_clause,), _ = mock_filter.filter.call_args
    assert str(date_clause.compile(compile_kwargs={"literal_binds": True})) == (
        "analysis_history.analysis_date = '2026-06-30'"
    )


@patch("services.staleness.compute_staleness")
def test_get_analysis_for_date_empty_date_returns_latest(mock_compute_staleness, mock_session):
    mock_compute_staleness.return_value = {"score": 10, "urgency": "Fresh", "reason": "Time"}
    row = MagicMock(
        full_json=json.dumps({"signal": "HOLD"}),
        confidence_math_breakdown={},
        raw_output="raw",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc)
    )
    mock_filter = mock_session.query.return_value.filter.return_value
    mock_filter.order_by.return_value.first.return_value = row

    res = get_analysis_for_date(mock_session, "RELIANCE", "")

    assert res is not None and res["signal"] == "HOLD"
    mock_filter.filter.assert_not_called()

def test_get_all_ticker_history(mock_session):
    row1 = MagicMock(full_json=json.dumps({"signal": "BULLISH"}), confidence_math_breakdown={}, raw_output="raw")
    # Mock the chain: query().filter().filter().order_by().limit().all()
    mock_query = mock_session.query.return_value
    mock_filter1 = mock_query.filter.return_value
    mock_filter2 = mock_filter1.filter.return_value
    mock_order = mock_filter2.order_by.return_value
    mock_limit = mock_order.limit.return_value
    mock_limit.all.return_value = [row1]
    
    res = get_all_ticker_history(mock_session, "RELIANCE", 1)
    assert len(res) == 1
    assert res[0]["signal"] == "BULLISH"
