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

from database import get_session
from models.db_models import UserSubscription

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


def get_or_create_subscription(user_id: int) -> dict:
    """Returns the user's subscription row, creating a default free-tier
    row on first access (mirrors services/preferences.py's lazy-create shape)."""
    with get_session() as session:
        sub = session.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            sub = UserSubscription(user_id=user_id, tier="free", is_active=True)
            session.add(sub)
            session.commit()
            session.refresh(sub)
        return _to_dict(sub)


def mock_upgrade(user_id: int, tier: str, billing_cycle: str) -> dict:
    """MOCK upgrade — no real StoreKit purchase completion or payment
    processor call happens here; this simply records the requested tier
    and computes a demo renewal date, simulating a completed purchase.

    Sets tier + billing_cycle, (re)starts the subscription clock, computes
    renews_at as now + 1 month (monthly) or + 1 year (annual), and clears
    any prior cancellation state.
    """
    if tier not in VALID_TIERS or tier == "free":
        raise ValueError(f"tier must be one of {VALID_TIERS[1:]} for an upgrade")
    if billing_cycle not in VALID_BILLING_CYCLES:
        raise ValueError(f"billing_cycle must be one of {VALID_BILLING_CYCLES}")

    now = datetime.now(timezone.utc)
    delta = _MONTHLY_DELTA if billing_cycle == "monthly" else _ANNUAL_DELTA

    with get_session() as session:
        sub = session.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            sub = UserSubscription(user_id=user_id)
            session.add(sub)

        sub.tier = tier
        sub.billing_cycle = billing_cycle
        sub.started_at = sub.started_at or now
        sub.renews_at = now + delta
        sub.is_active = True
        sub.cancelled_at = None
        session.commit()
        session.refresh(sub)
        return _to_dict(sub)


def mock_cancel(user_id: int) -> dict:
    """MOCK cancel — no real payment processor call. Marks the subscription
    inactive and stamps cancelled_at, but deliberately leaves `tier`
    unchanged: the user keeps their paid-for tier through `renews_at`
    (typical "cancel at period end" behaviour). See the UserSubscription
    docstring in models/db_models.py — there is NO cron job in this repo
    that flips `tier` back to "free" once `renews_at` passes; that revert
    is logical/expected only, and any caller needing the "true" current
    entitlement must derive it from is_active + renews_at rather than
    trusting `tier` alone.
    """
    with get_session() as session:
        sub = session.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            sub = UserSubscription(user_id=user_id, tier="free", is_active=True)
            session.add(sub)
            session.commit()
            session.refresh(sub)
            # Nothing to cancel — user was already on the free tier.
            return _to_dict(sub)

        sub.is_active = False
        sub.cancelled_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(sub)
        return _to_dict(sub)
