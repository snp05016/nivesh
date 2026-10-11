"""Subscription service — CRUD + MOCK upgrade/cancel for user_subscriptions.

MOCK DATA — simulated for demo purposes, not a real integration. No real
payment processor (Stripe/Razorpay/etc.) or StoreKit purchase-completion
flow is called anywhere in this module: mock_upgrade() / mock_cancel() just
write the requested state directly to the user_subscriptions table so the
iOS app has something to render for a premium-tier demo.

routers/subscription.py must only validate HTTP input and call functions
here (Controller-Service-Repository). All session.query() calls for
UserSubscription live in this module.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from database import get_session
from models.db_models import UserSubscription
from services.audit_service import audit

VALID_TIERS = ("free", "pro", "super_pro")
VALID_BILLING_CYCLES = ("monthly", "annual")

# Approximate calendar-month/year offsets used for the MOCK renewal date.
# This is a demo stand-in, not a real billing-cycle calculator (no
# dateutil dependency in this repo) — "monthly" = +30 days, "annual" = +365 days.
_MONTHLY_DELTA = timedelta(days=30)
_ANNUAL_DELTA = timedelta(days=365)


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
    cancelled. Nothing renews a mock plan, so `renews_at` is the end of access."""
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


def mock_upgrade(user_id: int, tier: str, billing_cycle: str) -> dict:
    """MOCK upgrade — no real StoreKit purchase completion or payment
    processor call happens here; this simply records the requested tier
    and computes a demo renewal date, simulating a completed purchase.

    Switching to a new tier (or buying again after the plan lapsed) sets
    tier + billing_cycle and starts a new period: renews_at = now + 1 month
    (monthly) or + 1 year (annual). Re-buying the tier the user already has
    while its period is still running only resumes a cancelled plan — it
    never extends renews_at, so replaying the call cannot stretch access.
    """
    if tier not in VALID_TIERS or tier == "free":
        raise ValueError(f"tier must be one of {VALID_TIERS[1:]} for an upgrade")
    if billing_cycle not in VALID_BILLING_CYCLES:
        raise ValueError(f"billing_cycle must be one of {VALID_BILLING_CYCLES}")

    now = datetime.now(timezone.utc)
    delta = _MONTHLY_DELTA if billing_cycle == "monthly" else _ANNUAL_DELTA

    with get_session() as session:
        sub = _load_subscription(session, user_id)  # a lapsed plan is already back to free here
        before = _to_dict(sub)

        if before["tier"] != tier:
            sub.tier = tier
            sub.billing_cycle = billing_cycle
            sub.started_at = sub.started_at or now
            sub.renews_at = now + delta
        sub.is_active = True
        sub.cancelled_at = None
        audit(session, user_id, "subscription_upgraded", {
            "from_tier": before["tier"], "to_tier": tier, "billing_cycle": billing_cycle,
            "was_active": before["is_active"], "renews_at": sub.renews_at,
        })
        session.commit()
        session.refresh(sub)
        return _to_dict(sub)


def mock_cancel(user_id: int) -> dict:
    """MOCK cancel — no real payment processor call. Marks the subscription
    inactive and stamps cancelled_at, but deliberately leaves `tier`
    unchanged: the user keeps their paid-for tier through `renews_at`
    (typical "cancel at period end" behaviour). There is no cron job: the
    next read after `renews_at` reverts the row to free (_load_subscription).
    """
    with get_session() as session:
        sub = _load_subscription(session, user_id)
        current = _to_dict(sub)
        if current["tier"] == "free":
            # Nothing to cancel — user is on the free tier (or the plan lapsed).
            return current

        sub.is_active = False
        sub.cancelled_at = datetime.now(timezone.utc)
        audit(session, user_id, "subscription_cancelled", {"tier": current["tier"], "renews_at": current["renews_at"]})
        session.commit()
        session.refresh(sub)
        return _to_dict(sub)
