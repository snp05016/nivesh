"""Notification Inbox API — GET /api/v1/notifications, PUT mark read."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from core.security import require_auth
from services.notifications_inbox import get_notifications, mark_read

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications Inbox"])


class NotificationItem(BaseModel):
    id: int
    type: str
    title: str
    body: str
    is_read: bool
    action_url: Optional[str] = None
    created_at: Optional[str] = None


@router.get("", response_model=List[NotificationItem])
def list_notifications(limit: int = Query(50, ge=1, le=200), user_id: int = Depends(require_auth)):
    return get_notifications(user_id, limit=limit)


@router.put("/{notification_id}/read")
def mark_notification_read(notification_id: int, user_id: int = Depends(require_auth)):
    if not mark_read(notification_id, user_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}
