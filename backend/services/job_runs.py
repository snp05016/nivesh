"""Per-run history of scheduled jobs, with failure and recovery alerts.

tracked(name, fn) wraps a job so every run writes a job_runs row. A coroutine
function gets an async wrapper (the job stays on the scheduler's event loop and
its bookkeeping, including the alert POST, runs in a worker thread); any other
callable gets a sync wrapper. Bookkeeping never raises into the job.

Datetimes are stored as naive UTC and serialised with a trailing Z.
"""
import asyncio
import functools
import inspect
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx
from sqlalchemy import func

from database import get_session
from models.db_models import JobRun

logger = logging.getLogger(__name__)

ERROR_MAX = 2000
ALERT_BODY_MAX = 300
META_MAX = 4000
_ROWS_KEYS = ("rows_written", "rows", "added", "count", "generated", "chunks")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_BEARER = re.compile(r"Bearer\s+[\w.~+/=-]+", re.IGNORECASE)
_URL_CREDS = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
_LONG_DIGITS = re.compile(r"\d{10,}")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


def scrub(text: Optional[str]) -> Optional[str]:
    """Mask emails, PAN, bearer tokens, URL credentials and 10+ digit runs; cap at 2000 chars."""
    if text is None:
        return None
    out = _URL_CREDS.sub("://<redacted>@", str(text))
    out = _BEARER.sub("Bearer <redacted>", out)
    out = _EMAIL.sub("<email>", out)
    out = _PAN.sub("<pan>", out)
    out = _LONG_DIGITS.sub("<number>", out)
    return out[:ERROR_MAX]


def notify_ops(title: str, body: str) -> bool:
    """Plain-text POST to OPS_ALERT_WEBHOOK_URL (ntfy-compatible). False when unset or failing."""
    url = os.getenv("OPS_ALERT_WEBHOOK_URL", "").strip()
    if not url:
        logger.warning("OPS_ALERT_WEBHOOK_URL is unset; alert not sent: %s", title)
        return False
    try:
        httpx.post(url, content=body.encode("utf-8"), headers={"Title": title}, timeout=5).raise_for_status()
        return True
    except Exception as exc:
        logger.warning("job alert delivery failed: %s", type(exc).__name__)
        return False


def _row_dict(r: JobRun) -> dict:
    return {
        "id": r.id,
        "job_name": r.job_name,
        "status": r.status,
        "started_at": _iso(r.started_at),
        "finished_at": _iso(r.finished_at),
        "duration_ms": r.duration_ms,
        "rows_written": r.rows_written,
        "error": r.error,
        "meta": r.meta,
    }


def start_run(job_name: str) -> Optional[int]:
    try:
        with get_session() as session:
            row = JobRun(job_name=job_name[:64], status="running", started_at=_now())
            session.add(row)
            session.commit()
            return row.id
    except Exception as exc:
        logger.warning("job_runs start failed for %s: %s", job_name, type(exc).__name__)
        return None


def _rows_from(result: Any) -> Optional[int]:
    if isinstance(result, int) and not isinstance(result, bool):
        return result
    if isinstance(result, dict):
        for key in _ROWS_KEYS:
            val = result.get(key)
            if isinstance(val, int) and not isinstance(val, bool):
                return val
    return None


def _meta_from(result: Any) -> Optional[dict]:
    if result is None:
        return None
    if isinstance(result, dict):
        try:
            text = json.dumps(result, default=str)
        except (TypeError, ValueError):
            return {"truncated": True}
        if len(text) > META_MAX:
            return {"truncated": True}
        return json.loads(text)
    if isinstance(result, (int, str)) and not isinstance(result, bool):
        return {"result": result if isinstance(result, int) else result[:200]}
    return None


def finish_run(run_id: Optional[int], status: str, *, error: Optional[str] = None,
               result: Any = None, duration_ms: Optional[int] = None) -> None:
    if run_id is None:
        return
    try:
        alert: Optional[tuple[str, str]] = None
        with get_session() as session:
            row = session.get(JobRun, run_id)
            if row is None:
                return
            row.status = status
            row.finished_at = _now()
            row.duration_ms = duration_ms
            row.rows_written = _rows_from(result)
            row.meta = _meta_from(result)
            row.error = scrub(error)
            prev = (
                session.query(JobRun.status)
                .filter(JobRun.job_name == row.job_name, JobRun.id < run_id, JobRun.status != "running")
                .order_by(JobRun.id.desc())
                .first()
            )
            prev_status = prev[0] if prev else None
            if status == "failed" and prev_status != "failed":
                alert = (f"Nivesh job failed: {row.job_name}", (row.error or "")[:ALERT_BODY_MAX])
            elif status == "ok" and prev_status == "failed":
                alert = (f"Nivesh job recovered: {row.job_name}", "")
            session.commit()
        if alert:
            notify_ops(*alert)
    except Exception as exc:
        logger.warning("job_runs finish failed for run %s: %s", run_id, type(exc).__name__)


