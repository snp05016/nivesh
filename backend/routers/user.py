import logging
from fastapi import APIRouter, HTTPException, Header, Depends, Query
from datetime import datetime, timezone
import time
from pydantic import BaseModel
from typing import Optional

from helpers import WatchlistAddRequest, WatchlistRemoveRequest, upsert_device_token
from core.security import require_admin, require_auth, require_user_match, assert_same_user
import services.user_service as user_service
from services.entitlement_service import QuotaExceeded

router = APIRouter(tags=["User"])

class DeviceTokenRegisterRequest(BaseModel):
    user_id: int
    device_token: str
    platform: str = "ios"

class TestNotificationRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"

class MorningSummaryPushRequest(BaseModel):
    user_id: int


@router.get("/users")
def list_users(authorization: str = Header(None)):
    require_admin(authorization)
    return user_service.get_all_users()


@router.post("/watchlist/add")
def watchlist_add_endpoint(req: WatchlistAddRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    try:
        return user_service.add_to_watchlist(req.user_id, req.ticker, req.company_name)
    except QuotaExceeded as e:
        raise HTTPException(status_code=402, detail=e.http_detail())
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/watchlist/remove")
def watchlist_remove_endpoint(req: WatchlistRemoveRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    try:
        return user_service.remove_from_watchlist(req.user_id, req.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/watchlist/{user_id}")
def watchlist_get_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
    try:
        result = user_service.get_watchlist(user_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/notifications/register-device")
def notifications_register_device(req: DeviceTokenRegisterRequest, token_user: int = Depends(require_auth)):
    """
    Register or update a device token for the token's user (AUTH-09: the body
    user_id must match it). Delegates to shared upsert helper.
    """
    assert_same_user(req.user_id, token_user)
    try:
        return upsert_device_token(token_user, req.device_token, req.platform or "ios")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=409, detail="Device token already registered")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/notifications/test")
def notifications_test(req: TestNotificationRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    try:
        return user_service.test_notification(token_user, req.ticker, req.exchange)
    except Exception:
        logging.exception("[NOTIFICATIONS/TEST] failed for user %s", req.user_id)
        raise HTTPException(status_code=503, detail="Could not build test notification")


@router.post("/notifications/morning-summary-push")
def notifications_morning_summary_push(req: MorningSummaryPushRequest, token_user: int = Depends(require_auth)):
    # Writes an inbox row + sends a push for req.user_id: only that user may trigger it.
    if req.user_id != token_user:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        result = user_service.push_morning_summary(req.user_id)
        if result is None:
            raise HTTPException(status_code=404, detail="User not found")
        return result
    except HTTPException:
        raise
    except RuntimeError:
        # GH-651: no brief could be built; nothing was pushed.
        raise HTTPException(status_code=503, detail="Morning summary unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/v1/experts")
def get_experts():
    return user_service.get_experts_service()


@router.get("/api/v1/expert-posts")
def get_expert_posts(limit: int = Query(30, ge=1, le=100)):
    return user_service.get_expert_posts_service(limit)


@router.get("/api/v1/admin/error-telemetry")
def get_error_telemetry(token: int = Depends(require_admin)):
    """
    Admin endpoint to get recent error logs.
    """
    return user_service.fetch_error_telemetry()
