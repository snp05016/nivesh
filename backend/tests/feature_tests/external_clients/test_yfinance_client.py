import pytest
from unittest.mock import patch, MagicMock

from services.yfinance_client import (
    _yf_fetch_info,
    _yf_price,
    _resolve_with_fallback,
    _to_ns,
    _resolve_ticker,
    _extract_json_from_text,
)

@patch("services.yfinance_client.yf.Ticker")
def test_yf_fetch_info_success(mock_ticker):
    mock_instance = MagicMock()
    mock_instance.info = {"currentPrice": 150.0, "shortName": "Test"}
    mock_ticker.return_value = mock_instance

    result = _yf_fetch_info("RELIANCE.NS")
    assert result == {"currentPrice": 150.0, "shortName": "Test"}

@patch("services.yfinance_client.yf.Ticker")
def test_yf_fetch_info_retry(mock_ticker):
    mock_instance = MagicMock()
    # First fails, second succeeds
    type(mock_instance).info = property(
        MagicMock(side_effect=[Exception("Network error"), {"regularMarketPrice": 200.0}])
    )
    mock_ticker.return_value = mock_instance

    with patch("services.yfinance_client.time.sleep") as mock_sleep:
        result = _yf_fetch_info("TCS.NS")
        assert result == {"regularMarketPrice": 200.0}
        assert mock_sleep.call_count == 1

@patch("services.yfinance_client.yf.Ticker")
def test_yf_price(mock_ticker):
    import pandas as pd
    mock_instance = MagicMock()
    mock_hist = pd.DataFrame({"Close": [100.0, 105.0]})
    mock_instance.history.return_value = mock_hist
    mock_ticker.return_value = mock_instance

    curr, prev = _yf_price("HDFCBANK.NS")
    assert curr == 105.0
    assert prev == 100.0

@patch("services.yfinance_client.yf.Ticker")
def test_yf_price_fallback(mock_ticker):
    import pandas as pd
    mock_instance_bse = MagicMock()
    mock_instance_bse.history.return_value = pd.DataFrame()
    
    mock_instance_ns = MagicMock()
    mock_instance_ns.history.return_value = pd.DataFrame({"Close": [50.0, 52.0]})
    
    def side_effect(sym):
        if sym.endswith(".BO"):
            return mock_instance_bse
        return mock_instance_ns
        
    mock_ticker.side_effect = side_effect

    curr, prev = _yf_price("INFY.BO")
    assert curr == 52.0
    assert prev == 50.0

@patch("services.yfinance_client.yf.Ticker")
def test_resolve_with_fallback(mock_ticker):
    mock_instance = MagicMock()
    mock_instance.fast_info = MagicMock(last_price=100.0)
    mock_ticker.return_value = mock_instance

    res = _resolve_with_fallback("TEST", ".NS")
    assert res == "TEST.NS"

def test_extract_json_from_text():
    raw = "```json\n{\"key\": \"value\"}\n```"
    res = _extract_json_from_text(raw)
    assert res == '{"key": "value"}'

    raw2 = "```\nplain text\n```"
    res2 = _extract_json_from_text(raw2)
    assert res2 == "plain text"

    res3 = _extract_json_from_text("no ticks")
    assert res3 == "no ticks"
