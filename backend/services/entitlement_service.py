"""Entitlement service — server-side per-tier feature gating.

Controller-Service-Repository: routers only call has_entitlement() /
get_effective_tier() from here; no ORM access happens in routers.

The effective tier is the stored `tier` as returned by
subscription_service.get_or_create_subscription(), which reverts any paid plan
whose `renews_at` has passed (cancelled or not) to "free" on read — the single
source of truth for expiry (FINSEC-13).
"""
from services import subscription_service

# Tier ranking — higher number == more entitlements. Used to compare a
# user's effective tier against a feature's minimum required tier.
TIER_RANK = {"free": 0, "pro": 1, "super_pro": 2}

# Feature keys mapped to their minimum required tier. Every key here must be
# enforced by a require_entitlement("<key>") dependency on a real endpoint
# (tests/test_entitlement_catalog.py checks this): the paywall is generated
# from this table, so it never advertises a perk the server does not gate.
FEATURE_MIN_TIER = {
    # No prediction-performance perk: the dashboards are admin-only QA, not a
    # sold perk (REG-11: unverified hit-rate claims about our own calls, no PaRRVA).
    "sector_rotation": "pro",         # routers/sector_rotation.py market rotation analytics
    "comprehensive_stock_insights": "pro",  # routers/fundamentals.py valuation endpoints (real DB-backed CompanyValuation)
    "swot_analysis": "pro",           # routers/fundamentals.py risk-signals endpoints (real DB-backed RiskSignal)
    "technical_picks": "pro",         # routers/strategy.py /backtest — real technical-rule backtest engine (services/strategy_engine.py)
    "ideas_for_profit": "pro",        # routers/options_strategy.py /options/payoff — real multi-leg options P&L/strategy builder
}

# Per-tier count caps, enforced on create via enforce_quota(). None == unlimited.
TIER_LIMITS = {
    "watchlist_size": {"free": 10, "pro": 100, "super_pro": None},
    "price_alerts": {"free": 5, "pro": 50, "super_pro": None},
}

QUOTA_NOUNS = {"watchlist_size": "watchlist stocks", "price_alerts": "active price alerts"}


class QuotaExceeded(Exception):
    """Raised by enforce_quota(); routers map it to HTTP 402 (same detail shape
    as core/entitlement_gate.py so iOS shows the upgrade prompt)."""

    def __init__(self, feature: str, limit: int, tier: str):
        self.feature, self.limit, self.tier = feature, limit, tier
        # Next tier up (limits rise strictly with rank).
        self.required_tier = next(
            (t for t, rank in sorted(TIER_RANK.items(), key=lambda kv: kv[1]) if rank > TIER_RANK.get(tier, 0)),
            None,
        )
        super().__init__(f"Your plan allows {limit} {QUOTA_NOUNS.get(feature, feature)}.")

    def http_detail(self) -> dict:
        return {"message": str(self), "required_tier": self.required_tier, "current_tier": self.tier}


def enforce_quota(user_id: int, feature: str, current_count: int) -> None:
    """Raises QuotaExceeded when adding one more item would exceed the
    user's effective-tier cap for `feature` (current_count is the count
    before the add)."""
    tier = get_effective_tier(user_id)
    limit = TIER_LIMITS[feature].get(tier, TIER_LIMITS[feature]["free"])
    if limit is not None and current_count >= limit:
        raise QuotaExceeded(feature, limit, tier)


# User-facing paywall titles for FEATURE_MIN_TIER keys.
FEATURE_TITLES = {
    "sector_rotation": "Sector rotation analytics",
    "comprehensive_stock_insights": "Valuation insights",
    "swot_analysis": "Risk signals",
    "technical_picks": "Strategy backtester",
    "ideas_for_profit": "Options strategy builder",
}


def get_feature_catalog() -> list[dict]:
    """Returns [{key, title, min_tier}] for every gated feature, cheapest tier first —
    the single source the iOS paywall renders its feature list and matrix from."""
    catalog = [
        {"key": key, "title": FEATURE_TITLES.get(key, key), "min_tier": min_tier}
        for key, min_tier in FEATURE_MIN_TIER.items()
    ]
    return sorted(catalog, key=lambda c: (TIER_RANK.get(c["min_tier"], 0), c["title"]))


def get_effective_tier(user_id: int) -> str:
    """Returns the user's *effective* (actually-entitled) subscription tier:
    "free" with no row or once the paid period (`renews_at`) has ended;
    otherwise the stored tier, including a cancelled plan whose paid period
    is still running. Expiry lives in subscription_service._load_subscription.
    """
    return subscription_service.get_or_create_subscription(user_id).get("tier", "free")


def has_entitlement(user_id: int, feature_key: str) -> bool:
    """Returns True if the user's effective tier meets or exceeds the
    minimum tier required for feature_key.

    Unknown feature keys fail closed (False): a typo must never ungate a
    paid route (AUTH-14). require_entitlement() rejects them at import time.
    """
    required_tier = FEATURE_MIN_TIER.get(feature_key)
    if required_tier is None:
        return False

    effective_tier = get_effective_tier(user_id)
    return TIER_RANK.get(effective_tier, 0) >= TIER_RANK.get(required_tier, 0)


def get_all_entitlements(user_id: int) -> dict:
    """Returns {tier, features: {feature_key: bool}, catalog} for the current user —
    consumed by GET /api/v1/subscription/entitlements for the iOS paywall
    to decide what to show/gate client-side."""
    effective_tier = get_effective_tier(user_id)
    tier_rank = TIER_RANK.get(effective_tier, 0)
    features = {
        feature_key: tier_rank >= TIER_RANK.get(min_tier, 0)
        for feature_key, min_tier in FEATURE_MIN_TIER.items()
    }
    return {"tier": effective_tier, "features": features, "catalog": get_feature_catalog()}
