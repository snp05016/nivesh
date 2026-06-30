import pytest
from fastapi.testclient import TestClient
from main import app
from core.security import create_access_token

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Bearer token setup": f"Bearer {token}"}

def test_universal_search_unauthorized(test_client):
    response = test_client.get("/api/v1/search?query=HDFC")
    assert response.status_code == 401

def test_universal_search_authorized(test_client):
    token = create_access_token(data={"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    response = test_client.get("/api/v1/search?query=HDFC", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    assert "results" in data
    assert isinstance(data["results"], list)

def test_universal_search_empty_query(test_client):
    token = create_access_token(data={"sub": "1"})
    headers = {"Authorization": f"Bearer {token}"}
    response = test_client.get("/api/v1/search?query=", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
