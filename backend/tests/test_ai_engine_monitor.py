"""AI engine monitor core mirrors check_stock.sh job visibility."""

import json
import random
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_tables():
    import database

    database.Base.metadata.create_all(database.ENGINE)


def _uid() -> int:
    import database
    from models.db_models import User

    uid = random.randint(100_000_000, 999_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"ai_engine_{uid}", password_hash="x", display_name="Test"))
        session.commit()
    return uid


def _set_job_fields(job_id: str, **fields) -> None:
    import database
    from models.db_models import AnalysisJob

    with database.get_session() as session:
        job = session.get(AnalysisJob, job_id)
        for key, value in fields.items():
            setattr(job, key, value)
        session.commit()


def _make_job(
    ticker: str,
    *,
    status: str,
    scan_type: str = "standard",
    created_delta: timedelta = timedelta(minutes=1),
    started_delta: timedelta | None = None,
    finished_delta: timedelta | None = None,
    heartbeat_delta: timedelta | None = None,
    stage: str = "market",
    progress_pct: int = 20,
    checkpoints: list[dict] | None = None,
    result: dict | None = None,
    error: str | None = None,
    now: datetime,
) -> dict:
    import database

    job = database.create_job(_uid(), ticker, "NSE", scan_type)
    created_at = (now - created_delta).replace(tzinfo=None)
    started_at = (now - started_delta).replace(tzinfo=None) if started_delta else None
    finished_at = (now - finished_delta).replace(tzinfo=None) if finished_delta else None
    heartbeat_at = (now - heartbeat_delta).replace(tzinfo=None) if heartbeat_delta else None
    _set_job_fields(
        job["job_id"],
        status=status,
        stage=stage,
        progress_pct=progress_pct,
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        heartbeat_at=heartbeat_at,
        checkpoints=json.dumps(checkpoints or []),
        result_json=json.dumps(result) if result else None,
        error=error,
        tokens_used=1234,
        pid=4242,
    )
    return database.get_job(job["job_id"])


def test_list_jobs_matches_check_stock_modes_and_labels():
    from services.ai_engine_monitor import build_ai_engine_monitor, list_ai_engine_jobs

    now = datetime(2026, 6, 16, 9, 30, tzinfo=timezone.utc)
    recent = _make_job(
        "RELIANCE",
        status="RUNNING",
        scan_type="deep",
        created_delta=timedelta(minutes=2, seconds=5),
        started_delta=timedelta(minutes=2),
        heartbeat_delta=timedelta(seconds=20),
        stage="research",
        progress_pct=45,
        now=now,
    )
    stuck = _make_job(
        "TCS",
        status="RUNNING",
        created_delta=timedelta(minutes=16),
        started_delta=timedelta(minutes=15, seconds=30),
        heartbeat_delta=timedelta(minutes=14),
        stage="risk",
        progress_pct=70,
        now=now,
    )
    done = _make_job(
        "INFY",
        status="SUCCEEDED",
        created_delta=timedelta(minutes=30),
        started_delta=timedelta(minutes=29),
        finished_delta=timedelta(minutes=27, seconds=15),
        now=now,
    )

    running = list_ai_engine_jobs(mode="running", now=now)
    assert [job["job_id"] for job in running[:2]] == [recent["job_id"], stuck["job_id"]]
    assert all(job["status"] == "RUNNING" for job in running)
    assert running[0]["age_label"] == "2m5s"
    assert running[0]["elapsed_label"] == "2m0s"
    assert running[0]["took_label"] == "running"
    assert running[0]["last_heartbeat_label"] == "20s ago"
    assert running[0]["is_stuck"] is False

    stuck_jobs = list_ai_engine_jobs(mode="--stuck", now=now)
    assert [job["job_id"] for job in stuck_jobs] == [stuck["job_id"]]
    assert stuck_jobs[0]["is_stuck"] is True

    all_jobs = list_ai_engine_jobs(mode="--all", now=now, limit=3)
    assert [job["job_id"] for job in all_jobs] == [recent["job_id"], stuck["job_id"], done["job_id"]]
    assert all_jobs[-1]["took_label"] == "1m45s"

    ticker_jobs = list_ai_engine_jobs(mode="infy", now=now)
    assert [job["job_id"] for job in ticker_jobs] == [done["job_id"]]

    monitor = build_ai_engine_monitor(mode="running", now=now)
    assert monitor["type"] == "ai_engine_monitor"
    assert monitor["mode"] == "running"
    assert monitor["generated_at"] == "2026-06-16T09:30:00+00:00"
    assert monitor["summary"]["running"] >= 2
    assert monitor["summary"]["stuck"] >= 1
    assert recent["job_id"] in {job["job_id"] for job in monitor["jobs"]}


