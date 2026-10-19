"""The scheduler runs in IST: explicit ids, tracking, expected fire times, market-hours alerts."""
import contextlib
import fcntl
import inspect
import io
import sys
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import services.harvest_worker as hw
from services import job_runs



@contextlib.contextmanager
def _real_apscheduler():
    """tests/conftest.py replaces apscheduler with a MagicMock; load the real package for a block."""
    prefixes = lambda k: k == "apscheduler" or k.startswith("apscheduler.")  # noqa: E731
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if prefixes(k)}
    try:
        yield
    finally:
        for k in [k for k in sys.modules if prefixes(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


IST = ZoneInfo("Asia/Kolkata")
MONDAY = datetime(2026, 10, 12, 0, 0, tzinfo=IST)


class FakeScheduler:
    def __init__(self, **kwargs):
        self.ctor_kwargs = kwargs
        self.jobs = []
        self.running = False

    def add_job(self, func, trigger, **kw):
        self.jobs.append(SimpleNamespace(func=func, trigger=trigger, kwargs=kw))

    def start(self):
        self.running = True


@pytest.fixture
def sched(monkeypatch):
    holder = {}
    monkeypatch.setattr(hw, "AsyncIOScheduler", lambda **kw: holder.setdefault("s", FakeScheduler(**kw)))
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", lambda *_a, **_k: io.StringIO(), raising=False)
    monkeypatch.setattr(fcntl, "lockf", lambda *_a, **_k: None)
    abandoned = []
    monkeypatch.setattr(job_runs, "mark_abandoned", lambda: abandoned.append(1) or 0)
    assert hw.start_scheduler() is True
    holder["s"].abandoned = abandoned
    return holder["s"]


def _job(sched, job_id):
    return next(j for j in sched.jobs if j.kwargs.get("id") == job_id)


def _fire(job, after=MONDAY):
    fields = {k: v for k, v in job.kwargs.items() if k in ("day", "day_of_week", "hour", "minute")}
    with _real_apscheduler():
        from apscheduler.triggers.cron import CronTrigger

        return CronTrigger(timezone=IST, **fields).get_next_fire_time(None, after)


def test_timezone_and_unique_ids(sched):
    assert sched.ctor_kwargs["timezone"] == "Asia/Kolkata"
    ids = [j.kwargs.get("id") for j in sched.jobs]
    assert all(ids), "every job needs an explicit id"
    assert len(ids) == len(set(ids)), "each job is registered once"


def test_every_job_is_tracked_and_sync(sched):
    for j in sched.jobs:
        assert j.func._job_runs_name == j.kwargs["id"]
        assert not inspect.iscoroutinefunction(j.func), j.kwargs["id"]


def test_async_job_stays_coroutine_after_wrapping():
    async def job():
        return 1

    assert inspect.iscoroutinefunction(hw._track_all_jobs(FakeScheduler()).add_job.__func__) is False
    proxy_sched = FakeScheduler()
    hw._track_all_jobs(proxy_sched).add_job(job, "cron", id="x", hour=1)
    assert inspect.iscoroutinefunction(proxy_sched.jobs[0].func)


# id -> (weekday of next fire from Monday 00:00 IST or None, hour, minute)
EXPECTED = {
    "advisor_harvest": (0, 7, 0),
    "morning_brief_pregen": (0, 6, 30),
    "error_digest": (0, 7, 0),
    "model_canary": (0, 8, 30),
    "portfolio_snapshot": (0, 16, 30),
    "portfolio_snapshot_retry": (0, 17, 30),
    "nightly_screen": (0, 16, 45),
    "bhavcopy": (0, 19, 0),
    "piotroski_weekly": (6, 23, 0),
    "legacy_outcome_eval": (0, 2, 0),
    "db_backup": (0, 2, 30),
    "prediction_outcomes": (0, 2, 40),
    "notification_cleanup": (0, 3, 0),
    "preferences_backfill": (0, 3, 5),
    "rag_ingest": (0, 3, 15),
    "retention": (0, 3, 20),
    "process_deletion_requests": (0, 3, 30),
    "corporate_actions": (0, 7, 30),
    "anomaly_scan": (0, 9, 30),
    "price_alerts": (0, 9, 0),
}


@pytest.mark.parametrize("job_id", sorted(EXPECTED))
def test_fire_time_ist(sched, job_id):
    weekday, hour, minute = EXPECTED[job_id]
    nxt = _fire(_job(sched, job_id))
    assert (nxt.weekday(), nxt.hour, nxt.minute) == (weekday, hour, minute)
    assert nxt.tzinfo is not None


def test_restore_drill_day_one(sched):
    nxt = _fire(_job(sched, "restore_drill"))
    assert (nxt.month, nxt.day, nxt.hour, nxt.minute) == (11, 1, 4, 0)


def test_price_alerts_only_during_market_hours(sched):
    job = _job(sched, "price_alerts")
    sat_morning = datetime(2026, 10, 17, 10, 0, tzinfo=IST)
    nxt = _fire(job, sat_morning)
    assert (nxt.day, nxt.hour, nxt.minute) == (19, 9, 0)  # Monday 2026-10-19
    mon_close = datetime(2026, 10, 19, 15, 56, tzinfo=IST)
    nxt = _fire(job, mon_close)
    assert (nxt.day, nxt.hour, nxt.minute) == (20, 9, 0)  # Tuesday
    last = _fire(job, datetime(2026, 10, 19, 15, 51, tzinfo=IST))
    assert (last.hour, last.minute) == (15, 55)


def test_mark_abandoned_once(sched):
    assert len(sched.abandoned) == 1


def test_research_jobs_pinned_to_utc(monkeypatch):
    from services.research import config, jobs

    monkeypatch.setattr(config, "CONFIG", SimpleNamespace(enabled=True, mode="shadow", degraded_reasons=()))
    fake = FakeScheduler()
    assert jobs.register_research_jobs(fake) == 7
    assert fake.jobs and all(j.kwargs["timezone"] == "UTC" for j in fake.jobs)
    assert all(j.trigger == "cron" for j in fake.jobs)
