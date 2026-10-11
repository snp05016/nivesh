from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from helpers import require_admin
from services.notifications_service import (
    register_user_device,
    dispatch_mock_push,
    fetch_notification_errors
)

router = APIRouter(tags=["Notifications"])

class RegisterDeviceRequest(BaseModel):
    user_id: int
    device_token: str
    platform: str = "ios"

class PushMockRequest(BaseModel):
    device_token: str
    title: str = "Nivesh Alert"
    body: str = "Test notification"
    user_id: int = 0

@router.post("/api/v1/notifications/register")
def register_device(req: RegisterDeviceRequest, authorization: str = Header(None)):
    try:
        return register_user_device(authorization, req.user_id, req.device_token, req.platform)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/dev/push-mock")
def push_mock(req: PushMockRequest, _admin: int = Depends(require_admin)):
    try:
        return dispatch_mock_push(req.device_token, req.title, req.body, req.user_id)
    except PermissionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/admin/notification-errors")
def get_notification_errors(authorization: str = Header(None)):
    require_admin(authorization)
    try:
        return fetch_notification_errors()
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
