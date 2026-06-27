"""Notification inbox service — CRUD for in_app_notifications table."""
from datetime import datetime, timezone, timedelta
from database import get_session
from models.db_models import InAppNotification


def get_notifications(user_id: int, limit: int = 50) -> list[dict]:
    with get_session() as session:
        notifs = (
            session.query(InAppNotification)
            .filter(InAppNotification.user_id == user_id)
            .order_by(InAppNotification.is_read.asc(), InAppNotification.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "is_read": n.is_read,
                "action_url": n.action_url,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifs
        ]


def mark_read(notification_id: int, user_id: int) -> bool:
    with get_session() as session:
        notif = (
            session.query(InAppNotification)
            .filter(InAppNotification.id == notification_id, InAppNotification.user_id == user_id)
            .first()
        )
        if not notif:
            return False
        notif.is_read = True
        session.commit()
        return True


def cleanup_old():
    """Delete notifications older than 14 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    with get_session() as session:
        deleted = (
            session.query(InAppNotification)
            .filter(InAppNotification.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return deleted
