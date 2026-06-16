import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_tech_momentum_endpoint():
    response = client.get("/api/v1/market/tech-momentum")
    assert response.status_code in [200, 401]
