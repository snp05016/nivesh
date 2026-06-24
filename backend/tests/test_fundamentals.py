from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_financials_empty():
    response = client.get("/fundamentals/RELIANCE/financials")
    assert response.status_code == 200
    assert response.json() == []

def test_get_shareholding_empty():
    response = client.get("/fundamentals/RELIANCE/shareholding")
    assert response.status_code == 200
    assert response.json() == []

def test_get_corporate_actions_empty():
    response = client.get("/fundamentals/RELIANCE/corporate-actions")
    assert response.status_code == 200
    assert response.json() == []

def test_get_valuation_not_found():
    response = client.get("/fundamentals/RELIANCE/valuation")
    assert response.status_code == 404
    assert response.json() == {"detail": "Valuation not found"}

def test_get_risk_signals_empty():
    response = client.get("/fundamentals/RELIANCE/risk-signals")
    assert response.status_code == 200
    assert response.json() == []
