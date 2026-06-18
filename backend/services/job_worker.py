"""Subprocess entry point for a single analysis job.

Runs fully decoupled from any HTTP connection. Writes all state (status, progress,
checkpoints, result) straight to the AnalysisJob row via the DB DAO, so the app can
poll it, navigate away, background, or close — the run survives.

Kill-switch: a daemon wall-clock watchdog hard-stops the subprocess at ``limit_sec``
so an extreme run can never exceed its budget.
"""
from __future__ import annotations

import json
import os
import threading
import time

# Wall-clock budgets per scan type (seconds). Extreme is depth-first ≤10 min.
_WALLCLOCK_LIMITS = {"extreme": 600, "deep": 420, "standard": 420}


def _start_wallclock_watchdog(job_id: str, limit_sec: int) -> None:
    def _kill():
        time.sleep(limit_sec)
        try:
            import database
            j = database.get_job(job_id)
            if j and j["status"] == "RUNNING":
                database.update_job(
                    job_id, status="TIMEOUT",
                    error=f"Exceeded {limit_sec}s wall-clock budget",
                )
        finally:
            os._exit(1)  # hard-stop the subprocess (and any in-flight LLM call)

    threading.Thread(target=_kill, daemon=True).start()


def run_job(job_id: str, ticker: str, exchange: str,
            user_id, deep_scan: bool, scan_type: str,
            language=None, debate_rounds=None, risk_tolerance=None) -> None:
    # Re-import deps + reload env inside the subprocess (AGENTS.md §3.3).
    # v2 fix: tradingagents-core must be on sys.path before services.orchestrator
    # resolves its tradingagents.default_config import.
    import sys as _sys
    from pathlib import Path as _Path
    _tg_path = _Path(__file__).parent.parent / "tradingagents-core"
    if _tg_path.exists() and str(_tg_path) not in _sys.path:
        _sys.path.insert(0, str(_tg_path))

    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

    import database
    database.update_job(job_id, status="RUNNING", pid=os.getpid(),
                        stage="starting", progress_pct=1)
    database.append_checkpoint(job_id, stage="starting", agent="Engine",
                               message=f"Analysis started for {ticker}",
                               state="running", pct=1)

    _start_wallclock_watchdog(job_id, _WALLCLOCK_LIMITS.get(scan_type, 300))

    try:
        from services.orchestrator import analyze
        result = analyze(ticker, exchange, user_id,
                         deep_scan=deep_scan, scan_type=scan_type, job_id=job_id,
                         language=language, debate_rounds=debate_rounds,
                         risk_tolerance=risk_tolerance)
        database.update_job(
            job_id, status="SUCCEEDED", progress_pct=100, stage="done",
            result_json=json.dumps(result, default=str),
        )
        database.append_checkpoint(job_id, stage="done", agent="Engine",
                                   message="Analysis complete", state="ok", pct=100)
    except Exception as e:
        database.update_job(job_id, status="FAILED", error=str(e))
        database.append_checkpoint(job_id, stage="failed", agent="Engine",
                                   message=f"Analysis failed: {e}", state="error", pct=0)
        raise
