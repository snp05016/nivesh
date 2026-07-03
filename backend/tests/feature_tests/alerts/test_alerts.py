import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_alerts_endpoint():
    response = client.get("/alerts/0")
    assert response.status_code in [200, 401, 404]
