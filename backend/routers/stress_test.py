import threading
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timezone

from helpers import get_session, require_auth
from database import Portfolio
from services.stress_test import run_stress_test

router = APIRouter()

_lock = threading.Lock()
_jobs: Dict[str, dict] = {}

class StressTestRequest(BaseModel):
    portfolio_id: str
    scenarios: List[str] = []
    custom_shocks: Optional[dict[str, float]] = None

class StressTestHolding(BaseModel):
    ticker: str
    company_name: str
    sector: str
    value: float
    weight_pct: float
    impact_pct: float
    impact_inr: float
    liquidity_penalty_pct: float
    liquidity_penalty_inr: float

class StressTestScores(BaseModel):
    risk_score: float
    stress_score: float
    macro_fragility: float
    liquidity_score: float
    concentration_score: float
    tail_risk_score: float

@router.post("/api/v1/portfolio/stress-test")
def start_stress_test(req: StressTestRequest, user_id: int = Depends(require_auth)):
    with get_session() as db:
        holdings = db.query(Portfolio).filter(
            Portfolio.user_id == user_id, Portfolio.group_name == req.portfolio_id
        ).all()

    if not holdings:
        return {"results": [], "status": "completed"}

    job_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    with _lock:
        _jobs[job_id] = {
            "job_id": job_id, "owner_user_id": user_id, "status": "running",
            "started_at": now, "stage": "Initializing…", "progress_pct": 0,
            "checkpoint": "init", "ticker_count": len(holdings),
            "result": None, "error": None,
        }

    def _set(stage: str, pct: int, checkpoint: str):
        with _lock:
            if job_id in _jobs:
                _jobs[job_id]["stage"] = stage
                _jobs[job_id]["progress_pct"] = pct
                _jobs[job_id]["checkpoint"] = checkpoint

    def _run():
        try:
            _set("Initializing simulation…", 2, "init")

            def _on_progress(done, total, current_ticker):
                pct = 5 + int((done / total) * 70)
                _set(f"Loading {current_ticker} ({done}/{total})", pct, "enrich")

            _set("Fetching market data for holdings…", 5, "enrich")
            results = run_stress_test(holdings, req.scenarios, progress_callback=_on_progress)

            _set(f"Running {len(req.scenarios)} scenario(s)…", 80, "scenarios")
            _set("Computing concentration & tail-risk scores…", 92, "scoring")

            with _lock:
                if job_id in _jobs:
                    _jobs[job_id]["status"] = "completed"
                    _jobs[job_id]["progress_pct"] = 100
                    _jobs[job_id]["stage"] = "Complete"
                    _jobs[job_id]["checkpoint"] = "done"
                    _jobs[job_id]["result"] = results
                    _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id]["status"] = "failed"
                    _jobs[job_id]["error"] = str(e)
                    _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id, "status": "running"}


def _cleanup_old_jobs():
    """Remove completed/failed jobs older than 5 minutes."""
    with _lock:
        now = datetime.now(timezone.utc)
        stale = [
            jid for jid, job in _jobs.items()
            if job["status"] in ("completed", "failed")
            and job.get("finished_at")
            and (now - datetime.fromisoformat(job["finished_at"])).total_seconds() > 300
        ]
        for jid in stale:
            del _jobs[jid]


def _get_owned_job(job_id: str, user_id: int) -> dict:
    """Return the job dict if it belongs to user_id, else raise 404."""
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["owner_user_id"] != user_id:
        # Return 404 (not 403) to avoid leaking job existence to other users
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/v1/portfolio/stress-test/{job_id}")
def get_stress_test_result(job_id: str, user_id: int = Depends(require_auth)):
    _cleanup_old_jobs()
    job = _get_owned_job(job_id, user_id)

    if job["status"] == "running":
        return {
            "status": "running",
            "progress_pct": job["progress_pct"],
            "stage": job["stage"],
            "checkpoint": job.get("checkpoint", "init"),
        }

    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Stress test failed: {job.get('error')}")

    return {"status": "completed", "results": job.get("result", [])}


@router.get("/api/v1/portfolio/stress-test/{job_id}/progress")
def get_stress_test_progress(job_id: str, user_id: int = Depends(require_auth)):
    job = _get_owned_job(job_id, user_id)
    return {
        "job_id": job_id, "status": job["status"],
        "progress_pct": job["progress_pct"], "stage": job["stage"],
        "ticker_count": job.get("ticker_count", 0),
        "started_at": job.get("started_at"),
    }


@router.get("/api/v1/dashboard/stress-test-jobs")
def list_stress_test_jobs(user_id: int = Depends(require_auth)):
    """List stress test jobs belonging to the authenticated user."""
    with _lock:
        user_jobs = [j for j in _jobs.values() if j["owner_user_id"] == user_id]
    return {
        "active_count": sum(1 for j in user_jobs if j["status"] == "running"),
        "total_count": len(user_jobs),
        "jobs": [
            {
                "job_id": j["job_id"], "status": j["status"],
                "progress_pct": j["progress_pct"], "stage": j["stage"],
                "ticker_count": j.get("ticker_count", 0),
                "started_at": j.get("started_at"),
                "has_error": bool(j.get("error")),
            }
            for j in user_jobs
        ]
    }
