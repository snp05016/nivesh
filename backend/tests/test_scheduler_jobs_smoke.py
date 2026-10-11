"""PERF-25: no broken filesystem-cache jobs are scheduled, and the plain sync
jobs run once without raising (they used an undefined module-level `logger`)."""
import contextlib
import fcntl
import importlib.util
import io
import os
from unittest.mock import MagicMock

import database
import services.harvest_worker as hw
import services.notifications_inbox as notifications_inbox


def _scheduled_funcs(monkeypatch) -> dict:
    sched = MagicMock()
    monkeypatch.setattr(hw, "AsyncIOScheduler", lambda **_kw: sched)
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", lambda *_a, **_k: io.StringIO(), raising=False)  # no real lock file
    monkeypatch.setattr(fcntl, "lockf", lambda *_a, **_k: None)

    assert hw.start_scheduler() is True
    return {getattr(c.args[0], "__name__", repr(c.args[0])): c.args[0] for c in sched.add_job.call_args_list}


def test_no_broken_cache_jobs(monkeypatch):
    funcs = _scheduled_funcs(monkeypatch)

    for dead in ("_run_cache_purge", "_run_premarket_cache_warm", "_run_harvest_filings"):
        assert dead not in funcs, dead


def test_registered_sync_jobs_do_not_raise(monkeypatch):
    funcs = _scheduled_funcs(monkeypatch)
    monkeypatch.setattr(notifications_inbox, "cleanup_old", lambda: 0)

    session = MagicMock()
    session.query.return_value.distinct.return_value.all.return_value = []
    session.query.return_value.all.return_value = []

    @contextlib.contextmanager
    def _fake_session():
        yield session

    monkeypatch.setattr(database, "get_session", _fake_session)

    funcs["_run_notification_cleanup"]()
    funcs["_run_backfill_preferences"]()
    session.commit.assert_called_once()


def test_disk_cache_has_no_filesystem_leftovers():
    # tests/conftest.py replaces services.disk_cache with a MagicMock; load the real file.
    path = os.path.join(os.path.dirname(hw.__file__), "disk_cache.py")
    spec = importlib.util.spec_from_file_location("_real_disk_cache_smoke", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert not hasattr(mod, "purge_expired")
    assert not hasattr(mod, "CACHE_ROOT")
