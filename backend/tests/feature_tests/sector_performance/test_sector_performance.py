import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_sector_performance_endpoint():
    response = client.get("/api/v1/market/sector-performance")
    assert response.status_code in [200, 401]
