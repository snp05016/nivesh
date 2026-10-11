"""REL-05: analysis job lifecycle — CAS status, ghost-job filter, periodic sweep,
shutdown marking, registry reaping and one shared wall-clock limit table.

Uses the isolated test DB configured by conftest; a fresh user per test keeps the
one-active-job-per-(user, scan_type) index from colliding across runs.
"""
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_table():
    import database
    database.Base.metadata.create_all(database.ENGINE)


def _uid() -> int:
    import database
    from models.db_models import User
    uid = random.randint(10_000_000, 99_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"rel05_{uid}", password_hash="x", display_name="Test"))
        session.commit()
    return uid


def _set(job_id: str, **fields) -> None:
    import database
    from models.db_models import AnalysisJob
    values: Any = fields
    with database.get_session() as session:
        session.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).update(
            values, synchronize_session=False)
        session.commit()


def _get(job_id: str) -> dict:
    import database
    job = database.get_job(job_id)
    assert job is not None
    return job


def _active(user_id: int) -> dict:
    import database
    job = database.get_active_job_for_user(user_id)
    assert job is not None
    return job


def _ago(seconds: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


def test_update_job_does_not_overwrite_cancelled():
    import database
    job = database.create_job(_uid(), "TCS", "NSE", "standard")
    assert database.update_job(job["job_id"], status="CANCELLED") is True
    assert database.update_job(job["job_id"], status="SUCCEEDED") is False
    assert _get(job["job_id"])["status"] == "CANCELLED"


def test_heartbeat_touch_false_once_cancelled():
    import database
    job = database.create_job(_uid(), "INFY", "NSE", "standard")
    assert database.update_job(job["job_id"]) is True  # heartbeat-only refresh
    database.update_job(job["job_id"], status="CANCELLED")
    assert database.update_job(job["job_id"]) is False  # worker's beat sees it and exits


def test_active_job_for_user_ignores_stale():
    import database
    uid = _uid()
    old = database.create_job(uid, "WIPRO", "NSE", "extreme")
    _set(old["job_id"], status="RUNNING", created_at=_ago(2 * 3600))
    assert database.get_active_job_for_user(uid) is None

    fresh = database.create_job(uid, "WIPRO", "NSE", "standard")
    assert _active(uid)["job_id"] == fresh["job_id"]


def test_sweep_marks_dead_heartbeat_failed():
    import database
    dead = database.create_job(_uid(), "SBIN", "NSE", "standard")
    _set(dead["job_id"], status="RUNNING", pid=None, heartbeat_at=_ago(300))
    alive = database.create_job(_uid(), "SBIN", "NSE", "standard")
    _set(alive["job_id"], status="RUNNING", pid=None, heartbeat_at=_ago(5))

    database.sweep_stale_jobs(90)

    assert _get(dead["job_id"])["status"] == "FAILED"
    assert _get(alive["job_id"])["status"] == "RUNNING"


def test_sweep_fails_overrun_job_even_if_pid_alive():
    import database
    job = database.create_job(_uid(), "ITC", "NSE", "extreme")
    # os.getpid() is alive (a reused pid looks the same); heartbeat fresh, but the
    # row is far past every wall-clock budget.
    _set(job["job_id"], status="RUNNING", pid=os.getpid(),
         heartbeat_at=_ago(5), created_at=_ago(2 * 3600))

    database.sweep_stale_jobs(90)

    assert _get(job["job_id"])["status"] == "FAILED"


class _FakeProc:
    def __init__(self, alive: bool):
        self._alive = alive
        self.closed = False

    def is_alive(self):
        return self._alive

    def terminate(self):
        self._alive = False

    def kill(self):
        self._alive = False

    def join(self, *_a, **_k):
        pass

    def close(self):
        self.closed = True


def test_shutdown_all_marks_owned_jobs_failed():
    import database
    import services.job_manager as jm
    job = database.create_job(_uid(), "LT", "NSE", "standard")
    with jm._registry_lock:
        jm._job_registry[job["job_id"]] = _FakeProc(alive=False)  # type: ignore[assignment]

    jm.shutdown_all()

    got = _get(job["job_id"])
    assert got["status"] == "FAILED"
    assert got["error"] == "Interrupted by server restart"
    assert job["job_id"] not in jm._job_registry


def test_shutdown_all_keeps_finished_status():
    import database
    import services.job_manager as jm
    job = database.create_job(_uid(), "ONGC", "NSE", "standard")
    database.update_job(job["job_id"], status="SUCCEEDED", result_json="{}")
    with jm._registry_lock:
        jm._job_registry[job["job_id"]] = _FakeProc(alive=False)  # type: ignore[assignment]

    jm.shutdown_all()

    assert _get(job["job_id"])["status"] == "SUCCEEDED"


def test_reap_finished_closes_dead_handles():
    import services.job_manager as jm
    dead, live = _FakeProc(alive=False), _FakeProc(alive=True)
    with jm._registry_lock:
        jm._job_registry["rel05_dead"] = dead  # type: ignore[assignment]
        jm._job_registry["rel05_live"] = live  # type: ignore[assignment]

    jm.reap_finished()

    assert dead.closed and not live.closed
    assert "rel05_dead" not in jm._job_registry
    with jm._registry_lock:
        assert jm._job_registry.pop("rel05_live") is live


def test_limits_single_source():
    from repositories import job_repo
    from services import job_worker
    assert job_worker.WALLCLOCK_LIMITS is job_repo.WALLCLOCK_LIMITS
