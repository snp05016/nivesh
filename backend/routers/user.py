import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from datetime import datetime, timezone
import time
from pydantic import BaseModel
from typing import Optional

from helpers import verify_access_token, WatchlistAddRequest, WatchlistRemoveRequest, upsert_device_token
from core.security import require_admin
import services.user_service as user_service

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
def watchlist_add_endpoint(req: WatchlistAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return user_service.add_to_watchlist(req.user_id, req.ticker, req.company_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/watchlist/remove")
def watchlist_remove_endpoint(req: WatchlistRemoveRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return user_service.remove_from_watchlist(req.user_id, req.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/watchlist/{user_id}")
def watchlist_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
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
def notifications_register_device(req: DeviceTokenRegisterRequest):
    """
    Register or update a device token. Delegates to shared upsert helper.
    """
    try:
        return upsert_device_token(req.user_id, req.device_token, req.platform or "ios")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/notifications/test")
def notifications_test(req: TestNotificationRequest):
    try:
        return user_service.test_notification(req.user_id, req.ticker, req.exchange)
    except Exception as e:
        return {
            "title": f"{req.ticker.upper()} — Analysis",
            "body": "Tap to view latest analysis",
            "data": {"ticker": req.ticker.upper(), "exchange": req.exchange},
        }


@router.post("/notifications/morning-summary-push")
def notifications_morning_summary_push(req: MorningSummaryPushRequest):
    try:
        result = user_service.push_morning_summary(req.user_id)
        if result is None:
            raise HTTPException(status_code=404, detail="User not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/v1/experts")
def get_experts():
    return user_service.get_experts_service()


@router.get("/api/v1/expert-posts")
def get_expert_posts(limit: int = 30):
    return user_service.get_expert_posts_service(limit)


@router.get("/api/v1/admin/error-telemetry")
def get_error_telemetry(token: int = Depends(require_admin)):
    """
    Admin endpoint to get recent error logs.
    """
    return user_service.fetch_error_telemetry()