def test_detail_payload_includes_phase_timeline_last_message_and_latest_success_summary():
    from services.ai_engine_monitor import get_ai_engine_job_detail

    now = datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc)
    checkpoints = [
        {
            "ts": (now - timedelta(minutes=5)).isoformat(),
            "stage": "market",
            "agent": "Market Analyst",
            "message": "Reading price and volume",
            "state": "running",
        },
        {
            "ts": (now - timedelta(minutes=3, seconds=30)).isoformat(),
            "stage": "news",
            "agent": "News Analyst",
            "message": "Checking current catalysts",
            "state": "running",
        },
    ]
    running = _make_job(
        "RELIANCE",
        status="RUNNING",
        scan_type="extreme",
        created_delta=timedelta(minutes=6),
        started_delta=timedelta(minutes=5, seconds=30),
        heartbeat_delta=timedelta(seconds=45),
        stage="news",
        progress_pct=52,
        checkpoints=checkpoints,
        now=now,
    )
    latest = _make_job(
        "RELIANCE",
        status="SUCCEEDED",
        scan_type="deep",
        created_delta=timedelta(hours=1),
        started_delta=timedelta(minutes=59),
        finished_delta=timedelta(minutes=56),
        result={
            "analysis_date": "2026-06-16",
            "signal": "BUY",
            "confidence_pct": 82,
            "analysis_tier": "institutional",
            "current_price_inr": 2840.5,
            "target_prices": {"medium_term_12m": 3250},
            "upside_downside_pct": {"medium_term": 14.4},
            "key_risks": ["Execution risk"],
        },
        now=now,
    )

    detail = get_ai_engine_job_detail(running["job_id"], now=now)

    assert detail["job"]["job_id"] == running["job_id"]
    assert detail["job"]["current_phase"] == "news"
    assert detail["job"]["last_message"] == "Checking current catalysts"
    assert detail["phase_timeline"] == [
        {
            "stage": "market",
            "agent": "Market Analyst",
            "message": "Reading price and volume",
            "state": "running",
            "age_label": "5m0s",
        },
        {
            "stage": "news",
            "agent": "News Analyst",
            "message": "Checking current catalysts",
            "state": "running",
            "age_label": "3m30s",
        },
    ]
    assert detail["latest_success_summary"] == {
        "job_id": latest["job_id"],
        "ticker": "RELIANCE",
        "signal": "BUY",
        "confidence_pct": 82,
        "scan_type": "deep",
        "analysis_tier": "institutional",
        "analysis_date": "2026-06-16",
        "current_price_inr": 2840.5,
        "target_12m": 3250,
        "upside_12m_pct": 14.4,
        "tokens_used": 1234,
    }


def test_malformed_checkpoint_json_does_not_break_monitor():
    from services.ai_engine_monitor import list_ai_engine_jobs

    now = datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc)
    job = _make_job("BADCHK", status="RUNNING", now=now)
    _set_job_fields(job["job_id"], checkpoints="not-json")

    jobs = list_ai_engine_jobs(mode="BADCHK", now=now)

    assert jobs[0]["job_id"] == job["job_id"]
    assert jobs[0]["phase_timeline"] == []
    assert jobs[0]["last_message"] == ""
