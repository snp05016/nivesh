from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import logging
from services.strategy_engine import run_backtest
from core.entitlement_gate import require_entitlement

router = APIRouter(prefix="/api/v1/analysis", tags=["Strategy Lab"])
router_legacy = APIRouter(prefix="", tags=["Strategy Lab"])
logger = logging.getLogger(__name__)

class BacktestRequest(BaseModel):
    ticker: str
    strategy_id: str
    years: int = 5

def _run_backtest(req: BacktestRequest):
    try:
        return run_backtest(req.ticker, req.strategy_id, req.years)
    except ValueError as ve:
        logger.warning(f"Backtest warning: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/backtest")
def backtest_endpoint(req: BacktestRequest, user_id: int = Depends(require_entitlement("technical_picks"))):
    """
    Gated behind the "technical_picks" entitlement (pro tier or higher) —
    see services/entitlement_service.py / core/entitlement_gate.py.
    """
    return _run_backtest(req)


@router_legacy.post("/analysis/backtest")
def backtest_legacy(req: BacktestRequest, user_id: int = Depends(require_entitlement("technical_picks"))):
    return _run_backtest(req)
