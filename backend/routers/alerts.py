from fastapi import APIRouter, HTTPException, Header
from core.logging_config import get_logger
from helpers import verify_access_token, AlertAddRequest, AlertRemoveRequest
from services.alerts_service import (
    add_price_alert,
    remove_price_alert,
    get_alerts_data,
    price_alert_poller as _price_alert_poller
)

router = APIRouter(tags=["Price Alerts"])
logger = get_logger("alerts")

@router.post("/alerts/add")
def alerts_add_endpoint(req: AlertAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return add_price_alert(req.user_id, req.ticker, req.target_price, req.direction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/alerts/remove")
def alerts_remove_endpoint(req: AlertRemoveRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return remove_price_alert(req.user_id, req.alert_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/alerts/{user_id}")
@router.get("/alerts/check/{user_id}")
def alerts_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return get_alerts_data(user_id)
    except Exception:
        logger.exception("Failed to fetch alerts for user %s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")
