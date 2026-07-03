import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_analysis_engine_status():
    response = client.get("/analyze/active")
    assert response.status_code in [200, 401]
