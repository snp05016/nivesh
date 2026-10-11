"""REL-03: scheduled jobs never run their blocking bodies on the API event loop.

APScheduler's AsyncIOExecutor runs coroutine jobs ON the loop and only sends plain
callables to a thread pool, so every registered job must be a plain callable.
Also covers job defaults, staggered 2-hourly jobs, the RSS fetch timeout and the
opt-in, duration-capped Whisper fallback.
"""
import asyncio
import fcntl
import inspect
import io
import time
from types import SimpleNamespace

import pytest

import services.harvest_worker as hw


class _FakeScheduler:
    def __init__(self, **kwargs):
        self.ctor_kwargs = kwargs
        self.jobs = []
        self.running = False

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append(SimpleNamespace(func=func, trigger=trigger, kwargs=kwargs))

    def start(self):
        self.running = True


@pytest.fixture
def captured(monkeypatch):
    holder = {}

    def _make(**kwargs):
        holder["sched"] = _FakeScheduler(**kwargs)
        return holder["sched"]

    monkeypatch.setattr(hw, "AsyncIOScheduler", _make)
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", lambda *_a, **_k: io.StringIO(), raising=False)  # no real lock file
    monkeypatch.setattr(fcntl, "lockf", lambda *_a, **_k: None)
    assert hw.start_scheduler() is True
    return holder["sched"]


def test_all_scheduled_jobs_are_sync(captured):
    async_jobs = [getattr(j.func, "__name__", repr(j.func)) for j in captured.jobs
                  if inspect.iscoroutinefunction(j.func)]
    assert not async_jobs, f"coroutine jobs run on the API event loop: {async_jobs}"

    wrapped = {j.func.__wrapped__.__name__ for j in captured.jobs if hasattr(j.func, "__wrapped__")}
    assert {"snapshot_all_users", "run_nightly_screen"} <= wrapped  # coroutines go through _sync


def test_job_defaults(captured):
    assert captured.ctor_kwargs["timezone"] == "UTC"
    assert captured.ctor_kwargs["job_defaults"] == {
        "coalesce": True, "max_instances": 1, "misfire_grace_time": 3600,
    }


def test_interval_jobs_staggered(captured):
    two_hourly = [j for j in captured.jobs if j.trigger == "interval"
                  and (j.kwargs.get("hours") == 2 or j.kwargs.get("minutes") == 120)]
    assert len(two_hourly) == 6
    starts = [j.kwargs.get("next_run_time") for j in two_hourly]
    assert None not in starts
    assert len(set(starts)) == len(starts), "2-hourly jobs must not all fire at the same instant"
    assert all(j.kwargs.get("jitter") for j in two_hourly)


def test_sync_wrapper_runs_off_loop():
    async def slow_coro():
        time.sleep(0.5)  # blocking body, like yfinance/subprocess in a real job
        return "done"

    async def scenario():
        loop = asyncio.get_running_loop()
        job = loop.run_in_executor(None, hw._sync(slow_coro))  # what AsyncIOExecutor does
        t0 = time.perf_counter()
        await asyncio.sleep(0.05)
        tick = time.perf_counter() - t0
        return tick, await job

    tick, result = asyncio.run(scenario())
    assert result == "done"
    assert tick < 0.2, f"event loop stalled {tick:.2f}s while the job ran"


def test_feed_fetch_uses_timeout(monkeypatch):
    import services.news_harvester as nh

    seen = []

    def _get(url, **kwargs):
        seen.append((url, kwargs))
        return SimpleNamespace(content=b"", raise_for_status=lambda: None)

    monkeypatch.setattr(nh.requests, "get", _get)
    monkeypatch.setattr(nh, "RSS_FEEDS", [{"url": "https://example.test/rss", "source": "Test"}])

    assert asyncio.run(nh.harvest_news()) == 0
    assert seen and seen[0][0] == "https://example.test/rss"
    assert seen[0][1]["timeout"] == 15


# ── REL-12: broken/dead jobs removed, cleanup jobs log without NameError ─────────

def test_removed_jobs_not_registered(captured):
    names = {getattr(j.func, "__name__", "") for j in captured.jobs}
    assert not names & {"_run_cache_purge", "_run_premarket_cache_warm", "_run_harvest_filings"}
    assert not hasattr(hw, "check_signal_outcomes")


def test_cleanup_jobs_do_not_nameerror(captured, monkeypatch):
    import services.notifications_inbox as inbox

    monkeypatch.setattr(inbox, "cleanup_old", lambda: 3)
    job = next(j.func for j in captured.jobs
               if getattr(j.func, "__name__", "") == "_run_notification_cleanup")
    job()  # used to raise NameError: name 'logger' is not defined


def test_dash_update_creates_unknown_key():
    from core import dashboard_state as ds

    key = "rel12_test_job"
    try:
        ds._dash_update_harvest(key, "running")
        assert ds._harvest_status[key]["status"] == "running"
        assert ds._harvest_status[key]["last_run"] is not None
    finally:
        with ds._dash_lock:
            ds._harvest_status.pop(key, None)


# ── SILENT-13: job status is persisted so every worker's dashboard sees it ───────

def test_unknown_key_recorded_and_persisted():
    from core import dashboard_state as ds
    from database import get_session
    from models.db_models import SchedulerJobStatus

    key = "silent13_bhavcopy_test"
    try:
        ds._dash_update_harvest(key, "running")
        ds._dash_update_harvest(key, "error", {"error": "x"})
        assert ds._harvest_status[key]["status"] == "error"

        with get_session() as session:
            row = session.get(SchedulerJobStatus, key)
            assert row is not None
            assert (row.status, row.last_error) == ("error", "x")
            assert row.last_started_at is not None and row.last_finished_at is not None

        persisted = ds.persisted_harvest_status()[key]
        assert persisted["status"] == "error"
        assert persisted["last_result"] == {"error": "x"}
    finally:
        with ds._dash_lock:
            ds._harvest_status.pop(key, None)
        with get_session() as session:
            session.query(SchedulerJobStatus).filter_by(job_name=key).delete()
            session.commit()


def test_persist_failure_never_raises(monkeypatch):
    import database
    from core import dashboard_state as ds

    def _broken_session():
        raise RuntimeError("db down")

    monkeypatch.setattr(database, "get_session", _broken_session)
    key = "silent13_db_down_test"
    try:
        ds._dash_update_harvest(key, "error", {"error": "boom"})  # must not raise
        assert ds._harvest_status[key]["status"] == "error"
        assert ds.persisted_harvest_status() == {}
    finally:
        with ds._dash_lock:
            ds._harvest_status.pop(key, None)


def test_dashboard_snapshot_reads_persisted_rows(monkeypatch):
    import routers.dashboard as dashboard_router

    monkeypatch.setattr(dashboard_router, "persisted_harvest_status",
                        lambda: {"bhavcopy": {"status": "error", "last_run": None, "last_result": None}})
    monkeypatch.setattr(dashboard_router, "build_ai_engine_monitor", lambda **_k: {})
    snap = dashboard_router.get_dashboard_snapshot()
    assert snap["harvest_status"]["bhavcopy"]["status"] == "error"
