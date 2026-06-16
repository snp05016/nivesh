import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_screener_endpoint():
    response = client.get("/api/v1/market/screener")
    assert response.status_code in [200, 401]
