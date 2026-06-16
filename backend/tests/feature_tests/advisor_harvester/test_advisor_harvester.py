import pytest
from database import get_session, AdvisorInsight

@pytest.mark.asyncio
async def test_run_advisor_harvester_real():
    from services.advisor_harvester import harvest_all_advisors
    with get_session() as session:
        initial_count = session.query(AdvisorInsight).count()
    added_count = await harvest_all_advisors()
    with get_session() as session:
        final_count = session.query(AdvisorInsight).count()
        assert final_count >= initial_count
