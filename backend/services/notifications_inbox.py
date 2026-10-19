"""Notification inbox service — CRUD for in_app_notifications table."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from database import get_session
from models.db_models import InAppNotification
from services.advisory_guard import first_advisory_term, neutralize_push

logger = logging.getLogger(__name__)
_ANALYZE_PREFIX = "nivesh://analyze/"


def create_notification(
    user_id: int,
    type: str,
    title: str,
    body: str,
    action_url: Optional[str] = None,
    session=None,
) -> int:
    """Write an inbox row. With a caller session it only flushes (caller commits).
    Tip-like text is replaced with a neutral pair (I03 backstop for direct writers)."""
    ticker = action_url[len(_ANALYZE_PREFIX):] if action_url and action_url.startswith(_ANALYZE_PREFIX) else None
    safe_title, safe_body, changed = neutralize_push(title, body, ticker or None)
    if changed:
        logger.warning("push_advisory_blocked", extra={
            "category": type, "term": first_advisory_term(title) or first_advisory_term(body)})
    title, body = safe_title, safe_body
    notif = InAppNotification(
        user_id=user_id, type=type, title=title[:200], body=body, action_url=action_url
    )
    if session is not None:
        session.add(notif)
        session.flush()
        return notif.id
    with get_session() as own:
        own.add(notif)
        own.commit()
        return notif.id


def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """ISO-8601 with an explicit UTC offset. created_at is a naive UTC column."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


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
                "created_at": _iso_utc(n.created_at),  # type: ignore[arg-type]
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
