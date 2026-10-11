from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_home_feed_guest():
    response = client.get("/api/v1/home-feed?user_id=0")
    assert response.status_code == 200
