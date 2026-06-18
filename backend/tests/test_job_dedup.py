# backend/tests/test_job_dedup.py
import os
import database

# Ensure tables exist (idempotent; safe against any SQLite DB)
database.init_db()


def _mk_user_jobs(uid):
    """Create one standard QUEUED job; return its job_id."""
    j = database.create_job(uid, "RELIANCE", "NSE", "standard")
    return j["job_id"]


def test_scoped_lookup_ignores_other_scan_type():
    uid = 990001
    std_id = _mk_user_jobs(uid)
    assert database.get_active_job_for_user_and_type(uid, "standard") is not None
    assert database.get_active_job_for_user_and_type(uid, "extreme") is None
    database.update_job(std_id, status="SUCCEEDED")


def test_scoped_lookup_same_type_blocks():
    uid = 990002
    ext = database.create_job(uid, "TCS", "NSE", "extreme")
    assert database.get_active_job_for_user_and_type(uid, "extreme") is not None
    database.update_job(ext["job_id"], status="SUCCEEDED")


def test_stale_job_not_active():
    uid = 990003
    j = database.create_job(uid, "INFY", "NSE", "standard")
    with database.get_session() as s:
        row = s.query(database.AnalysisJob).filter_by(job_id=j["job_id"]).first()
        import datetime
        row.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=900)
        s.commit()
    assert database.get_active_job_for_user_and_type(uid, "standard") is None
