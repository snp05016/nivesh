"""GET /api/v1/me/holdings/{ticker}: one holding's detail page (C11, spec 3.2). Flag money_holding_detail."""
import re

from fastapi import APIRouter, Depends, HTTPException

from core.feature_flags import require_flag
from core.security import require_auth
from services.money_holding import get_holding_detail

router = APIRouter(prefix="/api/v1/me", tags=["Money"])

_TICKER_RE = re.compile(r"^[A-Z0-9&.-]{1,20}$")  # exchange symbols and ISINs


@router.get("/holdings/{ticker}", dependencies=[Depends(require_flag("money_holding_detail"))])
def holding_detail(ticker: str, user_id: int = Depends(require_auth)):
    symbol = ticker.strip().upper()
    if not _TICKER_RE.match(symbol):
        raise HTTPException(status_code=422, detail={"code": "INVALID_TICKER", "message": "That isn't a valid ticker."})
    detail = get_holding_detail(user_id, symbol)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_HELD", "message": "This holding is no longer in your portfolio."})
    return detail
