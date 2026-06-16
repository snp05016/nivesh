import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_session, NewsArticle

client = TestClient(app)

def test_home_feed_guest():
    response = client.get("/api/v1/home-feed?user_id=0")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_run_news_harvester_real():
    from services.news_harvester import harvest_news
    with get_session() as session:
        initial_count = session.query(NewsArticle).count()
    added_count = await harvest_news()
    with get_session() as session:
        final_count = session.query(NewsArticle).count()
        assert final_count >= initial_count
