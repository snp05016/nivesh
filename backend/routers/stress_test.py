from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional

from helpers import get_session, require_auth
from database import Portfolio
from services.stress_test import run_stress_test

router = APIRouter()

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
    with get_session() as db:
        holdings = db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == req.portfolio_id
        ).all()

    if not holdings:
        return {"results": []}

    results = run_stress_test(holdings, req.scenarios)
    return {"results": results}
