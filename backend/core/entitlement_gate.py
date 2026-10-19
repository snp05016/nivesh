"""FastAPI dependency factory for server-side per-tier feature gating.

Usage in a router:

    from core.entitlement_gate import require_entitlement

    @router.get("/some-premium-endpoint")
    def some_premium_endpoint(user_id: int = Depends(require_entitlement("sector_rotation"))):
        ...

Raises HTTPException(402) — Payment Required — when the caller's effective
tier (see services/entitlement_service.entitled_tier) does not meet
the feature's minimum required tier.
"""
from fastapi import Depends, HTTPException

from core.security import require_auth
from services import entitlement_service


def require_entitlement(feature_key: str):
    """Returns a FastAPI dependency that resolves the caller's user_id via
    require_auth, then enforces has_entitlement(user_id, feature_key).

    Raises ValueError for a key missing from FEATURE_MIN_TIER, so a typo fails
    app import instead of silently ungating the route (AUTH-14).
    """
    if feature_key not in entitlement_service.FEATURE_MIN_TIER:
        raise ValueError(f"unknown entitlement feature key: {feature_key!r}")

    def _dependency(user_id: int = Depends(require_auth)) -> int:
        if not entitlement_service.has_entitlement(user_id, feature_key):
            required_tier = entitlement_service.FEATURE_MIN_TIER.get(feature_key)
            current_tier = entitlement_service.entitled_tier(user_id)
            raise HTTPException(
                status_code=402,
                detail={
                    "message": f"'{feature_key}' requires the '{required_tier}' tier or higher",
                    "required_tier": required_tier,
                    "current_tier": current_tier,
                },
            )
        return user_id

    return _dependency
