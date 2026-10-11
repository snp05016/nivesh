import pytest
from unittest.mock import patch, MagicMock

from backend.services.copilot_service import process_copilot_request, strip_emoji, _manage_tokens

def test_strip_emoji():
    assert strip_emoji("Hello 👋") == "Hello "
    assert strip_emoji("Bullish 🚀") == "Bullish "

def test_manage_tokens_no_summary():
    history = [{"role": "user", "content": "hello"}]
    managed = _manage_tokens(history)
    assert len(managed) == 1

@patch("backend.services.copilot_service.deepseek_chat")
@patch("backend.services.copilot_service.claude_haiku")
def test_process_copilot_general(mock_claude, mock_deepseek):
    # Mock routing as GENERAL, and then the actual response
    mock_deepseek.side_effect = ["GENERAL", "Here is a general response."]
    
    res = process_copilot_request("What is a stock?", [], {}, 1)
    
    assert "Here is a general response" in res["reply"]
    assert mock_deepseek.call_count == 2
    mock_claude.assert_not_called()

@patch("backend.services.copilot_service.has_active_consent", return_value=True)
@patch("backend.services.copilot_service.deepseek_chat")
@patch("backend.services.copilot_service.claude_haiku")
@patch("backend.services.copilot_service.get_session")
def test_process_copilot_portfolio(mock_get_session, mock_claude, mock_deepseek, _mock_consent):
    mock_deepseek.return_value = "PORTFOLIO"
    mock_claude.return_value = "Portfolio looks great."
    
    # Mock DB session
    mock_db = MagicMock()
    mock_get_session.return_value.__enter__.return_value = mock_db
    mock_db.query.return_value.filter.return_value.all.return_value = []
    
    res = process_copilot_request("How is my portfolio?", [], {}, 1)
    
    assert res["reply"] == "Portfolio looks great."
    mock_claude.assert_called_once()

@patch("backend.services.copilot_service.deepseek_chat")
@patch("backend.services.copilot_service.claude_haiku")
@patch("backend.services.copilot_service.multiprocessing.Process")
@patch("backend.services.copilot_service.multiprocessing.Queue")
def test_process_copilot_deep_analysis(mock_queue, mock_process, mock_claude, mock_deepseek):
    # Mock intent and ticker extraction
    mock_deepseek.side_effect = ["DEEP_ANALYSIS", "RELIANCE"]
    
    # Mock the multiprocessing queue to return a successful analysis
    mock_q_instance = MagicMock()
    mock_q_instance.get.return_value = {"status": "ok", "result": {"signal": "BULLISH", "confidence": 80}}
    mock_queue.return_value = mock_q_instance
    
    res = process_copilot_request("Analyze Reliance for me", [], {}, 1)
    
    assert "I've analyzed RELIANCE. The overall signal is BULLISH." in res["reply"]
    assert res["context_cards"] == [{"signal": "BULLISH", "confidence": 80}]
    mock_process.assert_called_once()
    mock_q_instance.get.assert_called_once()
