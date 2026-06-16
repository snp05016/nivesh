import pytest
from database import get_session, YouTubeVideo

@pytest.mark.asyncio
async def test_run_youtube_harvester_real():
    from services.youtube_harvester import harvest_portfolio_videos, harvest_youtube_metadata
    with get_session() as session:
        initial_count = session.query(YouTubeVideo).count()
    added_portfolio = await harvest_portfolio_videos()
    added_metadata = await harvest_youtube_metadata()
    with get_session() as session:
        final_count = session.query(YouTubeVideo).count()
        assert final_count >= initial_count
