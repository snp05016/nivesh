from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from services.earnings_surprise import get_all_surprises, get_surprise_history

router = APIRouter(tags=["earnings"])

class EarningsSurpriseResponse(BaseModel):
    ticker: str
    company_name: str
    quarter: str
    estimated_eps: Optional[float] = None
    actual_eps: Optional[float] = None
    surprise_pct: Optional[float] = None
    classification: str
    post_price_1d: Optional[float] = None
    post_price_5d: Optional[float] = None
    historical_score: Optional[float] = None
    serial_pattern: Optional[str] = None

@router.get("/api/v1/earnings/surprises", response_model=List[EarningsSurpriseResponse])
async def api_get_earnings_surprises(period: str = "current_quarter"):
    try:
        results = await get_all_surprises(period)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/earnings/surprise-history/{ticker}", response_model=List[EarningsSurpriseResponse])
async def api_get_earnings_surprise_history(ticker: str):
    try:
        ticker = ticker.upper()
        results = await get_surprise_history(ticker)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
