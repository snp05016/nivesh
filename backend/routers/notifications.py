"""
Push notification pipeline — device token registration, dev push mock, error telemetry.
"""

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

from helpers import (
    get_session,
    DeviceToken,
    NotificationErrorLog,
    log_notification_error,
    require_admin,
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
def register_device(req: RegisterDeviceRequest):
    """Register or update a device token for push notifications."""
    try:
        with get_session() as session:
            existing = (
                session.query(DeviceToken)
                .filter_by(device_token=req.device_token)
                .first()
            )
            if existing:
                # Update existing record
                existing.user_id = req.user_id
                existing.platform = req.platform
                existing.updated_at = datetime.utcnow()
            else:
                # Insert new record
                new_token = DeviceToken(
                    user_id=req.user_id,
                    device_token=req.device_token,
                    platform=req.platform,
                )
                session.add(new_token)
            session.commit()

        return {
            "status": "registered",
            "device_token": req.device_token,
        }
    except Exception as e:
        log_notification_error(
            failure_point="token_registration",
            error_trace=str(e),
            target_device=req.device_token,
        )
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /api/v1/dev/push-mock
# ---------------------------------------------------------------------------

@router.post("/api/v1/dev/push-mock")
def push_mock(req: PushMockRequest):
    """Dev-only mock push notification — logs payload, returns success.
    Real APNs dispatch requires production certificates and key provisioning.
    """
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
        print(f"[APNs MOCK] Dispatching to {req.device_token}: {json.dumps(payload)}")

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
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /api/v1/admin/notification-errors
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/notification-errors")
def get_notification_errors(authorization: str = Header(None)):
    """Fetch the 50 most recent notification pipeline errors. Admin-only."""
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
            "fetched_at": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
