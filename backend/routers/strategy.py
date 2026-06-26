from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from services.strategy_engine import run_backtest

router = APIRouter(prefix="/api/v1/analysis", tags=["Strategy Lab"])
router_legacy = APIRouter(prefix="", tags=["Strategy Lab"])
logger = logging.getLogger(__name__)

class BacktestRequest(BaseModel):
    ticker: str
    strategy_id: str
    years: int = 5

@router.post("/backtest")
def backtest_endpoint(req: BacktestRequest):
    try:
        result = run_backtest(req.ticker, req.strategy_id, req.years)
        return result
    except ValueError as ve:
        logger.warning(f"Backtest warning: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router_legacy.post("/analysis/backtest")
def backtest_legacy(req: BacktestRequest):
    return backtest_endpoint(req)
