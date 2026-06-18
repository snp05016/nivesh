"""Owns running analysis subprocesses: spawn, registry, cancel.

Module-level mutable state (`_job_registry`) is guarded by a dedicated lock per
AGENTS.md §3.4. The registry enables immediate cancellation (terminate the process
to stop burning credits); the worker itself self-enforces the wall-clock budget, so
correctness does not depend on this parent process staying alive.
"""
from __future__ import annotations

import multiprocessing
import threading

_job_registry: dict[str, "multiprocessing.Process"] = {}
_registry_lock = threading.Lock()


def spawn_job(job_id: str, ticker: str, exchange: str,
              user_id, deep_scan: bool, scan_type: str,
              language=None, debate_rounds=None, risk_tolerance=None) -> None:
    from services.job_worker import run_job
    p = multiprocessing.Process(
        target=run_job,
        args=(job_id, ticker, exchange, user_id, deep_scan, scan_type,
              language, debate_rounds, risk_tolerance),
        daemon=True,
    )
    p.start()
    with _registry_lock:
        _job_registry[job_id] = p


def cancel_job(job_id: str) -> bool:
    """Mark the job CANCELLED and terminate its subprocess if we own it locally."""
    import database
    database.update_job(job_id, status="CANCELLED", error="Cancelled by user")
    try:
        database.append_checkpoint(job_id, stage="cancelled", agent="Engine",
                                   message="Cancelled by user", state="error", pct=0)
    except Exception:
        pass
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
