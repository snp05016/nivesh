from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List

from helpers import require_auth
from services import job_manager
from services.stress_test_jobs import (
    get_owned_stress_test_job,
    list_owned_stress_test_jobs,
    mark_stress_test_start_failed,
    prepare_stress_test_job,
    record_stress_test_process,
    run_stress_test_job,
)

router = APIRouter()

class StressTestRequest(BaseModel):
    portfolio_id: str
    scenarios: List[str] = Field(default_factory=list, max_length=20)

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
    launch = prepare_stress_test_job(user_id, req.portfolio_id, req.scenarios)
    if launch.completed_response is not None:
        return launch.completed_response

    try:
        pid = job_manager.spawn_process(
            launch.job_id,
            run_stress_test_job,
            (launch.job_id, launch.holdings, launch.scenarios),
        )
        record_stress_test_process(launch.job_id, pid)
    except job_manager.JobCapacityError as exc:
        mark_stress_test_start_failed(launch.job_id, exc)
        raise HTTPException(
            status_code=429,
            detail="Server busy, please retry shortly",
            headers={"Retry-After": "30"},
        ) from exc
    except Exception as exc:
        mark_stress_test_start_failed(launch.job_id, exc)
        raise HTTPException(status_code=500, detail="Could not start stress test") from exc
    return {"job_id": launch.job_id, "status": "running"}


@router.get("/api/v1/portfolio/stress-test/{job_id}")
def get_stress_test_result(job_id: str, user_id: int = Depends(require_auth)):
    job = get_owned_stress_test_job(job_id, user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Stress test failed: {job['error']}")
    return job


@router.get("/api/v1/portfolio/stress-test/{job_id}/progress")
def get_stress_test_progress(job_id: str, user_id: int = Depends(require_auth)):
    job = get_owned_stress_test_job(job_id, user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@router.get("/api/v1/dashboard/stress-test-jobs")
def list_stress_test_jobs(user_id: int = Depends(require_auth)):
    """
    List stress test jobs belonging to the authenticated user.

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    return list_owned_stress_test_jobs(user_id)
