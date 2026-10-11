import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from database import get_session
from main import app
from models.db_models import StockUniverse

client = TestClient(app)
URL = "/api/v1/screener/natural-language"


@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_success(mock_chat):
    mock_chat.return_value = '{"parsed_filters": {"sector": "IT", "pe_max": 30}}'
    response = client.post(URL, json={"query": "tech companies with pe under 30"})
    assert response.status_code == 200
    data = response.json()
    assert "parsed_filters" in data
    assert "results" in data

    # Verify all parsed filters are strings
    for k, v in data["parsed_filters"].items():
        assert isinstance(v, str), f"Filter {k} should be str, got {type(v)}"


@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_malformed_llm(mock_chat):
    # LLM returns garbage: the query was not understood, so no "everything matches" list.
    mock_chat.return_value = "This is not valid json at all!"
    response = client.post(URL, json={"query": "banks"})
    assert response.status_code == 422
    assert "results" not in response.json()


@patch("services.nl_screener.cache_set")
@patch("services.nl_screener.deepseek_chat")
def test_llm_failure_returns_503_and_not_cached(mock_chat, mock_cache_set):
    query = f"debt-free IT stocks {uuid.uuid4().hex}"
    mock_chat.side_effect = RuntimeError("DeepSeek call failed after 3 retries")
    response = client.post(URL, json={"query": query})
    assert response.status_code == 503
    assert "results" not in response.json()
    mock_cache_set.assert_not_called()

    # DeepSeek recovers: the same query is parsed afresh, not served a cached failure.
    mock_chat.side_effect = None
    mock_chat.return_value = '{"parsed_filters": {"debt_to_equity_max": 0.1}}'
    response = client.post(URL, json={"query": query})
    assert response.status_code == 200
    assert response.json()["parsed_filters"] == {"debt_to_equity_max": "0.1"}
    mock_cache_set.assert_called_once()


@patch("services.nl_screener.deepseek_chat")
def test_unknown_filter_keys_rejected(mock_chat):
    mock_chat.return_value = '{"parsed_filters": {"foo": 1}}'
    response = client.post(URL, json={"query": "foo stocks"})
    assert response.status_code == 422
    assert "results" not in response.json()


@patch("services.nl_screener.deepseek_chat")
def test_results_capped(mock_chat):
    prefix = f"CAP{uuid.uuid4().hex[:6].upper()}"
    tickers = [f"{prefix}{i:03d}" for i in range(150)]
    with get_session() as session:
        session.add_all(StockUniverse(ticker=t, company_name=t, pe_ratio=10.0) for t in tickers)
        session.commit()
    try:
        mock_chat.return_value = '{"parsed_filters": {"pe_max": 20}}'
        response = client.post(URL, json={"query": "pe under 20"})
        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 100
        assert all(r["reason"] == "Matches all 1 parsed filters" for r in results)
    finally:
        with get_session() as session:
            session.query(StockUniverse).filter(StockUniverse.ticker.in_(tickers)).delete(
                synchronize_session=False
            )
            session.commit()


@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_empty_results(mock_chat):
    # LLM returns a filter that no stock can match
    mock_chat.return_value = '{"parsed_filters": {"pe_max": -100}}'
    response = client.post(URL, json={"query": "companies with negative 100 PE"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 0


@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_exact_failing_query(mock_chat):
    # The original failing query type - numeric filters
    mock_chat.return_value = '{"parsed_filters": {"sector": "banking", "pe_max": 20}}'
    response = client.post(URL, json={"query": "banks with PE less than 20"})
    assert response.status_code == 200
    data = response.json()
    # Check that pe_max exists and is a string
    assert data["parsed_filters"]["pe_max"] == "20"
