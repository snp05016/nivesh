"""Task 1 — AnalysisJob model + DAO lifecycle, one-active-per-user, crash sweep.

Uses the isolated stockapp_test.db configured by conftest. Unique user_ids per test
keep rows from colliding across runs.
"""
import random
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_table():
    import database
    database.Base.metadata.create_all(database.ENGINE)


def _uid():
    import database
    from models.db_models import User
    uid = random.randint(10_000_000, 99_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"test_{uid}", password_hash="x", display_name="Test"))
        session.commit()
    return uid


def test_job_lifecycle():
    import database
    job = database.create_job(_uid(), "RELIANCE", "NSE", "extreme")
    assert job["status"] == "QUEUED"
    assert len(job["job_id"]) == 12

    database.update_job(job["job_id"], status="RUNNING", pid=4242,
                        progress_pct=10, stage="market")
    database.append_checkpoint(job["job_id"], stage="market", agent="Market Analyst",
                               message="reading indicators", state="running", pct=15)
    got = database.get_job(job["job_id"])
    assert got["status"] == "RUNNING"
    assert got["pid"] == 4242
    assert got["checkpoints"][-1]["agent"] == "Market Analyst"
    assert got["progress_pct"] == 15


def test_result_json_surfaced_on_success():
    import database
    job = database.create_job(_uid(), "TCS", "NSE", "extreme")
    database.update_job(job["job_id"], status="SUCCEEDED",
                        result_json='{"signal": "BUY"}', progress_pct=100)
    got = database.get_job(job["job_id"])
    assert got["status"] == "SUCCEEDED"
    assert got["result"] == {"signal": "BUY"}


def test_token_accumulation():
    import database
    job = database.create_job(_uid(), "INFY", "NSE", "extreme")
    assert database.add_job_tokens(job["job_id"], 1000) == 1000
    assert database.add_job_tokens(job["job_id"], 500) == 1500


def test_one_active_per_user():
    import database
    uid = _uid()
    j1 = database.create_job(uid, "HDFCBANK", "NSE", "extreme")
    database.update_job(j1["job_id"], status="RUNNING")
    assert database.get_active_job_for_user(uid)["job_id"] == j1["job_id"]
    database.update_job(j1["job_id"], status="SUCCEEDED")
    assert database.get_active_job_for_user(uid) is None


def test_sweep_stale_running_marks_failed():
    import database
    j = database.create_job(_uid(), "WIPRO", "NSE", "standard")
    database.update_job(j["job_id"], status="RUNNING",
                        heartbeat_at=datetime.now(timezone.utc) - timedelta(seconds=300))
    n = database.sweep_stale_jobs(max_heartbeat_age_sec=90)
    assert n >= 1
    assert database.get_job(j["job_id"])["status"] == "FAILED"
