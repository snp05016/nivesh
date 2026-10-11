"""DB-11: analysis jobs follow an atomic state machine.

One active (QUEUED/RUNNING) job per user and scan_type is enforced by a partial
unique index, terminal rows are never overwritten, and the stale sweep spares
jobs whose worker pid is alive. Uses the per-session temp DB from conftest.
"""
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

import database
from models.db_models import AnalysisJob, User
from repositories.job_repo import JobAlreadyActive


def _uid() -> int:
    uid = random.randint(500_000_000, 599_999_999)
    with database.get_session() as s:
        s.add(User(id=uid, username=f"jsm_{uid}", password_hash="x", display_name="JSM"))
        s.commit()
    return uid


def _set(job_id: str, **fields) -> None:
    with database.get_session() as s:
        s.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).update(
            {k: v for k, v in fields.items()}, synchronize_session=False)
        s.commit()


def _job(job_id: str) -> dict:
    job = database.get_job(job_id)
    assert job is not None
    return job


def _active_count(uid: int, scan_type: str) -> int:
    with database.get_session() as s:
        return s.query(AnalysisJob).filter(
            AnalysisJob.user_id == uid,
            AnalysisJob.scan_type == scan_type,
            AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
        ).count()


def test_full_uuid_job_id():
    job = database.create_job(_uid(), "RELIANCE", "NSE", "standard")
    assert len(job["job_id"]) == 36


def test_duplicate_create_raises_job_already_active():
    uid = _uid()
    first = database.create_job(uid, "TCS", "NSE", "extreme")
    with pytest.raises(JobAlreadyActive) as exc:
        database.create_job(uid, "INFY", "NSE", "extreme")
    assert exc.value.job["job_id"] == first["job_id"]
    assert _active_count(uid, "extreme") == 1
    # Another scan_type is a separate slot.
    database.create_job(uid, "INFY", "NSE", "standard")


def test_stale_active_does_not_block():
    uid = _uid()
    old = database.create_job(uid, "WIPRO", "NSE", "standard")
    _set(old["job_id"], status="RUNNING",
         created_at=datetime.now(timezone.utc) - timedelta(hours=1))

    new = database.create_job(uid, "WIPRO", "NSE", "standard")

    assert new["status"] == "QUEUED"
    assert _job(old["job_id"])["status"] == "FAILED"
    assert _active_count(uid, "standard") == 1


def test_update_after_cancel_rejected():
    job = database.create_job(_uid(), "HDFCBANK", "NSE", "deep")
    assert database.update_job(job["job_id"], status="CANCELLED") is True

    assert database.update_job(job["job_id"], status="SUCCEEDED", result_json="{}") is False
    assert database.update_job(job["job_id"]) is False  # heartbeat-only CAS too

    got = _job(job["job_id"])
    assert got["status"] == "CANCELLED"
    assert "result" not in got


def test_checkpoint_ignored_after_terminal():
    job = database.create_job(_uid(), "ITC", "NSE", "standard")
    database.update_job(job["job_id"], status="CANCELLED")
    database.append_checkpoint(job["job_id"], stage="late", agent="Engine",
                               message="after cancel", state="running", pct=50)
    got = _job(job["job_id"])
    assert got["checkpoints"] == []
    assert got["progress_pct"] == 0


def test_cancel_keeps_cancelled_checkpoint():
    from services.job_manager import cancel_job
    job = database.create_job(_uid(), "SBIN", "NSE", "standard")
    cancel_job(job["job_id"])
    got = _job(job["job_id"])
    assert got["status"] == "CANCELLED"
    assert got["checkpoints"][-1]["stage"] == "cancelled"


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_sweep_skips_live_pid():
    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    live = database.create_job(_uid(), "LT", "NSE", "standard")
    _set(live["job_id"], status="RUNNING", pid=os.getpid(), heartbeat_at=stale)
    dead = database.create_job(_uid(), "LT", "NSE", "standard")
    _set(dead["job_id"], status="RUNNING", pid=_dead_pid(), heartbeat_at=stale)

    assert database.sweep_stale_jobs(90) >= 1

    assert _job(live["job_id"])["status"] == "RUNNING"
    assert _job(dead["job_id"])["status"] == "FAILED"


def test_sweep_never_overwrites_terminal():
    job = database.create_job(_uid(), "ONGC", "NSE", "standard")
    database.update_job(job["job_id"], status="SUCCEEDED")
    _set(job["job_id"], heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    database.sweep_stale_jobs(90)
    assert _job(job["job_id"])["status"] == "SUCCEEDED"


def test_concurrent_analyze_yields_one_409(client, spawned_jobs, monkeypatch):
    """Both requests pass the read-only pre-check (the race); the index decides."""
    uid = _uid()
    monkeypatch.setattr(database, "get_active_job_for_user_and_type", lambda *_a, **_k: None)
    body = {"ticker": "MARUTI", "exchange": "NSE", "user_id": uid, "scan_type": "standard"}

    first = client.post("/analyze", json=body)
    second = client.post("/analyze", json=body)

    assert first.status_code == 202, first.text
    assert second.status_code == 409, second.text
    assert second.json()["error_code"] == "ALREADY_RUNNING"
    assert second.json()["job_id"] == first.json()["job_id"]
    assert len(spawned_jobs) == 1
    assert _active_count(uid, "standard") == 1
