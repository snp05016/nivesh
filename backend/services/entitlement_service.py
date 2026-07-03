"""Entitlement service — server-side per-tier feature gating.

Controller-Service-Repository: routers only call has_entitlement() /
get_effective_tier() from here; no ORM access happens in routers.

This module derives a user's *effective* tier from UserSubscription rather
than trusting the stored `tier` column blindly. See the UserSubscription
docstring in models/db_models.py: once `is_active` is False (the user
cancelled) and `renews_at` has passed, there is no cron job in this repo
that flips `tier` back to "free" — so callers that care about "is this
subscription still actually entitled" must derive it themselves. That is
exactly what get_effective_tier() does below.
"""
from datetime import datetime, timezone

from services import subscription_service

# Tier ranking — higher number == more entitlements. Used to compare a
# user's effective tier against a feature's minimum required tier.
TIER_RANK = {"free": 0, "pro": 1, "super_pro": 2}

# Small, representative set of feature keys mapped to their minimum
# required tier. These map to REAL endpoints already present in this
# backend (see routers/predictions.py, routers/sector_rotation.py,
# routers/forum.py) — not invented placeholder features.
FEATURE_MIN_TIER = {
    "advanced_analysis": "pro",       # routers/predictions.py performance/calibration dashboards
    "forum_premium_board": "pro",     # community forum premium discussion boards
    "sector_rotation": "pro",         # routers/sector_rotation.py market rotation analytics
    "alpha_generators": "super_pro",  # high-conviction / alpha-generator style analysis
    "whatsapp_alerts": "super_pro",   # premium delivery channel for alerts/notifications
    "comprehensive_stock_insights": "pro",  # routers/fundamentals.py valuation endpoints (real DB-backed CompanyValuation)
    "swot_analysis": "pro",           # routers/fundamentals.py risk-signals endpoints (real DB-backed RiskSignal)
    "technical_picks": "pro",         # routers/strategy.py /backtest — real technical-rule backtest engine (services/strategy_engine.py)
    "ideas_for_profit": "pro",        # routers/options_strategy.py /options/payoff — real multi-leg options P&L/strategy builder
}


def get_effective_tier(user_id: int) -> str:
    """Returns the user's *effective* (actually-entitled) subscription tier.

    - No subscription row at all -> "free".
    - is_active is False AND renews_at has passed (or is unset) -> "free",
      regardless of what the stale `tier` column says.
    - Otherwise -> the stored `tier` (covers: active subscriptions, and
      cancelled-but-not-yet-lapsed subscriptions that still keep access
      through the end of the billing period they already paid for).
    """
    sub = subscription_service.get_or_create_subscription(user_id)
    tier = sub.get("tier", "free")
    is_active = sub.get("is_active", True)
    renews_at = sub.get("renews_at")

    if is_active:
        return tier

    # is_active is False — subscription was cancelled. Still entitled to
    # `tier` until renews_at, if that date is known and hasn't passed yet.
    if renews_at is not None:
        now = datetime.now(timezone.utc)
        # renews_at may be a naive datetime (SQLite/tests) — normalize.
        if renews_at.tzinfo is None:
            renews_at = renews_at.replace(tzinfo=timezone.utc)
        if renews_at > now:
            return tier

    return "free"


def has_entitlement(user_id: int, feature_key: str) -> bool:
    """Returns True if the user's effective tier meets or exceeds the
    minimum tier required for feature_key.

    Unknown feature keys are treated as ungated (return True) so this
    never accidentally locks out an endpoint that hasn't been added to
    FEATURE_MIN_TIER yet.
    """
    required_tier = FEATURE_MIN_TIER.get(feature_key)
    if required_tier is None:
        return True

    effective_tier = get_effective_tier(user_id)
    return TIER_RANK.get(effective_tier, 0) >= TIER_RANK.get(required_tier, 0)


def get_all_entitlements(user_id: int) -> dict:
    """Returns {tier, features: {feature_key: bool}} for the current user —
    consumed by GET /api/v1/subscription/entitlements for the iOS paywall
    banner to decide what to show/gate client-side."""
    effective_tier = get_effective_tier(user_id)
    tier_rank = TIER_RANK.get(effective_tier, 0)
    features = {
        feature_key: tier_rank >= TIER_RANK.get(min_tier, 0)
        for feature_key, min_tier in FEATURE_MIN_TIER.items()
    }
    return {"tier": effective_tier, "features": features}
