import threading
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional

from helpers import get_session, require_auth
from database import Portfolio
from services.stress_test import run_stress_test

router = APIRouter()

_stress_test_lock = threading.Lock()
_active_stress_tests = 0

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
def run_portfolio_stress_test(req: StressTestRequest, user_id: int = Depends(require_auth)):
    global _active_stress_tests
    
    with get_session() as db:
        holdings = db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == req.portfolio_id
        ).all()

    if not holdings:
        return {"results": []}

    with _stress_test_lock:
        _active_stress_tests += 1
        
    try:
        results = run_stress_test(holdings, req.scenarios)
        return {"results": results}
    finally:
        with _stress_test_lock:
            _active_stress_tests -= 1

@router.get("/api/v1/portfolio/stress-test/status")
def get_stress_test_status():
    """Returns whether any stress tests are currently running."""
    with _stress_test_lock:
        is_running = _active_stress_tests > 0
        count = _active_stress_tests
    return {"is_running": is_running, "active_count": count}

