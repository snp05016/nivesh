from fastapi import APIRouter, Depends, HTTPException

from core.feature_flags import is_enabled
from core.security import require_auth
from services import risk_flags_service

router = APIRouter(tags=["Risk flags"])


@router.get("/api/v1/stocks/{symbol}/risk-flags")
def get_risk_flags(symbol: str, user_id: int = Depends(require_auth)) -> dict:
    """At most three plain risk facts about a stock the user holds, each with source and date."""
    if not (is_enabled("risk_flags_concentration") or is_enabled("risk_flags_surveillance")):
        raise HTTPException(status_code=404, detail={"code": "FEATURE_DISABLED", "feature": "risk_flags"})
    try:
        return risk_flags_service.risk_flags(user_id, symbol)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "INVALID_SYMBOL"})
