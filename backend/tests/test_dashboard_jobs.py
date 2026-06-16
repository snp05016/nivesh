"""Task 9 — dashboard snapshot surfaces DB-backed active jobs."""
import random

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_table():
    import database
    database.Base.metadata.create_all(database.ENGINE)


def test_snapshot_includes_db_active_jobs():
    import database
    from routers.dashboard import get_dashboard_snapshot
    uid = random.randint(40_000_000, 49_999_999)
    with database.get_session() as session:
        session.add(database.User(
            id=uid,
            username=f"job_test_{uid}",
            password_hash="test",
            display_name="Job Test",
        ))
        session.commit()
    j = database.create_job(uid, "RELIANCE", "NSE", "extreme")
    database.update_job(j["job_id"], status="RUNNING", progress_pct=42, stage="debate")

    snap = get_dashboard_snapshot()
    jobs = snap["active_analyses"]
    assert j["job_id"] in jobs
    assert jobs[j["job_id"]]["progress_pct"] == 42
    assert jobs[j["job_id"]]["stage"] == "debate"

    # once terminal, it drops out of the active panel
    database.update_job(j["job_id"], status="SUCCEEDED")
    assert j["job_id"] not in get_dashboard_snapshot()["active_analyses"]
