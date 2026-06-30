import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from services.scraper import (
    TTLLRUCache,
    _get_soup,
    _parse_float,
    fetch_market_pulse,
    fetch_momentum,
    fetch_macro_alternatives,
    fetch_earnings_sync_ratio,
)

def test_ttl_lru_cache():
    cache = TTLLRUCache(maxsize=2, ttl=10)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)
    # b should be evicted because maxsize=2 and a was accessed last
    assert cache.get("b") is None
    assert cache.get("c") == 3

@patch("services.scraper.requests.get")
def test_get_soup(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><h1>Test</h1></body></html>"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp
    
    soup = _get_soup("http://test.com")
    assert soup is not None
    assert soup.find("h1").text == "Test"

def test_parse_float():
    assert _parse_float("1,234.56%") == 1234.56
    assert _parse_float("12.3") == 12.3
    assert _parse_float("invalid") is None

@patch("services.scraper._cache_get")
@patch("services.scraper._cache_set")
@patch("services.scraper._firecrawl_extract")
@patch("services.scraper._fetch_pulse_fallback")
def test_fetch_market_pulse(mock_fallback, mock_firecrawl, mock_set, mock_get):
    # Test cache hit
    mock_get.return_value = {"cached": True}
    res = fetch_market_pulse()
    assert res == {"cached": True}
    
    # Test firecrawl success
    mock_get.return_value = None
    mock_firecrawl.return_value = {"indices": [{"name": "Test", "value": "100"}]}
    res2 = fetch_market_pulse()
    assert "indices" in res2
    assert mock_fallback.call_count == 0
    
    # Test fallback
    mock_firecrawl.return_value = None
    mock_fallback.return_value = {"fallback": True}
    res3 = fetch_market_pulse()
    assert res3 == {"fallback": True}

@patch("services.scraper._cache_get")
@patch("services.scraper._cache_set")
@patch("services.scraper.yf.Ticker")
def test_fetch_momentum(mock_ticker, mock_set, mock_get):
    mock_get.return_value = None
    
    mock_instance = MagicMock()
    closes = [100.0] * 60
    mock_hist = pd.DataFrame({"Close": closes}, index=pd.date_range("2023-01-01", periods=60))
    mock_instance.history.return_value = mock_hist
    mock_ticker.return_value = mock_instance
    
    res = fetch_momentum()
    assert "bullish" in res
    assert "bearish" in res

@patch("services.scraper._cache_get")
@patch("services.scraper._cache_set")
@patch("services.scraper.yf.Ticker")
def test_fetch_macro_alternatives(mock_ticker, mock_set, mock_get):
    mock_get.return_value = None
    
    mock_instance = MagicMock()
    mock_instance.fast_info = MagicMock(last_price=150.0, previous_close=145.0)
    mock_ticker.return_value = mock_instance
    
    res = fetch_macro_alternatives()
    assert "items" in res
    assert len(res["items"]) > 0

@patch("services.scraper._cache_get")
@patch("services.scraper._cache_set")
@patch("services.scraper.requests.get")
def test_fetch_earnings_sync_ratio(mock_get_req, mock_set, mock_get_cache):
    mock_get_cache.return_value = None
    
    with patch("services.scraper._firecrawl_extract", return_value=None):
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><table class='mctable1'><tr><td></td><td></td><td></td></tr></table></body></html>"
        mock_get_req.return_value = mock_resp
        
        res = fetch_earnings_sync_ratio()
        assert "declared_count" in res
        assert "total_expected" in res
