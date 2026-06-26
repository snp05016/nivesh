import logging
"""
Push notification pipeline — device token registration, dev push mock, error telemetry.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

from helpers import (
    get_session,
    DeviceToken,
    NotificationErrorLog,
    log_notification_error,
    require_admin,
    upsert_device_token,
)

router = APIRouter(tags=["Notifications"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class RegisterDeviceRequest(BaseModel):
    user_id: int
    device_token: str
    platform: str = "ios"


class PushMockRequest(BaseModel):
    device_token: str
    title: str = "Nivesh Alert"
    body: str = "Test notification"
    user_id: int = 0


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/register
# ---------------------------------------------------------------------------

@router.post("/api/v1/notifications/register")
def register_device(req: RegisterDeviceRequest, authorization: str = Header(None)):
    """
    Register or update a device token for push notifications.

Requires Bearer token authentication. The user_id is derived from the
token, not from the request body — this prevents push notification
hijacking via a forged user_id.

    Args:
        req (RegisterDeviceRequest): The req.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import verify_access_token

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token_user = verify_access_token(authorization.split(" ", 1)[1])
    if token_user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if token_user != req.user_id:
        # Despite the body, only the authenticated principal matters.
        # If there's a mismatch we still use the token identity.
        pass

    try:
        upsert_device_token(token_user, req.device_token, req.platform)
        return {
            "status": "registered",
            "device_token": req.device_token,
        }
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_notification_error(
            failure_point="token_registration",
            error_trace=type(e).__name__,
            target_device=req.device_token,
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# POST /api/v1/dev/push-mock
# ---------------------------------------------------------------------------

@router.post("/api/v1/dev/push-mock")
def push_mock(req: PushMockRequest):
    """
    Dev-only mock push notification — logs payload, returns success.
Disabled in production. Real APNs dispatch goes through alerts.py.

    Args:
        req (PushMockRequest): The req.

    Returns:
        Any: The response.
    """
    import os
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    payload = {
        "aps": {
            "alert": {
                "title": req.title,
                "body": req.body,
            },
            "sound": "default",
            "badge": 1,
        },
        "user_id": req.user_id,
    }

    try:
        # In production, this would use aioapns / PyAPNs2 to dispatch.
        # For now, log the payload as proof the pipeline is wired correctly.
        logging.info(f"[APNs MOCK] Dispatching to {req.device_token}: {json.dumps(payload)}")

        return {
            "status": "queued",
            "payload": payload,
        }
    except Exception as e:
        log_notification_error(
            failure_point="apns_dispatch",
            error_trace=str(e),
            target_device=req.device_token,
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /api/v1/admin/notification-errors
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/notification-errors")
def get_notification_errors(authorization: str = Header(None)):
    """
    Fetch the 50 most recent notification pipeline errors. Admin-only.

    Args:
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_admin(authorization)

    try:
        with get_session() as session:
            rows = (
                session.query(NotificationErrorLog)
                .order_by(NotificationErrorLog.timestamp.desc())
                .limit(50)
                .all()
            )

            errors = [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "failure_point": r.failure_point,
                    "error_trace": r.error_trace,
                    "target_device": r.target_device,
                }
                for r in rows
            ]

        return {
            "errors": errors,
            "count": len(errors),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
