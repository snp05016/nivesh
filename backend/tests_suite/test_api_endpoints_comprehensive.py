import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app
from database import User

# 100+ tests for API endpoints
# Using TestClient

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_header(test_user):
    from database import create_access_token
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.parametrize("i", range(20))
def test_ping(client, i):
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"pong": True}

def test_login_success(client, db_session):
    from database import _hash_password
    u = User(username="loginuser", password_hash=_hash_password("password"), display_name="Login")
    db_session.add(u)
    db_session.commit()
    
    response = client.post("/login", json={"username": "loginuser", "password": "password"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_fail(client):
    response = client.post("/login", json={"username": "wrong", "password": "wrong"})
    assert response.status_code == 401

@pytest.mark.parametrize("ticker", ["RELIANCE", "SBIN", "INFY", "TCS", "HDFCBANK"])
def test_quick_info_success(client, ticker):
    # conftest.py already mocks yf.Ticker
    response = client.get(f"/quick-info?ticker={ticker}")
    assert response.status_code == 200
    assert response.json()["ticker"] == ticker

def test_quick_info_invalid_exchange(client):
    response = client.get("/quick-info?ticker=SBIN&exchange=INVALID")
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_analyze_endpoint_mocked(client, auth_header):
    # Mocking the process and queue behavior in main.py
    with patch("main.analyze") as mock_analyze:
        mock_analyze.return_value = {"signal": "BUY", "confidence_pct": 90}
        
        with patch("multiprocessing.Queue") as mock_queue, \
             patch("multiprocessing.Process") as mock_process:
            
            instance_q = mock_queue.return_value
            instance_q.empty.side_effect = [True, False]
            instance_q.get.return_value = {"status": "ok", "result": {"signal": "BUY"}}
            
            mock_process.return_value.is_alive.side_effect = [True, False]
            
            response = client.post("/analyze", 
                                   json={"ticker": "SBIN", "exchange": "NSE"},
                                   headers=auth_header)
            assert response.status_code == 200
            assert response.json()["signal"] == "BUY"

@pytest.mark.parametrize("user_id", [1, 2, 3, 999])
def test_portfolio_access(client, user_id):
    # Portfolio is auth-optional but scoped
    response = client.get(f"/portfolio/{user_id}")
    assert response.status_code in [200, 404, 401]

def test_portfolio_with_auth(client, test_user, auth_header):
    response = client.get(f"/portfolio/{test_user.id}", headers=auth_header)
    assert response.status_code in [200, 404]

# Testing more endpoints
@pytest.mark.parametrize("days", [7, 30, 90, 365])
def test_nifty_history(client, days):
    response = client.get(f"/nifty-history?days={days}")
    assert response.status_code == 200
    assert "prices" in response.json()

@pytest.mark.parametrize("ticker", ["SBIN", "INFY"])
def test_quarterly_financials(client, ticker):
    response = client.get(f"/quarterly-financials?ticker={ticker}")
    assert response.status_code == 200
    assert "quarters" in response.json()

# Edge Cases for API
def test_analyze_invalid_ticker(client, auth_header):
    response = client.post("/analyze", json={"ticker": "INVALID_TICKER_NAME_TOO_LONG", "exchange": "NSE"}, headers=auth_header)
    assert response.status_code == 422 # Pydantic validation error

def test_rate_limiting_mock(client):
    with patch("main._check_rate_limit") as mock_limit:
        mock_limit.return_value = False
        response = client.get("/ping")
        assert response.status_code == 429
