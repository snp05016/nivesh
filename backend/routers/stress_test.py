import threading
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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
    
    progress = {"stage": "initializing", "pct": 0, "total": len(holdings), "completed": 0}
    
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id, "status": "running", "started_at": now,
            "stage": progress["stage"], "progress_pct": 0, "ticker_count": len(holdings),
            "result": None, "error": None, "progress": progress
        }
    
    def _run():
        try:
            def _on_progress(done, total, current_ticker):
                pct = int((done / total) * 80)
                with _lock:
                    if job_id in _jobs:
                        _jobs[job_id]["stage"] = f"Loading {current_ticker} ({done}/{total})"
                        _jobs[job_id]["progress_pct"] = pct
            
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id]["stage"] = "Fetching market data..."
                    _jobs[job_id]["progress_pct"] = 5
            
            results = run_stress_test(holdings, req.scenarios, progress_callback=_on_progress)
            
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id]["status"] = "completed"
                    _jobs[job_id]["progress_pct"] = 100
                    _jobs[job_id]["stage"] = "Complete"
                    _jobs[job_id]["result"] = results
        except Exception as e:
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id]["status"] = "failed"
                    _jobs[job_id]["error"] = str(e)
    
    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id, "status": "running"}

@router.get("/api/v1/portfolio/stress-test/{job_id}")
def get_stress_test_result(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] == "running":
        return {"status": "running", "progress_pct": job["progress_pct"], "stage": job["stage"]}
    
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Stress test failed: {job.get('error')}")
    
    return {"status": "completed", "results": job.get("result", [])}

@router.get("/api/v1/portfolio/stress-test/{job_id}/progress")
def get_stress_test_progress(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id, "status": job["status"],
        "progress_pct": job["progress_pct"], "stage": job["stage"],
        "ticker_count": job.get("ticker_count", 0),
        "started_at": job.get("started_at"),
    }
