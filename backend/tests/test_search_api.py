import pytest
from fastapi.testclient import TestClient
from main import app
from database import create_access_token

SWIFT_KEYS = {"ticker", "company_name", "sector", "exchange"}


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(1)
    return {"Authorization": f"Bearer {token}"}


def test_universal_search_unauthorized(test_client):
    response = test_client.get("/api/v1/search?query=HDFC")
    assert response.status_code == 401


def test_universal_search_returns_swift_shape(test_client, auth_headers):
    # follow_redirects=False: the route must be served at /api/v1/search directly, no 307.
    response = test_client.get("/api/v1/search?query=HDFC", headers=auth_headers, follow_redirects=False)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) and data
    assert all(set(item) == SWIFT_KEYS for item in data)
    assert data[0]["ticker"].startswith("HDFC")


def test_universal_search_exact_ticker_first(test_client, auth_headers):
    response = test_client.get("/api/v1/search?query=TCS", headers=auth_headers, follow_redirects=False)
    assert response.status_code == 200
    assert response.json()[0]["ticker"] == "TCS"


def test_universal_search_respects_limit(test_client, auth_headers):
    response = test_client.get("/api/v1/search?query=HDFC&limit=2", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_universal_search_empty_query(test_client, auth_headers):
    response = test_client.get("/api/v1/search?query=", headers=auth_headers, follow_redirects=False)
    assert response.status_code == 200
    assert response.json() == []
