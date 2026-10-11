import os
import json
import logging
from datetime import datetime, timezone
from helpers import (
    get_session,
    NotificationErrorLog,
    log_notification_error,
    upsert_device_token,
    verify_access_token
)

def register_user_device(authorization: str, user_id: int, device_token: str, platform: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise PermissionError("Bearer token required")
    
    token_user = verify_access_token(authorization.split(" ", 1)[1])
    if token_user is None:
        raise PermissionError("Invalid or expired token")
        
    try:
        upsert_device_token(token_user, device_token, platform)
        return {
            "status": "registered",
            "device_token": device_token,
        }
    except (ValueError, PermissionError):
        raise
    except Exception as e:
        log_notification_error(
            failure_point="token_registration",
            error_trace=type(e).__name__,
            target_device=device_token,
        )
        raise RuntimeError("Internal server error")

def dispatch_mock_push(device_token: str, title: str, body: str, user_id: int):
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise PermissionError("Not found")
        
    payload = {
        "aps": {
            "alert": {
                "title": title,
                "body": body,
            },
            "sound": "default",
            "badge": 1,
        },
        "user_id": user_id,
    }

    try:
        logging.info(f"[APNs MOCK] Dispatching to {device_token[:8]}...: {json.dumps(payload)}")
        return {
            "status": "queued",
            "payload": payload,
        }
    except Exception as e:
        log_notification_error(
            failure_point="apns_dispatch",
            error_trace=str(e),
            target_device=device_token,
        )
        raise RuntimeError("Internal server error")

def fetch_notification_errors():
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
