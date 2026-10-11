"""My Account API — /api/me/*.

Thin, read-only-ish aggregation router: composes existing
services/subscription_service.py, services/kyc_consent_service.py, and
services/compliance_service.py so the iOS app can hit a single "my account"
surface. No new business logic lives here — this router is controller-only,
same as kyc.py/compliance.py/forum.py.

MOCK/demo caveats are inherited from the underlying services: subscription
state is not backed by a real payment processor (see subscription_service.py
/ routers/subscription.py), and account deletion only drives a
request/workflow state machine, not real irreversible data deletion (see
compliance_service.py / routers/compliance.py).
"""
from fastapi import APIRouter, Depends

from core.security import require_auth
from routers.subscription import SubscriptionResponse
from services import compliance_service, kyc_consent_service, subscription_service

router = APIRouter(prefix="/api/me", tags=["My Account"])


@router.get("/subscription", response_model=SubscriptionResponse)
def get_my_subscription(user_id: int = Depends(require_auth)):
    """Return the current user's subscription state."""
    return subscription_service.get_or_create_subscription(user_id)


@router.get("/consent")
def get_my_consents(user_id: int = Depends(require_auth)):
    """Return the current user's active KYC consents."""
    return kyc_consent_service.get_active_consents(user_id)


@router.delete("/account")
def delete_my_account(user_id: int = Depends(require_auth)):
    """Request deletion of the current user's account (DEMO — workflow
    state only, does NOT delete any data). If a deletion request is
    already pending, the underlying service reports that instead of
    creating a duplicate; either way the result dict is returned as-is."""
    return compliance_service.request_account_deletion(user_id, reason=None)
