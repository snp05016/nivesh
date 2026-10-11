import pytest
from unittest.mock import patch, MagicMock

from services.orchestrator import analyze, reformat_with_deepseek, run_trading_agents

@pytest.fixture
def mock_db_session():
    with patch("services.orchestrator.get_session") as mock_get_session:
        session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = session
        yield session

@pytest.fixture
def mock_deepseek_chat():
    with patch("services.orchestrator._deepseek_chat") as mock_ds:
        yield mock_ds

@pytest.fixture
def mock_claude_haiku():
    with patch("services.orchestrator.reformat_with_claude") as mock_claude:
        yield mock_claude

def test_analyze_cache_hit(mock_db_session):
    # Mocking cache hit
    with patch("services.orchestrator.get_analysis_for_date") as mock_get:
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

@patch("services.orchestrator.run_trading_agents")
@patch("services.orchestrator.reformat_with_deepseek")
def test_analyze_full_run(mock_reformat, mock_run_agents, mock_db_session):
    with patch("services.orchestrator.get_analysis_for_date") as mock_get:
        mock_get.return_value = None  # Cache miss
        
        with patch("services.orchestrator.compute_staleness") as mock_staleness:
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


# run_job's QUEUED -> RUNNING -> SUCCEEDED/FAILED transitions are covered by
# tests/test_worker.py against the real job DAO.
