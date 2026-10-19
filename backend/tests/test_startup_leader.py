"""DB-13: one-time startup tasks run only in the worker holding the scheduler lock."""
import asyncio
import fcntl
import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import database
import core.lifecycle as lifecycle
import services.harvest_worker as hw
import services.harvester_db


def _run_startup(monkeypatch, leader: bool) -> MagicMock:
    calls = MagicMock()
    calls.sweep.return_value = 0
    monkeypatch.setattr("core.logging_config.configure_logging", calls.configure_logging)
    monkeypatch.setattr(lifecycle, "start_scheduler", lambda: leader)
    monkeypatch.setattr(lifecycle, "init_db", calls.init_db)
    monkeypatch.setattr(lifecycle, "_seed_catalogs", calls.seed_catalogs)
    monkeypatch.setattr(lifecycle, "threading", SimpleNamespace(Thread=calls.Thread))
    monkeypatch.setattr(database, "sweep_stale_jobs", calls.sweep)
    monkeypatch.setattr(services.harvester_db, "init_harvester_db", calls.init_harvester_db)
    monkeypatch.setattr(hw, "_seed_harvester_sources", calls.seed_harvester_sources)
    asyncio.run(lifecycle.on_startup())
    return calls


_ONE_TIME = ("init_db", "sweep", "init_harvester_db", "seed_harvester_sources",
             "seed_catalogs", "Thread")


def test_follower_skips_one_time_tasks(monkeypatch):
    monkeypatch.delenv("NIVESH_TESTING", raising=False)  # tests are otherwise always leader
    calls = _run_startup(monkeypatch, leader=False)

    calls.configure_logging.assert_called_once()
    for name in _ONE_TIME:
        assert not getattr(calls, name).called, name


def test_testing_env_is_leader_even_when_lock_held(monkeypatch):
    monkeypatch.setenv("NIVESH_TESTING", "1")
    calls = _run_startup(monkeypatch, leader=False)

    calls.seed_catalogs.assert_called_once()


def test_leader_runs_one_time_tasks_once(monkeypatch):
    calls = _run_startup(monkeypatch, leader=True)

    for name in _ONE_TIME:
        assert getattr(calls, name).call_count == 1, name
    calls.sweep.assert_called_once_with(90)


def _fresh_scheduler(monkeypatch, lockf):
    sched = MagicMock()
    monkeypatch.setattr(hw, "AsyncIOScheduler", lambda **_kw: sched)
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", lambda *_a, **_k: io.StringIO(), raising=False)  # no real lock file
    monkeypatch.setattr(fcntl, "lockf", lockf)
    return sched


def test_start_scheduler_false_when_lock_held(monkeypatch):
    def _held(*_a, **_k):
        raise IOError("lock held by another worker")

    sched = _fresh_scheduler(monkeypatch, _held)

    assert hw.start_scheduler() is False
    sched.start.assert_not_called()


def test_start_scheduler_true_and_schedules_job_sweep(monkeypatch):
    from repositories.job_repo import sweep_stale_jobs

    sched = _fresh_scheduler(monkeypatch, lambda *_a, **_k: None)

    assert hw.start_scheduler() is True
    jobs = {c.kwargs.get("id"): c for c in sched.add_job.call_args_list}
    sweep = jobs["job_sweep"]
    assert sweep.args[0].__wrapped__ is sweep_stale_jobs  # wrapped by job_runs.tracked
    assert sweep.args[1] == "interval" and sweep.kwargs["minutes"] == 2
