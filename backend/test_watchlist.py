"""
Test script for invoking the watchlist endpoint using FastAPI's TestClient.
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
resp = client.get("/watchlist/1")
print(resp.status_code)
print(resp.json())
