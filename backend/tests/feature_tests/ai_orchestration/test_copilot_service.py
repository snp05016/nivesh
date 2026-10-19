import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from services.copilot_service import process_copilot_request, strip_emoji, _trim_history

def test_strip_emoji():
    assert strip_emoji("Hello 👋") == "Hello"
    assert strip_emoji("Bullish 🚀") == "Bullish"
    assert strip_emoji("₹1,200 – up 📈") == "₹1,200 – up"

def test_trim_history_keeps_short_history():
    history = [{"role": "user", "content": "hello"}]
    assert _trim_history(history) == history

@patch("services.copilot_service.deepseek_chat")
@patch("services.copilot_service.claude_haiku")
def test_process_copilot_general(mock_claude, mock_deepseek):
    # Mock routing as GENERAL, and then the actual response
    mock_deepseek.side_effect = ["GENERAL", "Here is a general response."]
    
    res = process_copilot_request("What is a stock?", [], {}, 1)
    
    assert "Here is a general response" in res["reply"]
    assert mock_deepseek.call_count == 2
    mock_claude.assert_not_called()

@patch("services.copilot_service._yf_price", return_value=(600.0, None))
@patch("services.copilot_service.deepseek_chat")
@patch("services.copilot_service.claude_haiku")
@patch("services.copilot_service.get_session")
def test_process_copilot_portfolio(mock_get_session, mock_claude, mock_deepseek, _mock_price):
    mock_deepseek.return_value = "PORTFOLIO"

    mock_db = MagicMock()
    mock_get_session.return_value.__enter__.return_value = mock_db
    # SimpleNamespace, not MagicMock: a MagicMock row answered h.quantity and hid DB-20.
    mock_db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(ticker="SBIN", shares=10.0, buy_price=500.0, group_name="holdings"),
    ]

    res = process_copilot_request("How is my portfolio?", [], {}, 1)

    assert res["reply_source"] == "computed"
    assert "You hold 1 stock." in res["reply"]
    assert "₹5,000" in res["reply"] and "₹6,000" in res["reply"]
    mock_claude.assert_not_called()


@patch("services.copilot_service.deepseek_chat")
@patch("services.copilot_service.claude_haiku")
@patch("services.copilot_service.get_session")
def test_process_copilot_portfolio_anonymous(mock_get_session, mock_claude, mock_deepseek):
    mock_deepseek.return_value = "PORTFOLIO"

    res = process_copilot_request("How is my portfolio?", [], {}, None)

    assert "Sign in" in res["reply"]
    mock_claude.assert_not_called()
    mock_get_session.assert_not_called()

@patch("services.copilot_service.deepseek_chat")
@patch("services.copilot_service.claude_haiku")
def test_process_copilot_deep_analysis(mock_claude, mock_deepseek):
    # Chat never runs an analysis itself; it deep-links to the analysis screen.
    mock_deepseek.side_effect = ["DEEP_ANALYSIS", "RELIANCE"]

    res = process_copilot_request("Analyze Reliance for me", [], {}, 1)

    assert "RELIANCE" in res["reply"]
    assert "signal" not in res["reply"].lower()
    assert res["context_cards"] == [{"type": "open_analysis", "ticker": "RELIANCE"}]
    mock_claude.assert_not_called()
