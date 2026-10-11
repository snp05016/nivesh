import pytest
from unittest.mock import patch, MagicMock

from backend.services.orchestrator import analyze, reformat_with_deepseek, run_trading_agents
from backend.services.job_manager import spawn_job
from backend.services.job_worker import run_job

@pytest.fixture
def mock_db_session():
    with patch("backend.services.orchestrator.get_session") as mock_get_session:
        session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = session
        yield session

@pytest.fixture
def mock_deepseek_chat():
    with patch("backend.services.orchestrator._deepseek_chat") as mock_ds:
        yield mock_ds

@pytest.fixture
def mock_claude_haiku():
    with patch("backend.services.orchestrator.reformat_with_claude") as mock_claude:
        yield mock_claude

def test_analyze_cache_hit(mock_db_session):
    # Mocking cache hit
    with patch("backend.services.orchestrator.get_analysis_for_date") as mock_get:
        mock_get.return_value = {
            "signal": "BULLISH",
            "confidence_pct": 85,
            "governance_score": 75,  # below 40 the hierarchy cap turns BULLISH into HOLD
            "key_factors": {"indian_market_sentiment": "Positive"},
            "raw_output": "cached response"
        }
        
        result = analyze(ticker="RELIANCE", exchange="NSE", scan_type="standard")
        
        assert result["signal"] == "BULLISH"
        assert result["_cache_type"] == "CACHE HIT"

@patch("backend.services.orchestrator.run_trading_agents")
@patch("backend.services.orchestrator.reformat_with_deepseek")
def test_analyze_full_run(mock_reformat, mock_run_agents, mock_db_session):
    with patch("backend.services.orchestrator.get_analysis_for_date") as mock_get:
        mock_get.return_value = None  # Cache miss
        
        with patch("backend.services.orchestrator.compute_staleness") as mock_staleness:
            mock_staleness.return_value = (80, "URGENT")
            
            # Mock graph output
            mock_run_agents.return_value = ("RAW OUTPUT", [], {"governance_report": "Gov"})
            
            # Mock reformatter output
            mock_reformat.return_value = {
                "signal": "BULLISH",
                "confidence_pct": 75,
                "governance_score": 75,
                "key_factors": {"indian_market_sentiment": "Good"}
            }
            
            result = analyze(ticker="TCS", exchange="NSE", scan_type="standard")
            
            assert result["signal"] == "BULLISH"
            mock_run_agents.assert_called_once()
            mock_reformat.assert_called_once()

def test_reformat_with_deepseek(mock_deepseek_chat):
    mock_deepseek_chat.return_value = '''
    ```json
    {
        "signal": "BEARISH",
        "confidence_pct": 60,
        "key_factors": {"indian_market_sentiment": "Negative"},
        "bull_case": ["Good cash flow"],
        "bear_case": ["Bad management"],
        "key_risks": ["Competition"],
        "target_prices": {"short_term_3m": 100},
        "upside_downside_pct": {"short_term_3m": -10}
    }
    ```
    '''
    
    result = reformat_with_deepseek("RAW DATA", "INFY", "NSE")
    
    assert result["signal"] == "BEARISH"
    assert result["reformat_model"] == "deepseek-flash"

@patch("backend.services.job_worker.database")
@patch("backend.services.job_worker.analyze")
@patch("backend.services.job_worker._start_wallclock_watchdog")
def test_state_transitions_queued_processing_completed(mock_watchdog, mock_analyze, mock_db):
    """
    Test state transitions from QUEUED (default state before job spawn)
    -> PROCESSING/RUNNING (when job starts)
    -> COMPLETED/SUCCEEDED (when job finishes).
    """
    mock_analyze.return_value = {"signal": "BULLISH"}
    
    # Run the worker process simulation
    run_job(job_id="job123", ticker="WIPRO", exchange="NSE", user_id=1, deep_scan=False, scan_type="standard")
    
    # Verify the database status updates align with state transition expectations
    update_calls = mock_db.update_job.call_args_list
    assert len(update_calls) == 2
    
    # 1st call -> PROCESSING/RUNNING
    first_call_kwargs = update_calls[0].kwargs
    assert first_call_kwargs["status"] == "RUNNING"
    assert first_call_kwargs["progress_pct"] == 1
    
    # 2nd call -> COMPLETED/SUCCEEDED
    second_call_kwargs = update_calls[1].kwargs
    assert second_call_kwargs["status"] == "SUCCEEDED"
    assert second_call_kwargs["progress_pct"] == 100
    assert "result_json" in second_call_kwargs

@patch("backend.services.job_worker.database")
@patch("backend.services.job_worker.analyze")
@patch("backend.services.job_worker._start_wallclock_watchdog")
def test_state_transitions_failed(mock_watchdog, mock_analyze, mock_db):
    mock_analyze.side_effect = ValueError("Something broke")
    
    with pytest.raises(ValueError):
        run_job(job_id="job456", ticker="WIPRO", exchange="NSE", user_id=1, deep_scan=False, scan_type="standard")
        
    update_calls = mock_db.update_job.call_args_list
    assert len(update_calls) == 2
    
    # First call sets to RUNNING/PROCESSING
    assert update_calls[0].kwargs["status"] == "RUNNING"
    
    # Second call sets to FAILED
    assert update_calls[1].kwargs["status"] == "FAILED"
    assert "Something broke" in update_calls[1].kwargs["error"]
