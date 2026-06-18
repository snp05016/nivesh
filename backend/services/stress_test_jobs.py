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


@dataclass(frozen=True)
class StressTestLaunch:
    job_id: str
    holdings: list[dict]
    scenarios: list[str]
    completed_response: dict | None = None


def _latest_message(job: dict) -> str:
    for checkpoint in reversed(job.get("checkpoints") or []):
        message = checkpoint.get("message")
        if message:
            return str(message)
    return str(job.get("stage") or "Initializing stress test")


def _api_job(job: dict) -> dict:
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
    job = job_repo.get_job(job_id)
    if not job or job.get("user_id") != user_id:
        return None
    if job.get("scan_type") != STRESS_TEST_SCAN_TYPE:
        return None
    return _api_job(job)


def list_owned_stress_test_jobs(user_id: int) -> dict:
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
    for checkpoint in job.get("checkpoints") or []:
        if checkpoint.get("stage") == "init":
            message = str(checkpoint.get("message") or "")
            prefix = message.split(" holding", maxsplit=1)[0]
            if prefix.isdigit():
                return int(prefix)
    return 0


def prepare_stress_test_job(
    user_id: int,
    portfolio_id: str,
    scenarios: list[str],
) -> StressTestLaunch:
    holdings = stress_test_repo.list_portfolio_holdings(user_id, portfolio_id)
    job = job_repo.create_job(
        user_id,
        _STRESS_TEST_TICKER,
        _STRESS_TEST_EXCHANGE,
        STRESS_TEST_SCAN_TYPE,
    )
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
        job_repo.update_job(
            job_id,
            status="SUCCEEDED",
            progress_pct=100,
            stage="done",
            result_json="[]",
        )
        job_repo.append_checkpoint(
            job_id,
            stage="done",
            agent="Stress Test Engine",
            message="No portfolio holdings to stress test",
            state="ok",
            pct=100,
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
    job_repo.update_job(job_id, pid=pid)


def mark_stress_test_start_failed(job_id: str, error: Exception) -> None:
    message = f"Failed to start stress-test worker: {error}"
    job_repo.update_job(job_id, status="FAILED", stage="failed", error=message)
    job_repo.append_checkpoint(
        job_id,
        stage="failed",
        agent="Stress Test Engine",
        message=message,
        state="error",
        pct=0,
    )


def run_stress_test_job(
    job_id: str,
    holdings_payload: list[dict],
    scenarios: list[str],
) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

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
        job_repo.update_job(
            job_id,
            status="SUCCEEDED",
            progress_pct=100,
            stage="done",
            result_json=json.dumps(results, default=str),
        )
        job_repo.append_checkpoint(
            job_id,
            stage="done",
            agent="Stress Test Engine",
            message="Stress test complete",
            state="ok",
            pct=100,
        )
    except Exception as exc:
        job_repo.update_job(
            job_id,
            status="FAILED",
            stage="failed",
            error=str(exc),
        )
        job_repo.append_checkpoint(
            job_id,
            stage="failed",
            agent="Stress Test Engine",
            message=f"Stress test failed: {exc}",
            state="error",
            pct=0,
        )
