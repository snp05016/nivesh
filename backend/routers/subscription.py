"""Subscription API — /api/v1/subscription.

MOCK — simulated for demo purposes, not a real integration. There is no
real StoreKit purchase-completion handshake and no real payment processor
wired to these endpoints; /upgrade and /cancel just record the requested
state via services/subscription_service.py.
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

from core.security import rate_limited_user, require_auth
from services import entitlement_service, subscription_service

router = APIRouter(prefix="/api/v1/subscription", tags=["Subscription"])


class FeatureCatalogEntry(BaseModel):
    key: str
    title: str
    min_tier: str


class EntitlementsResponse(BaseModel):
    tier: str
    features: Dict[str, bool]
    catalog: List[FeatureCatalogEntry] = []


class SubscriptionResponse(BaseModel):
    user_id: int
    tier: str
    billing_cycle: Optional[str] = None
    started_at: Optional[datetime] = None
    renews_at: Optional[datetime] = None
    is_active: bool
    cancelled_at: Optional[datetime] = None


class UpgradeRequest(BaseModel):
    tier: str = Field(..., description="'pro' or 'super_pro'")
    billing_cycle: str = Field(..., description="'monthly' or 'annual'")


@router.get("", response_model=SubscriptionResponse)
def get_subscription(user_id: int = Depends(require_auth)):
    """Returns the caller's current subscription, lazily creating a
    free-tier row on first access."""
    return SubscriptionResponse(**subscription_service.get_or_create_subscription(user_id))


@router.post("/upgrade", response_model=SubscriptionResponse)
def upgrade_subscription(req: UpgradeRequest, user_id: int = Depends(rate_limited_user("subscription"))):
    """MOCK upgrade — simulated for demo purposes. No real StoreKit
    purchase or payment processor call happens server-side, so it is a 404
    unless ALLOW_MOCK_PURCHASES=1 (dev/demo only; AUTH-14): otherwise any
    account could grant itself a paid tier."""
    if os.getenv("ALLOW_MOCK_PURCHASES") != "1":
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        result = subscription_service.mock_upgrade(user_id, tier=req.tier, billing_cycle=req.billing_cycle)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return SubscriptionResponse(**result)


@router.post("/cancel", response_model=SubscriptionResponse)
def cancel_subscription(user_id: int = Depends(rate_limited_user("subscription"))):
    """MOCK cancel — simulated for demo purposes. Tier stays until
    `renews_at`; see services/subscription_service.mock_cancel() for the
    "no cron reverts this" caveat."""
    result = subscription_service.mock_cancel(user_id)
    return SubscriptionResponse(**result)


@router.get("/entitlements", response_model=EntitlementsResponse)
def get_entitlements(user_id: int = Depends(require_auth)):
    """Returns the caller's effective tier and a feature_key -> bool map of
    server-side entitlements (see services/entitlement_service.py). The iOS
    paywall banner calls this to decide what to show/gate client-side."""
    return EntitlementsResponse(**entitlement_service.get_all_entitlements(user_id))
