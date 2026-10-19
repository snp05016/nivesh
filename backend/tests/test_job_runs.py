"""services/job_runs: tracked() rows, scrubbing, alert streaks, queries, retention, digest."""
import asyncio
import inspect
from contextlib import contextmanager
from datetime import timedelta

import pytest

from database import ENGINE, get_session
from models.db_models import JobRun
from services import job_runs


@pytest.fixture(autouse=True)
def _db():
    JobRun.__table__.create(ENGINE, checkfirst=True)
    with get_session() as s:
        s.query(JobRun).delete()
        s.commit()
    yield
    with get_session() as s:
        s.query(JobRun).delete()
        s.commit()


@pytest.fixture
def alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(job_runs, "notify_ops", lambda title, body: sent.append((title, body)) or True)
    return sent


def _rows(name=None):
    with get_session() as s:
        q = s.query(JobRun)
        if name:
            q = q.filter(JobRun.job_name == name)
        return [(r.status, r.rows_written, r.error, r.duration_ms, r.meta) for r in q.order_by(JobRun.id).all()]


def test_success_row(alerts):
    out = job_runs.tracked("j_ok", lambda: {"rows": 5, "x": 1})()
    assert out == {"rows": 5, "x": 1}
    status, rows, err, dur, meta = _rows("j_ok")[0]
    assert (status, rows, err) == ("ok", 5, None)
    assert dur is not None and meta == {"rows": 5, "x": 1}
    assert alerts == []


def test_failure_row_scrubbed_and_reraised(alerts):
    def boom():
        raise ValueError("bad user a@b.com token Bearer abc.def")

    with pytest.raises(ValueError):
        job_runs.tracked("j_bad", boom)()
    status, _, err, _, _ = _rows("j_bad")[0]
    assert status == "failed"
    assert "a@b.com" not in err and "abc.def" not in err and "<email>" in err
    assert alerts and alerts[0][0] == "Nivesh job failed: j_bad"


def test_async_wrapper(alerts):
    async def good():
        return 3

    async def bad():
        raise RuntimeError("nope")

    t_good, t_bad = job_runs.tracked("a_ok", good), job_runs.tracked("a_bad", bad)
    assert inspect.iscoroutinefunction(t_good) and t_good._job_runs_name == "a_ok"
    assert asyncio.run(t_good()) == 3
    with pytest.raises(RuntimeError):
        asyncio.run(t_bad())
    assert _rows("a_ok")[0][:2] == ("ok", 3)
    assert _rows("a_bad")[0][0] == "failed"


def test_no_asyncio_run_in_module():
    assert "asyncio.run" not in inspect.getsource(job_runs)


def test_bookkeeping_outage_does_not_stop_job(monkeypatch):
    @contextmanager
    def down():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(job_runs, "get_session", down)
    assert job_runs.tracked("j_x", lambda: 42)() == 42


def test_alert_streak_and_recovery(alerts):
    state = {"fail": True}

    def job():
        if state["fail"]:
            raise RuntimeError("x" * 900)
        return 1

    t = job_runs.tracked("streak", job)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            t()
    assert len(alerts) == 1 and len(alerts[0][1]) <= 300
    state["fail"] = False
    t()
    t()
    assert [a[0] for a in alerts] == ["Nivesh job failed: streak", "Nivesh job recovered: streak"]


def test_notify_ops_unset_and_post(monkeypatch):
    monkeypatch.delenv("OPS_ALERT_WEBHOOK_URL", raising=False)
    assert job_runs.notify_ops("t", "b") is False
    calls = []

    class R:
        def raise_for_status(self):
            pass

    monkeypatch.setenv("OPS_ALERT_WEBHOOK_URL", "https://ntfy.invalid/topic")
    monkeypatch.setattr(job_runs.httpx, "post", lambda url, **kw: calls.append((url, kw)) or R())
    assert job_runs.notify_ops("t", "b") is True
    assert calls[0][1]["headers"] == {"Title": "t"} and calls[0][1]["timeout"] == 5


