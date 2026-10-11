"""LLM-20: NL screener cache key, industry filter, applied-filter echo, dead universe."""
import hashlib
import uuid
from unittest.mock import patch

import services.nl_screener as nl_screener
from database import get_session
from models.db_models import StockUniverse

URL = "/api/v1/screener/natural-language"


def test_cache_key_is_process_independent_and_normalised():
    # builtin hash() is salted per process (PYTHONHASHSEED); the key must be a pure digest,
    # so it equals this literal sha256 in every worker and after every restart.
    expected = "nl_screener_" + hashlib.sha256(b"banks with pe < 20").hexdigest()
    assert nl_screener._cache_key("banks with pe < 20") == expected
    assert nl_screener._cache_key("  Banks with PE < 20 ") == expected
    assert nl_screener._cache_key("pharma") != expected


@patch("services.nl_screener.cache_set")
@patch("services.nl_screener.deepseek_chat")
def test_industry_filter_excludes_other_industries(mock_chat, _mock_cache_set, client):
    tag = uuid.uuid4().hex[:6].upper()
    it_ticker, bank_ticker = f"IT{tag}", f"BK{tag}"
    with get_session() as session:
        session.add_all([
            StockUniverse(ticker=it_ticker, company_name="Test IT Co", industry="IT Services",
                          market_cap=1e15),
            StockUniverse(ticker=bank_ticker, company_name="Test Bank Co", industry="Banks",
                          market_cap=1e15),
        ])
        session.commit()
    try:
        mock_chat.return_value = '{"parsed_filters": {"industry": "IT"}}'
        response = client.post(URL, json={"query": f"IT companies {tag}"})
        assert response.status_code == 200
        tickers = {r["ticker"] for r in response.json()["results"]}
        assert it_ticker in tickers
        assert bank_ticker not in tickers
    finally:
        with get_session() as session:
            session.query(StockUniverse).filter(
                StockUniverse.ticker.in_([it_ticker, bank_ticker])
            ).delete(synchronize_session=False)
            session.commit()


@patch("services.nl_screener.cache_set")
@patch("services.nl_screener.deepseek_chat")
def test_unsupported_keys_not_echoed_as_applied(mock_chat, _mock_cache_set, client):
    mock_chat.return_value = (
        '{"parsed_filters": {"pe_max": 20, "reference_company": "INFY"}, '
        '"reference_company": "INFY"}'
    )
    response = client.post(URL, json={"query": f"cheaper than Infosys {uuid.uuid4().hex}"})
    assert response.status_code == 200
    assert response.json()["parsed_filters"] == {"pe_max": "20"}


def test_unused_stock_universe_list_removed():
    assert not hasattr(nl_screener, "_INDIA_STOCK_UNIVERSE")
    assert "reference_company" not in nl_screener.SYSTEM_PROMPT
