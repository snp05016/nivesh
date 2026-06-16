from fastapi import APIRouter, HTTPException, Depends
from database import get_session, Portfolio
from core.security import require_auth
from services.correlation_engine import compute_portfolio_correlation
import traceback
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Portfolio"])

@router.get("/portfolio/correlation")
def get_portfolio_correlation(portfolio_id: str, user_id: int = Depends(require_auth)):
    if portfolio_id != "holdings":
        raise HTTPException(status_code=400, detail="Only 'holdings' portfolio_id is supported")
        
    try:
        with get_session() as session:
            holdings = session.query(Portfolio).filter(
                Portfolio.user_id == user_id, 
                Portfolio.group_name == "holdings"
            ).all()
            
            if not holdings:
                return {
                    "correlation_matrix": [],
                    "diversification_score": 0,
                    "sector_concentration": [],
                    "suggestions": [],
                    "error": None,
                    "message": f"No holdings found for user {user_id}"
                }
            
            try:
                result = compute_portfolio_correlation(holdings)
                result["error"] = None
                return result
            except Exception as compute_err:
                logger.error(f"Correlation computation failed for user {user_id}: {compute_err}")
                logger.error(traceback.format_exc())
                return {
                    "correlation_matrix": [],
                    "diversification_score": 0,
                    "sector_concentration": [],
                    "suggestions": [],
                    "error": f"Computation error: {str(compute_err)}",
                    "holdings_count": len(holdings),
                    "holdings_tickers": [h.ticker for h in holdings]
                }
    except Exception as db_err:
        logger.error(f"Database error in correlation endpoint for user {user_id}: {db_err}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(db_err)}"
        )