def test_mark_abandoned(alerts):
    with get_session() as s:
        s.add(JobRun(job_name="r", status="running"))
        s.commit()
    assert job_runs.mark_abandoned() == 1
    assert _rows("r")[0][:3] == ("failed", None, "abandoned: scheduler restarted")
    assert alerts == []


@pytest.mark.parametrize("raw,needle", [
    ("mail me@x.in", "<email>"),
    ("pan ABCDE1234F end", "<pan>"),
    ("Authorization: Bearer abc123", "Bearer <redacted>"),
    ("postgres://user:pw@host/db", "://<redacted>@"),
    ("acct 123456789012", "<number>"),
])
def test_scrub(raw, needle):
    assert needle in job_runs.scrub(raw)


def test_scrub_truncates():
    assert len(job_runs.scrub("a" * 5000)) == 2000


def test_summary_list_and_latest(alerts):
    with get_session() as s:
        for st in ("ok", "ok", "ok", "failed"):
            s.add(JobRun(job_name="s1", status=st))
        s.add(JobRun(job_name="s2", status="ok"))
        s.add(JobRun(job_name="s2", status="running"))
        s.commit()
    out = job_runs.summary(days=7)
    jobs = {j["job_name"]: j for j in out["jobs"]}
    assert jobs["s1"]["success_pct"] == 75.0 and jobs["s1"]["last_status"] == "failed"
    assert jobs["s2"]["runs"] == 1
    assert out["overall_success_pct"] == 80.0
    page1 = job_runs.list_runs(limit=3)
    page2 = job_runs.list_runs(limit=3, before_id=page1[-1]["id"])
    assert len(page1) == 3 and page2[0]["id"] < page1[-1]["id"]
    assert job_runs.list_runs(job_name="s2", status="running")[0]["status"] == "running"
    latest = job_runs.latest_by_job()
    assert latest["s1"]["status"] == "failed" and latest["s2"]["status"] == "running"
    assert job_runs.summary(days=1000)["days"] == 90


def test_summary_empty():
    assert job_runs.summary()["overall_success_pct"] is None


def test_purge():
    with get_session() as s:
        s.add(JobRun(job_name="old", status="ok", started_at=job_runs._now() - timedelta(days=100)))
        s.add(JobRun(job_name="new", status="ok"))
        s.commit()
    assert job_runs.purge_older_than(90) == 1
    assert [r[0] for r in _rows()] == ["ok"]


def test_retention_reports_job_runs(monkeypatch):
    from services import retention

    monkeypatch.setattr(retention, "_rotate_token_log", lambda: 0)
    with get_session() as s:
        s.add(JobRun(job_name="old", status="ok", started_at=job_runs._now() - timedelta(days=100)))
        s.commit()
    assert retention.run_retention().get("job_runs_deleted") == 1


def test_digest_block(monkeypatch):
    from services import error_telemetry

    with get_session() as s:
        s.add(JobRun(job_name="dj", status="failed"))
        s.add(JobRun(job_name="dj", status="ok"))
        s.commit()
    text = "\n".join(error_telemetry._scheduled_jobs_block())
    assert "Scheduled jobs (last 24h)" in text and "dj: 1 failed of 2" in text

    def boom(**_k):
        raise RuntimeError("x")

    monkeypatch.setattr(job_runs, "summary", boom)
    assert "Scheduled jobs: UNKNOWN - query failed" in "\n".join(error_telemetry._scheduled_jobs_block())


def test_merge_harvest_status(monkeypatch):
    monkeypatch.setattr(job_runs, "latest_by_job", lambda: {
        "seen": {"status": "ok", "started_at": "t", "error": None, "meta": {"a": 1}},
        "new": {"status": "ok", "started_at": "t2", "error": None, "meta": {"a": 1}},
    })
    out = job_runs.merge_harvest_status({"seen": {"status": "running"}})
    assert out["seen"] == {"status": "running"}
    assert out["new"] == {"status": "idle", "last_run": "t2", "last_result": {"a": 1}}
