from fastapi import APIRouter, Depends, HTTPException
from core.logging_config import get_logger
from helpers import AlertAddRequest, AlertRemoveRequest
from core.security import require_auth, require_user_match, assert_same_user
from services.entitlement_service import QuotaExceeded
from services.alerts_service import (
    add_price_alert,
    remove_price_alert,
    get_alerts_data,
    check_alerts,
)

router = APIRouter(tags=["Price Alerts"])
logger = get_logger("alerts")

@router.post("/alerts/add")
def alerts_add_endpoint(req: AlertAddRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    try:
        return add_price_alert(req.user_id, req.ticker, req.target_price, req.direction)
    except QuotaExceeded as e:
        raise HTTPException(status_code=402, detail=e.http_detail())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/alerts/remove")
def alerts_remove_endpoint(req: AlertRemoveRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    try:
        return remove_price_alert(req.user_id, req.alert_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

# GH-656: iOS decodes AlertsResponse {"alerts": [...]} and
# AlertCheckResponse {"newly_triggered": [...]}; a bare list decodes as empty.
@router.get("/alerts/{user_id}")
def alerts_get_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
    try:
        return {"alerts": get_alerts_data(user_id)}
    except Exception:
        logger.exception("Failed to fetch alerts for user %s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/alerts/check/{user_id}")
def alerts_check_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
    try:
        return {"newly_triggered": check_alerts(user_id)}
    except Exception:
        logger.exception("Failed to check alerts for user %s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")
