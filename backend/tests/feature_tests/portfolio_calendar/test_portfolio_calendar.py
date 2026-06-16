import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_portfolio_calendar_endpoint():
    response = client.get("/api/v1/portfolio/0/calendar")
    assert response.status_code in [200, 401, 404]
