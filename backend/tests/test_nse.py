import os
import logging
import requests
from unittest.mock import patch, MagicMock

def test_nse_connection():
    """
    Test HTTP requests to the NSE India API using a custom session and headers.
    Uses mocked requests by default to prevent live network calls during pytest.
    Opt-in to live network by setting ALLOW_LIVE_NSE_CHECK=1.
    """
    allow_live = os.environ.get("ALLOW_LIVE_NSE_CHECK") == "1"
    
    def run_logic():
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/"
        })
        s.get("https://www.nseindia.com", timeout=5)
        r = s.get("https://www.nseindia.com/api/historical/bulk-deals", timeout=5)
        logging.info(r.text[:200])
        return r

    if allow_live:
        r = run_logic()
        assert r.status_code == 200
    else:
        with patch("requests.Session.get") as mock_get:
            dummy_response = MagicMock()
            dummy_response.text = '{"dummy": "data"}'
            dummy_response.status_code = 200
            mock_get.return_value = dummy_response
            
            r = run_logic()
            
            assert mock_get.call_count == 2
            mock_get.assert_any_call("https://www.nseindia.com", timeout=5)
            mock_get.assert_any_call("https://www.nseindia.com/api/historical/bulk-deals", timeout=5)
