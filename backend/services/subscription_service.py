"""Subscription service — reads, lazily creates and lapses the user_subscriptions row.

Paid tiers will come only from App Store verification (docs/billing/RUNBOOK.md);
nothing in this module grants one.

routers/subscription.py must only validate HTTP input and call functions
here (Controller-Service-Repository). All session.query() calls for
UserSubscription live in this module.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from database import get_session
from models.db_models import UserSubscription
from services.audit_service import audit

VALID_TIERS = ("free", "pro", "super_pro")


def _to_dict(sub: UserSubscription) -> dict:
    return {
        "user_id": sub.user_id,
        "tier": sub.tier,
        "billing_cycle": sub.billing_cycle,
        "started_at": sub.started_at,
        "renews_at": sub.renews_at,
        "is_active": sub.is_active,
        "cancelled_at": sub.cancelled_at,
    }


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    # SQLite/tests hand back naive datetimes; they are stored as UTC.
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _is_lapsed(sub: dict, now: datetime) -> bool:
    """A paid tier whose paid-for period has ended — whether or not the user
    cancelled. `renews_at` is the end of access."""
    if sub["tier"] == "free":
        return False
    renews_at = _as_utc(sub["renews_at"])
    return renews_at is None or renews_at <= now


def _load_subscription(session, user_id: int) -> UserSubscription:
    """Returns the user's row, creating a default free-tier row on first access
    and lazily reverting a lapsed paid plan to free (no cron needed: every
    reader self-heals, so `tier` is always the effective tier)."""
    query = session.query(UserSubscription).filter(UserSubscription.user_id == user_id)
    sub = query.first()
    if sub is None:
        session.add(UserSubscription(user_id=user_id, tier="free", is_active=True))
        try:
            session.commit()
        except IntegrityError:
            # user_id is unique: a concurrent first request won the insert.
            session.rollback()
        sub = query.one()
    if _is_lapsed(_to_dict(sub), datetime.now(timezone.utc)):
        audit(session, user_id, "subscription_lapsed", {"from_tier": sub.tier, "renews_at": sub.renews_at})
        sub.tier = "free"
        sub.billing_cycle = None
        sub.renews_at = None
        sub.is_active = True
        sub.cancelled_at = None
        session.commit()
    return sub


def get_or_create_subscription(user_id: int) -> dict:
    """Returns the user's subscription row, creating a default free-tier
    row on first access (mirrors services/preferences.py's lazy-create shape).
    A paid plan past `renews_at` comes back as free (see _load_subscription)."""
    with get_session() as session:
        return _to_dict(_load_subscription(session, user_id))
