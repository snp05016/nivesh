"""Durable orchestration for portfolio stress-test subprocesses."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from types import SimpleNamespace

from repositories import job_repo, stress_test_repo


STRESS_TEST_SCAN_TYPE = "stress_test"
_STRESS_TEST_TICKER = "PORTFOLIO"
_STRESS_TEST_EXCHANGE = "NSE"
_ACTIVE_STATUSES = {"QUEUED", "RUNNING"}
# Hard wall-clock budget for one stress-test worker; matches the 300 s window in which
# job_repo.get_active_job_for_user_and_type treats a stress job as still active.
STRESS_TEST_WALLCLOCK_SEC = 300


@dataclass(frozen=True)
class StressTestLaunch:
    """
    Data payload representing a newly launched stress test job.

    Attributes:
        job_id (str): The unique identifier for the stress test job.
        holdings (list[dict]): A list of portfolio holding dictionaries.
        scenarios (list[str]): A list of scenario keys to run.
        completed_response (dict | None): Optional pre-computed response if immediately finished.
    """
    job_id: str
    holdings: list[dict]
    scenarios: list[str]
    completed_response: dict | None = None


def _latest_message(job: dict) -> str:
    """
    Extract the latest checkpoint message from a job dictionary.

    Args:
        job (dict): The job data dictionary.

    Returns:
        str: The latest message, or a default initialization message.
    """
    for checkpoint in reversed(job.get("checkpoints") or []):
        message = checkpoint.get("message")
        if message:
            return str(message)
    return str(job.get("stage") or "Initializing stress test")


def _api_job(job: dict) -> dict:
    """
    Transform a database job record into an API-friendly response dictionary.

    Args:
        job (dict): The job data dictionary.

    Returns:
        dict: An API-formatted job summary with status, progress, and stage details.
    """
    status = str(job.get("status") or "FAILED").upper()
    if status in _ACTIVE_STATUSES:
        return {
            "status": "running",
            "progress_pct": int(job.get("progress_pct") or 0),
            "stage": _latest_message(job),
            "checkpoint": str(job.get("stage") or "init"),
        }
    if status == "SUCCEEDED":
        return {
            "status": "completed",
            "progress_pct": 100,
            "stage": "Stress test complete",
            "checkpoint": "done",
            "results": job.get("result") or [],
        }
    return {
        "status": "failed",
        "error": str(job.get("error") or "Stress test failed"),
    }


def get_owned_stress_test_job(job_id: str, user_id: int) -> dict | None:
    """
    Retrieve a stress test job if it is owned by the specified user.

    Args:
        job_id (str): The unique job identifier.
        user_id (int): The ID of the requesting user.

    Returns:
        dict | None: The API-formatted job dictionary if found and authorized, otherwise None.
    """
    job = job_repo.get_job(job_id)
    if not job or job.get("user_id") != user_id:
        return None
    if job.get("scan_type") != STRESS_TEST_SCAN_TYPE:
        return None
    return _api_job(job)


def list_owned_stress_test_jobs(user_id: int) -> dict:
    """
    List all stress test jobs owned by the specified user.

    Args:
        user_id (int): The ID of the requesting user.

    Returns:
        dict: A dictionary containing active counts, total counts, and the list of jobs.
    """
    jobs = job_repo.list_jobs_for_user_and_type(
        user_id,
        STRESS_TEST_SCAN_TYPE,
    )
    rows = []
    for job in jobs:
        status = str(job.get("status") or "FAILED").upper()
        rows.append({
            "job_id": job["job_id"],
            "status": "running" if status in _ACTIVE_STATUSES else status.lower(),
            "progress_pct": int(job.get("progress_pct") or 0),
            "stage": _latest_message(job),
            "checkpoint": str(job.get("stage") or "init"),
            "ticker_count": _ticker_count(job),
            "started_at": job.get("started_at") or job.get("created_at"),
            "has_error": bool(job.get("error")),
        })
    return {
        "active_count": sum(1 for row in rows if row["status"] == "running"),
        "total_count": len(rows),
        "jobs": rows,
    }


def _ticker_count(job: dict) -> int:
    """
    Extract the number of tickers (holdings) queued in the job based on the init message.

    Args:
        job (dict): The job data dictionary.

    Returns:
        int: The number of tickers if successfully parsed, otherwise 0.
    """
    for checkpoint in job.get("checkpoints") or []:
        if checkpoint.get("stage") == "init":
            message = str(checkpoint.get("message") or "")
            prefix = message.split(" holding", maxsplit=1)[0]
            if prefix.isdigit():
                return int(prefix)
    return 0


def _existing_job_launch(job_id: str, scenarios: list[str]) -> StressTestLaunch:
    """Launch result pointing at an already-active stress test job."""
    return StressTestLaunch(
        job_id=job_id,
        holdings=[],
        scenarios=list(scenarios),
        completed_response={"job_id": job_id, "status": "running"},
    )


def prepare_stress_test_job(
    user_id: int,
    portfolio_id: str,
    scenarios: list[str],
) -> StressTestLaunch:
    """
    Create and queue a new stress test job for a given portfolio.

    Args:
        user_id (int): The ID of the user requesting the stress test.
        portfolio_id (str): The ID of the portfolio to test.
        scenarios (list[str]): A list of stress test scenario identifiers.

    Returns:
        StressTestLaunch: An object containing the created job_id and payload.
        If the user already has an active stress test, its job_id is returned
        instead of starting a second worker.
        The active-job check is backed by a unique index, so a concurrent
        request that loses the race also gets the existing job_id.
    """
    existing = job_repo.get_active_job_for_user_and_type(user_id, STRESS_TEST_SCAN_TYPE)
    if existing:
        return _existing_job_launch(existing["job_id"], scenarios)

    holdings = stress_test_repo.list_portfolio_holdings(user_id, portfolio_id)
    try:
        job = job_repo.create_job(
            user_id,
            _STRESS_TEST_TICKER,
            _STRESS_TEST_EXCHANGE,
            STRESS_TEST_SCAN_TYPE,
        )
    except job_repo.JobAlreadyActive as e:
        return _existing_job_launch(e.job["job_id"], scenarios)
    job_id = job["job_id"]
    job_repo.append_checkpoint(
        job_id,
        stage="init",
        agent="Stress Test Engine",
        message=f"{len(holdings)} holdings queued for stress testing",
        state="queued",
        pct=0,
    )

    if not holdings:
        job_repo.append_checkpoint(
            job_id,
            stage="done",
            agent="Stress Test Engine",
            message="No portfolio holdings to stress test",
            state="ok",
            pct=100,
        )
        job_repo.update_job(
            job_id,
            status="SUCCEEDED",
            progress_pct=100,
            stage="done",
            result_json="[]",
        )
        return StressTestLaunch(
            job_id=job_id,
            holdings=[],
            scenarios=list(scenarios),
            completed_response={
                "job_id": job_id,
                "status": "completed",
                "results": [],
            },
        )

    return StressTestLaunch(
        job_id=job_id,
        holdings=holdings,
        scenarios=list(scenarios),
    )


def record_stress_test_process(job_id: str, pid: int | None) -> None:
    """
    Update the job record with the process ID running the stress test.

    Args:
        job_id (str): The unique job identifier.
        pid (int | None): The process ID handling the job, or None.
    """
    job_repo.update_job(job_id, pid=pid)


def mark_stress_test_start_failed(job_id: str, error: Exception) -> None:
    """
    Mark a stress test job as failed during the initial startup process.

    Args:
        job_id (str): The unique job identifier.
        error (Exception): The exception that caused the startup failure.
    """
    message = f"Failed to start stress-test worker: {error}"
    job_repo.append_checkpoint(
        job_id,
        stage="failed",
        agent="Stress Test Engine",
        message=message,
        state="error",
        pct=0,
    )
    job_repo.update_job(job_id, status="FAILED", stage="failed", error=message)


def run_stress_test_job(
    job_id: str,
    holdings_payload: list[dict],
    scenarios: list[str],
) -> None:
    """
    Execute a stress test job and update checkpoints with progress.

    Args:
        job_id (str): The unique job identifier.
        holdings_payload (list[dict]): A list of holding dictionaries to test.
        scenarios (list[str]): A list of stress test scenario keys.
    """
    try:
        from core.env import load_backend_env
        load_backend_env()
    except Exception as _e:
        pass

    # The parent's pool is dropped by database._reset_pool_after_fork (DB-02);
    # dispose() with close=True here would close the parent's shared sockets.

    from services.stress_test import run_stress_test

    holdings = [SimpleNamespace(**payload) for payload in holdings_payload]
    emit_lock = threading.Lock()

    def emit(checkpoint: str, pct: int, message: str) -> None:
        with emit_lock:
            job_repo.append_checkpoint(
                job_id,
                stage=checkpoint,
                agent="Stress Test Engine",
                message=message,
                state="running",
                pct=pct,
            )

    try:
        job_repo.update_job(
            job_id,
            status="RUNNING",
            pid=os.getpid(),
            stage="init",
            progress_pct=2,
        )
        from services.job_worker import _start_wallclock_watchdog
        _start_wallclock_watchdog(job_id, STRESS_TEST_WALLCLOCK_SEC)
        emit("init", 2, "Initializing stress-test engine")

        def on_holding_progress(done: int, total: int, ticker: str) -> None:
            pct = 5 + int((done / max(total, 1)) * 45)
            emit("enrich", pct, f"Loaded {ticker} ({done}/{total})")

        results = run_stress_test(
            holdings,
            scenarios,
            progress_callback=on_holding_progress,
            phase_callback=emit,
        )
        job_repo.append_checkpoint(
            job_id,
            stage="done",
            agent="Stress Test Engine",
            message="Stress test complete",
            state="ok",
            pct=100,
        )
        job_repo.update_job(
            job_id,
            status="SUCCEEDED",
            progress_pct=100,
            stage="done",
            result_json=json.dumps(results, default=str),
        )
    except Exception as exc:
        job_repo.append_checkpoint(
            job_id,
            stage="failed",
            agent="Stress Test Engine",
            message=f"Stress test failed: {exc}",
            state="error",
            pct=0,
        )
        job_repo.update_job(
            job_id,
            status="FAILED",
            stage="failed",
            error=str(exc),
        )
