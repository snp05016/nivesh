from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import List

from helpers import get_session, require_auth
from database import Portfolio
from services.stress_test import run_stress_test

router = APIRouter()

class StressTestRequest(BaseModel):
    scenarios: List[str]
    portfolio_id: str

@router.post("/api/v1/portfolio/stress-test")
def portfolio_stress_test(req: StressTestRequest, authorization: str = Header(None)):
    user_id = require_auth(authorization)
    with get_session() as db:
        holdings = db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == req.portfolio_id
        ).all()
        
    if not holdings:
        return {"results": []}
        
    results = run_stress_test(holdings, req.scenarios)
    return {"results": results}
