from fastapi import APIRouter, HTTPException, Depends
from database import get_session, Portfolio
from core.security import require_auth
from services.correlation_engine import compute_portfolio_correlation

router = APIRouter(tags=["Portfolio"])

@router.get("/portfolio/correlation")
def get_portfolio_correlation(portfolio_id: str, user_id: int = Depends(require_auth)):
    if portfolio_id != "holdings":
        raise HTTPException(status_code=400, detail="Only 'holdings' portfolio_id is supported")
        
    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id, 
            Portfolio.group_name == "holdings"
        ).all()
        
        result = compute_portfolio_correlation(holdings)
        return result