def tracked(job_name: str, fn: Callable) -> Callable:
    """Wrap `fn` so each run is recorded; the exception, if any, is re-raised."""
    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            run_id = await asyncio.to_thread(start_run, job_name)
            t0 = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                await asyncio.to_thread(
                    finish_run, run_id, "failed", error=f"{type(exc).__name__}: {exc}",
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
                raise
            await asyncio.to_thread(
                finish_run, run_id, "ok", result=result, duration_ms=int((time.monotonic() - t0) * 1000),
            )
            return result

        async_wrapper._job_runs_name = job_name
        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args, **kwargs):
        run_id = start_run(job_name)
        t0 = time.monotonic()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            finish_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}",
                       duration_ms=int((time.monotonic() - t0) * 1000))
            raise
        finish_run(run_id, "ok", result=result, duration_ms=int((time.monotonic() - t0) * 1000))
        return result

    sync_wrapper._job_runs_name = job_name
    return sync_wrapper


def mark_abandoned() -> int:
    """Leftover 'running' rows from a restart become failed. No alert."""
    try:
        with get_session() as session:
            n = (
                session.query(JobRun)
                .filter(JobRun.status == "running")
                .update(
                    {"status": "failed", "error": "abandoned: scheduler restarted", "finished_at": _now()},
                    synchronize_session=False,
                )
            )
            session.commit()
            return n
    except Exception as exc:
        logger.warning("job_runs mark_abandoned failed: %s", type(exc).__name__)
        return 0


def latest_by_job() -> dict[str, dict]:
    """job_name -> its newest row. {} when the table cannot be read."""
    try:
        with get_session() as session:
            newest = session.query(func.max(JobRun.id)).group_by(JobRun.job_name).subquery()
            rows = session.query(JobRun).filter(JobRun.id.in_(session.query(newest.c[0]))).all()
            return {r.job_name: _row_dict(r) for r in rows}
    except Exception as exc:
        logger.warning("job_runs latest_by_job failed: %s", type(exc).__name__)
        return {}


def list_runs(job_name: Optional[str] = None, status: Optional[str] = None,
              limit: int = 50, before_id: Optional[int] = None) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with get_session() as session:
        q = session.query(JobRun)
        if job_name:
            q = q.filter(JobRun.job_name == job_name)
        if status:
            q = q.filter(JobRun.status == status)
        if before_id is not None:
            q = q.filter(JobRun.id < before_id)
        return [_row_dict(r) for r in q.order_by(JobRun.id.desc()).limit(limit).all()]


def summary(days: int = 7) -> dict:
    days = max(1, min(int(days), 90))
    since = _now() - timedelta(days=days)
    with get_session() as session:
        rows = (
            session.query(JobRun)
            .filter(JobRun.started_at >= since, JobRun.status != "running")
            .order_by(JobRun.id)
            .all()
        )
        # ponytail: python aggregation, move to SQL GROUP BY past ~100k rows
        jobs: dict[str, dict] = {}
        for r in rows:
            j = jobs.setdefault(r.job_name, {"job_name": r.job_name, "runs": 0, "failures": 0})
            j["runs"] += 1
            if r.status == "failed":
                j["failures"] += 1
            j["last_status"] = r.status
            j["last_started_at"] = _iso(r.started_at)
            j["last_error"] = r.error
        total = sum(j["runs"] for j in jobs.values())
        failed = sum(j["failures"] for j in jobs.values())
        for j in jobs.values():
            j["success_pct"] = round(100.0 * (j["runs"] - j["failures"]) / j["runs"], 1)
        return {
            "days": days,
            "overall_success_pct": round(100.0 * (total - failed) / total, 1) if total else None,
            "jobs": sorted(jobs.values(), key=lambda j: j["job_name"]),
        }


def purge_older_than(days: int = 90) -> int:
    cutoff = _now() - timedelta(days=days)
    with get_session() as session:
        n = session.query(JobRun).filter(JobRun.started_at < cutoff).delete(synchronize_session=False)
        session.commit()
        return n


_STATUS_MAP = {"running": "running", "ok": "idle", "failed": "error"}


def merge_harvest_status(in_memory: dict) -> dict:
    """Dashboard harvest_status: the in-memory entries plus job_runs entries for jobs
    the web process has not seen (the scheduler may run in another worker)."""
    merged = dict(in_memory)
    for name, run in latest_by_job().items():
        if name in merged:
            continue
        merged[name] = {
            "status": _STATUS_MAP.get(run["status"], "idle"),
            "last_run": run["started_at"],
            "last_result": {"error": run["error"]} if run["error"] else run["meta"],
        }
    return merged
