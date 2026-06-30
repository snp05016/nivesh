from fastapi import APIRouter, HTTPException, Depends
from core.security import require_auth
from services.correlation_service import get_portfolio_correlation_data

router = APIRouter(tags=["Portfolio"])

@router.get("/portfolio/correlation")
def get_portfolio_correlation(portfolio_id: str, user_id: int = Depends(require_auth)):
    if portfolio_id != "holdings":
        raise HTTPException(status_code=400, detail="Only 'holdings' portfolio_id is supported")
        
    try:
        return get_portfolio_correlation_data(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
