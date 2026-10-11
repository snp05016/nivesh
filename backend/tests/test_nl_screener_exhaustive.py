import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, MagicMock
import json
import math

client = TestClient(app)

def mock_deepseek_return(filters_dict):
    return json.dumps({"parsed_filters": filters_dict})

@patch("services.nl_screener.deepseek_chat")
def test_valid_natural_language_query(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"sector": "IT"})
    response = client.post("/api/v1/screener/natural-language", json={"query": "top IT companies"})
    assert response.status_code == 200
    data = response.json()
    assert data["parsed_filters"]["sector"] == "IT"
    assert isinstance(data["results"], list)

@patch("services.nl_screener.deepseek_chat")
def test_empty_query(mock_chat):
    response = client.post("/api/v1/screener/natural-language", json={"query": ""})
    # A blank query is rejected before any (billed) LLM call.
    assert response.status_code == 422
    mock_chat.assert_not_called()

@patch("services.nl_screener.deepseek_chat")
def test_ambiguous_query(mock_chat):
    mock_chat.return_value = mock_deepseek_return({})
    response = client.post("/api/v1/screener/natural-language", json={"query": "good stocks"})
    # No filter means nothing to screen on; never return the whole universe as matches.
    assert response.status_code == 422
    assert "results" not in response.json()

@patch("services.nl_screener.deepseek_chat")
def test_no_matching_stocks(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"pe_max": -100})
    response = client.post("/api/v1/screener/natural-language", json={"query": "stocks with negative pe below 100"})
    assert response.status_code == 200
    assert response.json()["results"] == []

@patch("services.nl_screener.deepseek_chat")
def test_high_volume_query(mock_chat):
    mock_chat.return_value = mock_deepseek_return({})
    # Volume is not a supported filter, so the query is rejected rather than unfiltered.
    response = client.post("/api/v1/screener/natural-language", json={"query": "stocks with high volume"})
    assert response.status_code == 422

@patch("services.nl_screener.deepseek_chat")
def test_sector_filter(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"sector": "Banks"})
    response = client.post("/api/v1/screener/natural-language", json={"query": "banking stocks"})
    assert response.status_code == 200
    data = response.json()
    assert data["parsed_filters"]["sector"] == "Banks"

@patch("services.nl_screener.deepseek_chat")
def test_valuation_filter(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"pe_max": 15})
    response = client.post("/api/v1/screener/natural-language", json={"query": "pe under 15"})
    assert response.status_code == 200
    assert response.json()["parsed_filters"]["pe_max"] == "15"

@patch("services.nl_screener.deepseek_chat")
def test_profitability_filter(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"roce_min": 20})
    response = client.post("/api/v1/screener/natural-language", json={"query": "roce above 20%"})
    assert response.status_code == 200
    assert response.json()["parsed_filters"]["roce_min"] == "20"

@patch("services.nl_screener.deepseek_chat")
def test_debt_leverage_filter(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"debt_to_equity_max": 0.5})
    response = client.post("/api/v1/screener/natural-language", json={"query": "low debt companies"})
    assert response.status_code == 200
    assert response.json()["parsed_filters"]["debt_to_equity_max"] == "0.5"

@patch("services.nl_screener.deepseek_chat")
def test_market_cap_filter(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"market_cap_min": 100000000000})
    response = client.post("/api/v1/screener/natural-language", json={"query": "large cap stocks"})
    assert response.status_code == 200
    assert response.json()["parsed_filters"]["market_cap_min"] == "100000000000"

@patch("services.nl_screener.deepseek_chat")
def test_combined_filters(mock_chat):
    mock_chat.return_value = mock_deepseek_return({"pe_max": 20, "roce_min": 15, "sector": "IT"})
    response = client.post("/api/v1/screener/natural-language", json={"query": "IT stocks with pe < 20 and roce > 15"})
    assert response.status_code == 200
    data = response.json()
    assert data["parsed_filters"]["pe_max"] == "20"
    assert data["parsed_filters"]["roce_min"] == "15"
    assert data["parsed_filters"]["sector"] == "IT"

@patch("services.nl_screener.deepseek_chat")
def test_malformed_llm_output(mock_chat):
    mock_chat.return_value = "Here are the results... wait this isn't json"
    response = client.post("/api/v1/screener/natural-language", json={"query": "banks"})
    assert response.status_code == 422
    assert "results" not in response.json()

@patch("services.nl_screener.deepseek_chat")
def test_parser_timeout(mock_chat):
    mock_chat.side_effect = TimeoutError("LLM Timeout")
    response = client.post("/api/v1/screener/natural-language", json={"query": "banks"})
    assert response.status_code == 503 # LLM outage is an error, not an unfiltered screen
    assert "results" not in response.json()

@patch("services.nl_screener.deepseek_chat")
def test_nan_infinity_serialization(mock_chat):
    # What if yfinance returns NaN for a metric? We must ensure the backend handles it or JSON won't crash
    # By default Python json converts NaN to NaN but FastAPI/Pydantic validation might complain
    # Fastapi handles NaN natively if configured, but let's test a query.
    # Actually the score is derived, if it becomes NaN, let's see.
    mock_chat.return_value = mock_deepseek_return({"pe_max": math.nan})
    # Math.nan is float.
    response = client.post("/api/v1/screener/natural-language", json={"query": "nan pe"})
    assert response.status_code == 200
    assert response.json()["parsed_filters"]["pe_max"] == "nan"

def test_endpoint_always_returns_json():
    # Send a malformed body
    response = client.post("/api/v1/screener/natural-language", content="not json")
    assert response.status_code == 422
    assert "detail" in response.json() # Error envelope is JSON
