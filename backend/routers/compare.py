from fastapi import APIRouter, Depends, HTTPException, Query
from core.security import require_auth
from typing import List, Dict, Any

router = APIRouter(prefix="/api/v1/compare", tags=["Compare"])

@router.get("/")
def compare_stocks(
    tickers: List[str] = Query(..., description="List of up to 3 tickers to compare"),
    user_id: int = Depends(require_auth)
) -> Dict[str, Any]:
    """Compare up to 3 stock tickers."""
    if not tickers:
        raise HTTPException(status_code=400, detail="At least one ticker must be provided")
    if len(tickers) > 3:
        raise HTTPException(status_code=400, detail="Cannot compare more than 3 tickers at once")
    
    return {"status": "success", "comparing": [t.upper() for t in tickers]}
