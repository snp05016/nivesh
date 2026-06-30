import pytest
from unittest.mock import patch, MagicMock

from services.nse_client import (
    _nse_session,
    _get_asm_gsm_lists,
    _evict_asm_gsm_ticker,
    _fetch_single_index,
    _get_indices_data,
)

@patch("services.nse_client.requests.Session")
def test_nse_session(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    
    session = _nse_session()
    assert session == mock_session
    mock_session.get.assert_called_once_with("https://www.nseindia.com", timeout=15)

@patch("services.nse_client._nse_session")
@patch("services.nse_client._dcache_get")
@patch("services.nse_client._dcache_set")
def test_get_asm_gsm_lists_no_cache(mock_set, mock_get, mock_session_fn):
    mock_get.return_value = None
    mock_session = MagicMock()
    mock_session_fn.return_value = mock_session
    
    mock_resp_asm1 = MagicMock()
    mock_resp_asm1.status_code = 200
    mock_resp_asm1.json.return_value = {"data": [{"symbol": "ASM1"}]}
    
    mock_resp_asm2 = MagicMock()
    mock_resp_asm2.status_code = 200
    mock_resp_asm2.json.return_value = {"data": [{"symbol": "ASM2"}]}
    
    mock_resp_gsm = MagicMock()
    mock_resp_gsm.status_code = 200
    mock_resp_gsm.json.return_value = {"data": [{"symbol": "GSM1"}]}
    
    mock_session.get.side_effect = [mock_resp_asm1, mock_resp_asm2, mock_resp_gsm]
    
    res = _get_asm_gsm_lists()
    
    assert "ASM1" in res["ASM"]
    assert "ASM2" in res["ASM"]
    assert "GSM1" in res["GSM"]
    mock_set.assert_called_once()

@patch("services.nse_client._dcache_get")
@patch("services.nse_client._dcache_set")
def test_evict_asm_gsm_ticker(mock_set, mock_get):
    mock_get.return_value = {"ASM": ["TICKER1", "TICKER2"], "GSM": ["TICKER3"]}
    
    res = _evict_asm_gsm_ticker("TICKER1")
    assert res is True
    mock_set.assert_called_once()
    
    res2 = _evict_asm_gsm_ticker("NOTFOUND")
    assert res2 is False

@patch("services.nse_client.yf.Ticker")
def test_fetch_single_index(mock_ticker):
    mock_instance = MagicMock()
    mock_instance.fast_info = MagicMock(last_price=20000.0, previous_close=19500.0)
    mock_ticker.return_value = mock_instance
    
    res = _fetch_single_index("^NSEI", "Nifty 50")
    assert res is not None
    assert res["name"] == "Nifty 50"
    assert res["ticker"] == "^NSEI"
    assert res["value"] == 20000.0
    assert res["change_abs"] == 500.0

@patch("services.nse_client._fetch_single_index")
@patch("services.nse_client._dcache_get")
@patch("services.nse_client._dcache_set")
def test_get_indices_data(mock_set, mock_get, mock_fetch):
    mock_get.return_value = None
    mock_fetch.return_value = {"name": "Test", "value": 100.0}
    
    res = _get_indices_data()
    assert "indices" in res
    assert "fetched_at" in res
    assert len(res["indices"]) == 6
    mock_set.assert_called_once()
