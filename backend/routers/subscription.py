"""Subscription API — /api/v1/subscription (read-only).

Paid tiers come only from App Store verification (docs/billing/RUNBOOK.md); there is
no route that grants one.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

from core.security import require_auth
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


@router.get("", response_model=SubscriptionResponse)
def get_subscription(user_id: int = Depends(require_auth)):
    """Returns the caller's current subscription, lazily creating a
    free-tier row on first access."""
    return SubscriptionResponse(**subscription_service.get_or_create_subscription(user_id))


@router.get("/entitlements", response_model=EntitlementsResponse)
def get_entitlements(user_id: int = Depends(require_auth)):
    """Returns the caller's effective tier and a feature_key -> bool map of
    server-side entitlements (see services/entitlement_service.py). The iOS
    paywall banner calls this to decide what to show/gate client-side."""
    return EntitlementsResponse(**entitlement_service.get_all_entitlements(user_id))
