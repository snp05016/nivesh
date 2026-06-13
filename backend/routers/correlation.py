from fastapi import APIRouter, Header, HTTPException
from database import get_session, verify_access_token, Portfolio
from services.correlation_engine import compute_portfolio_correlation

router = APIRouter(tags=["Portfolio"])

@router.get("/portfolio/correlation")
def get_portfolio_correlation(portfolio_id: str, authorization: str = Header(None)):
    if portfolio_id != "holdings":
        raise HTTPException(status_code=400, detail="Only 'holdings' portfolio_id is supported")
        
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == token_user, 
            Portfolio.group_name == "holdings"
        ).all()
        
    result = compute_portfolio_correlation(holdings)
    return result
