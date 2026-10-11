"""AUTH-17: DB-counted admission caps for analysis and stress-test workers, and a
cancel recorded by any API worker stops the job's subprocess."""
import threading
import types
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException

import database
from models.db_models import AnalysisJob, User
from services import job_manager


def _user() -> int:
    with database.get_session() as session:
        user = User(username=f"adm_{uuid4().hex[:12]}", password_hash="x", display_name="Admission Test")
        session.add(user)
        session.commit()
        session.refresh(user)
        return cast(int, user.id)


def _active(job_id: str, user_id, scan_type: str = "deep") -> dict:
    return {"job_id": job_id, "user_id": user_id, "scan_type": scan_type,
            "created_at": datetime.now(timezone.utc).isoformat()}


def _statuses(user_id: int) -> list:
    with database.get_session() as session:
        return [j.status for j in session.query(AnalysisJob).filter(AnalysisJob.user_id == user_id)]


@pytest.fixture
def started(monkeypatch, real_spawn_job):
    """Real spawn_job -> spawn_process with a fake Process; collects the started workers."""
    procs = []

    class _Proc:
        pid = 4242

        def __init__(self, target=None, args=(), daemon=None):
            procs.append(args)

        def start(self):
            pass

        def is_alive(self):
            return False

    monkeypatch.setattr(job_manager.multiprocessing, "Process", _Proc)
    monkeypatch.setattr(database, "get_analysis_for_date", lambda *a, **k: None)  # cache miss
    return procs


def test_job_under_the_caps_starts_a_worker(client, started, monkeypatch):
    uid = _user()
    monkeypatch.setattr(job_manager, "MAX_CONCURRENT_JOBS", 2)
    monkeypatch.setattr(job_manager, "MAX_JOBS_PER_USER", 1)
    monkeypatch.setattr(job_manager.job_repo, "list_active_jobs", lambda: [_active("busy-1", 990001)])

    resp = client.post("/analyze", json={"ticker": "RELIANCE", "exchange": "NSE", "user_id": uid})

    assert resp.status_code == 202
    assert len(started) == 1
    job_manager.cancel_job(resp.json()["job_id"])


def test_platform_cap_returns_503_without_starting_a_worker(client, started, monkeypatch):
    uid = _user()
    monkeypatch.setattr(job_manager, "MAX_CONCURRENT_JOBS", 2)
    monkeypatch.setattr(job_manager.job_repo, "list_active_jobs",
                        lambda: [_active("busy-1", 990001), _active("busy-2", 990002)])

    resp = client.post("/analyze", json={"ticker": "RELIANCE", "exchange": "NSE", "user_id": uid})

    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "30"
    assert resp.json()["error_code"] == "CAPACITY"
    assert started == []
    assert _statuses(uid) == ["FAILED"]


@pytest.mark.parametrize("anonymous", [True, False])
def test_owner_cap_spans_scan_types_and_returns_429(client, started, monkeypatch, anonymous):
    # Anonymous callers share one owner bucket; the running job is another scan type.
    uid = None if anonymous else _user()
    monkeypatch.setattr(job_manager, "MAX_JOBS_PER_USER", 1)
    monkeypatch.setattr(job_manager.job_repo, "list_active_jobs", lambda: [_active("deep-1", uid)])
    resp = client.post("/analyze", json={"ticker": "RELIANCE", "exchange": "NSE",
                                         "user_id": uid, "scan_type": "extreme"})

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "30"
    assert resp.json()["error_code"] == "TOO_MANY_JOBS"
    assert started == []


def test_stress_test_counts_toward_the_owner_cap(monkeypatch):
    from routers import stress_test as stress_test_router
    from services.stress_test_jobs import StressTestLaunch

    launch = StressTestLaunch(job_id="stress-cap", holdings=[], scenarios=[])
    monkeypatch.setattr(stress_test_router, "prepare_stress_test_job", lambda *_a, **_k: launch)
    monkeypatch.setattr(stress_test_router, "mark_stress_test_start_failed", lambda *_a: None)
    monkeypatch.setattr(job_manager, "MAX_JOBS_PER_USER", 1)
    monkeypatch.setattr(job_manager.job_repo, "list_active_jobs", lambda: [_active("std-1", 7, "standard")])

    with pytest.raises(HTTPException) as exc:
        stress_test_router.start_stress_test(
            stress_test_router.StressTestRequest(portfolio_id="holdings"), user_id=7)

    assert exc.value.status_code == 429
    assert "Too many analyses" in exc.value.detail


class _Beats(threading.Event):
    """A stop event that lets `n` heartbeats run, then ends the loop."""

    def __init__(self, n: int):
        super().__init__()
        self.left = n

    def wait(self, timeout=None) -> bool:
        self.left -= 1
        return self.left < 0


def test_heartbeat_stops_a_worker_cancelled_by_another_api_worker(monkeypatch):
    # cancel_job only terminates processes its own API worker started; the subprocess
    # must notice a cancel recorded anywhere else on its own.
    import services.job_worker as job_worker

    class _Exited(Exception):
        pass

    def _exit(code):
        raise _Exited(code)

    beats = []
    monkeypatch.setattr(job_worker, "threading", types.SimpleNamespace(
        Thread=lambda target, daemon: types.SimpleNamespace(start=lambda: beats.append(target))))
    monkeypatch.setattr(job_worker, "os", types.SimpleNamespace(_exit=_exit))
    job_id = database.create_job(None, "TCS", "NSE", "standard")["job_id"]

    job_worker._start_heartbeat(job_id, _Beats(1))
    beats.pop()()  # still active: one heartbeat, the worker keeps running

    job_manager.cancel_job(job_id)  # recorded by an API worker that does not own the process
    job_worker._start_heartbeat(job_id, _Beats(1))
    with pytest.raises(_Exited):
        beats.pop()()
