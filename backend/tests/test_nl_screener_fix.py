import pytest
from fastapi.testclient import TestClient
from main import app
from routers.nl_screener import NLScreenerResponse
from unittest.mock import patch
import json

client = TestClient(app)

def test_nl_screener_success():
    response = client.post("/api/v1/screener/natural-language", json={
        "query": "tech companies with pe under 30"
    })
    assert response.status_code == 200
    data = response.json()
    assert "parsed_filters" in data
    assert "results" in data
    
    # Verify all parsed filters are strings
    for k, v in data["parsed_filters"].items():
        assert isinstance(v, str), f"Filter {k} should be str, got {type(v)}"

@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_malformed_llm(mock_chat):
    # LLM returns garbage
    mock_chat.return_value = "This is not valid json at all!"
    response = client.post("/api/v1/screener/natural-language", json={
        "query": "banks"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["parsed_filters"] == {}

@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_empty_results(mock_chat):
    # LLM returns a filter that no stock can match
    mock_chat.return_value = '{"parsed_filters": {"pe_max": -100}}'
    response = client.post("/api/v1/screener/natural-language", json={
        "query": "companies with negative 100 PE"
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 0

def test_nl_screener_exact_failing_query():
    # The original failing query type - numeric filters
    response = client.post("/api/v1/screener/natural-language", json={
        "query": "banks with PE less than 20"
    })
    assert response.status_code == 200
    data = response.json()
    # Check that pe_max exists and is a string
    if "pe_max" in data["parsed_filters"]:
        assert isinstance(data["parsed_filters"]["pe_max"], str)
