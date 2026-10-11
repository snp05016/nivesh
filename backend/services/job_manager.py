"""Owns running analysis subprocesses: spawn, registry, cancel.

Module-level mutable state (`_job_registry`) is guarded by a dedicated lock per
AGENTS.md §3.4. The registry enables immediate cancellation (terminate the process
to stop burning credits); the worker itself self-enforces the wall-clock budget, so
correctness does not depend on this parent process staying alive.
"""
from __future__ import annotations

import multiprocessing
import os
import threading
from datetime import datetime, timedelta, timezone
from multiprocessing.process import BaseProcess

from repositories import job_repo

# REL-06: never fork the threaded API process. A forked child would share the
# parent's pooled DB/pgvector sockets and could inherit a lock held by another
# thread; a spawned child starts clean and re-imports what it needs.
MP_CTX = multiprocessing.get_context("spawn")

_job_registry: dict[str, BaseProcess] = {}
_registry_lock = threading.Lock()

# Platform-wide cap on QUEUED/RUNNING worker jobs, counted from the DB so it holds
# across uvicorn workers.
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "6"))
# Per-owner cap across every scan type and stress tests, so varying scan_type or
# opening more screens cannot multiply one account's workers. Anonymous jobs
# (user_id None) all share one owner bucket (AUTH-17).
MAX_JOBS_PER_USER = int(os.getenv("MAX_JOBS_PER_USER", "2"))
# Longer than any worker's wall-clock budget (extreme = 600 s): an active row older
# than this belongs to a worker that died without updating it, so it holds no slot.
_STALE_ACTIVE_SEC = 900


class JobCapacityError(RuntimeError):
    """Raised when MAX_CONCURRENT_JOBS worker jobs are already active."""


class JobUserLimitError(JobCapacityError):
    """Raised when the job's owner already has MAX_JOBS_PER_USER active jobs."""


def _active_jobs(exclude_job_id: str) -> list[dict]:
    """Active rows that still hold a worker slot, minus the job being started."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_STALE_ACTIVE_SEC)
    active = []
    for job in job_repo.list_active_jobs():
        if job.get("job_id") == exclude_job_id:
            continue
        created = job.get("created_at")
        if created:
            ts = datetime.fromisoformat(created)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
        active.append(job)
    return active


def spawn_process(job_id: str, target, args: tuple, user_id: int | None = None) -> int | None:
    """Start a daemon worker for an already-created job row and register it.

    Every subprocess job goes through here so shutdown_all/cancel_job and the
    admission caps cover it. The row exists before this check, so two concurrent
    starts can only both be refused, never both admitted past a cap. Raises
    JobCapacityError at the platform-wide cap and JobUserLimitError when the owner
    (user_id) is at its own cap.
    """
    active = _active_jobs(job_id)
    if len(active) >= MAX_CONCURRENT_JOBS:
        raise JobCapacityError("Server busy, please retry shortly")
    if sum(1 for job in active if job.get("user_id") == user_id) >= MAX_JOBS_PER_USER:
        raise JobUserLimitError("Too many analyses running for this account. "
                                "Wait for one to finish, then try again.")
    p = MP_CTX.Process(target=target, args=args, daemon=True)
    p.start()
    with _registry_lock:
        _job_registry[job_id] = p
    return p.pid


def spawn_job(job_id: str, ticker: str, exchange: str,
              user_id, deep_scan: bool, scan_type: str,
              language=None, debate_rounds=None, risk_tolerance=None) -> None:
    from services.job_worker import run_job
    spawn_process(
        job_id,
        run_job,
        (job_id, ticker, exchange, user_id, deep_scan, scan_type,
         language, debate_rounds, risk_tolerance),
        user_id=user_id,
    )


def cancel_job(job_id: str) -> bool:
    """Mark the job CANCELLED and terminate its subprocess if we own it locally.

    A worker owned by another uvicorn process sees the terminal status on its
    next heartbeat and exits itself (services.job_worker).
    """
    import database
    try:  # before the status: append_checkpoint ignores terminal jobs
        database.append_checkpoint(job_id, stage="cancelled", agent="Engine",
                                   message="Cancelled by user", state="error", pct=0)
    except Exception as _e:
        pass
    database.update_job(job_id, status="CANCELLED", error="Cancelled by user")
    with _registry_lock:
        p = _job_registry.pop(job_id, None)
    if p is not None and p.is_alive():
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
            p.join(timeout=2)
    return True


def reap_finished() -> None:
    """Drop dead processes from the registry (called opportunistically)."""
    with _registry_lock:
        for jid in [j for j, p in _job_registry.items() if not p.is_alive()]:
            _job_registry.pop(jid, None)

def shutdown_all() -> None:
    """Terminate all running jobs during server shutdown to prevent semaphore leaks."""
    with _registry_lock:
        jobs = list(_job_registry.values())
        _job_registry.clear()
        
    for p in jobs:
        if p.is_alive():
            p.terminate()
            p.join(timeout=2)
            if p.is_alive():
                p.kill()
                p.join(timeout=1)
