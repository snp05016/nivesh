"""AI engine monitor formatting shared by dashboard APIs and CLI scripts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from repositories import job_repo


_RUNNING_LABEL = "running"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT"}


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _seconds_between(now: datetime, start: datetime | None) -> int | None:
    if start is None:
        return None
    return max(0, int((now - start).total_seconds()))


def _duration_label(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m{remainder}s"
    return f"{remainder}s"


def _ago_label(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    return f"{_duration_label(seconds)} ago"


def _result_dict(job: dict) -> dict:
    raw = job.get("result_json") or job.get("result")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _phase_timeline(checkpoints: list[dict], *, now: datetime) -> list[dict]:
    timeline: list[dict] = []
    for checkpoint in checkpoints:
        ts = _as_utc(checkpoint.get("ts"))
        timeline.append({
            "stage": checkpoint.get("stage") or "-",
            "agent": checkpoint.get("agent") or "-",
            "message": checkpoint.get("message") or "",
            "state": checkpoint.get("state") or "-",
            "age_label": _duration_label(_seconds_between(now, ts)),
        })
    return timeline


def _last_message(checkpoints: list[dict], fallback: str | None = None) -> str:
    for checkpoint in reversed(checkpoints):
        message = checkpoint.get("message")
        if message:
            return str(message)
    return fallback or ""


def _format_job(job: dict, *, now: datetime, stuck_minutes: int) -> dict:
    created_at = _as_utc(job.get("created_at"))
    started_at = _as_utc(job.get("started_at"))
    finished_at = _as_utc(job.get("finished_at"))
    heartbeat_at = _as_utc(job.get("heartbeat_at"))
    status = str(job.get("status") or "")
    checkpoints = job.get("checkpoints") if isinstance(job.get("checkpoints"), list) else []
    age_seconds = _seconds_between(now, created_at)
    elapsed_seconds = _seconds_between(now, started_at or created_at)
    took_seconds = None
    if finished_at is not None:
        took_seconds = _seconds_between(finished_at, started_at or created_at)
    heartbeat_seconds = _seconds_between(now, heartbeat_at)
    is_stuck = status == "RUNNING" and (age_seconds or 0) > stuck_minutes * 60

    formatted = dict(job)
    formatted.pop("result_json", None)
    formatted.update({
        "current_phase": job.get("stage") or "-",
        "progress_pct": int(job.get("progress_pct") or 0),
        "age_seconds": age_seconds,
        "age_label": _duration_label(age_seconds),
        "elapsed_seconds": elapsed_seconds,
        "elapsed_label": _duration_label(elapsed_seconds),
        "took_seconds": took_seconds,
        "took_label": _duration_label(took_seconds) if finished_at else _RUNNING_LABEL,
        "last_heartbeat_seconds": heartbeat_seconds,
        "last_heartbeat_label": _ago_label(heartbeat_seconds),
        "is_stuck": is_stuck,
        "last_message": _last_message(checkpoints, job.get("error")),
        "phase_timeline": _phase_timeline(checkpoints, now=now),
    })
    return formatted


def _latest_success_summary(job: dict | None) -> dict | None:
    if not job:
        return None
    result = _result_dict(job)
    targets = result.get("target_prices") if isinstance(result.get("target_prices"), dict) else {}
    upside = result.get("upside_downside_pct") if isinstance(result.get("upside_downside_pct"), dict) else {}
    return {
        "job_id": job.get("job_id"),
        "ticker": job.get("ticker"),
        "signal": result.get("signal"),
        "confidence_pct": result.get("confidence_pct"),
        "scan_type": job.get("scan_type") or "standard",
        "analysis_tier": result.get("analysis_tier"),
        "analysis_date": result.get("analysis_date"),
        "current_price_inr": result.get("current_price_inr"),
        "target_12m": targets.get("medium_term_12m"),
        "upside_12m_pct": upside.get("medium_term"),
        "tokens_used": job.get("tokens_used"),
    }


def list_ai_engine_jobs(
    *,
    mode: str = "running",
    ticker: str | None = None,
    limit: int = 20,
    stuck_minutes: int = 15,
    now: datetime | None = None,
) -> list[dict]:
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    jobs = job_repo.list_monitor_jobs(
        mode=mode,
        ticker=ticker,
        limit=limit,
        stuck_minutes=stuck_minutes,
        now=now_utc,
    )
    return [_format_job(job, now=now_utc, stuck_minutes=stuck_minutes) for job in jobs]


def _summary_from_jobs(jobs: list[dict]) -> dict:
    running = sum(1 for job in jobs if job.get("status") == "RUNNING")
    queued = sum(1 for job in jobs if job.get("status") == "QUEUED")
    stuck = sum(1 for job in jobs if job.get("is_stuck") is True)
    terminal_recent = sum(1 for job in jobs if job.get("status") in _TERMINAL_STATUSES)
    return {
        "running": running,
        "queued": queued,
        "stuck": stuck,
        "terminal_recent": terminal_recent,
    }


def build_ai_engine_monitor(
    *,
    mode: str = "running",
    ticker: str | None = None,
    limit: int = 20,
    stuck_minutes: int = 15,
    now: datetime | None = None,
) -> dict:
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    jobs = list_ai_engine_jobs(
        mode=mode,
        ticker=ticker,
        limit=limit,
        stuck_minutes=stuck_minutes,
        now=now_utc,
    )
    return {
        "type": "ai_engine_monitor",
        "mode": (mode or "running").strip() or "running",
        "ticker": ticker.upper() if ticker else None,
        "generated_at": now_utc.isoformat(),
        "summary": _summary_from_jobs(jobs),
        "jobs": jobs,
    }


def get_ai_engine_job_detail(
    job_id: str,
    *,
    now: datetime | None = None,
    stuck_minutes: int = 15,
) -> dict | None:
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    job = job_repo.get_monitor_job(job_id)
    if not job:
        return None
    formatted = _format_job(job, now=now_utc, stuck_minutes=stuck_minutes)
    latest = job_repo.get_latest_successful_monitor_job(str(job.get("ticker") or ""))
    return {
        "job": formatted,
        "phase_timeline": formatted["phase_timeline"],
        "latest_success_summary": _latest_success_summary(latest),
    }
