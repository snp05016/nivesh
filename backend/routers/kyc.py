"""KYC consent + device-binding ("SIM-binding") API.

Controller-only: HTTP validation lives here, all DB access / business logic
lives in services/kyc_consent_service.py (Controller-Service-Repository).

MOCK DATA - simulated for demo purposes, not a real integration. There is no
real telecom SIM-swap-detection API and no real credit-bureau / government ID
verification anywhere behind this router — see kyc_consent_service.py for the
full disclosure and the KYC-gate invariant this endpoint set makes reachable.
"""
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from core.security import require_auth
from services.kyc_consent_service import (
    bind_device,
    get_active_consents,
    get_fraud_signals_for_user,
    record_consent,
    revoke_consent,
    verify_device_binding,
)

router = APIRouter(prefix="/api/kyc", tags=["KYC Consent"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RecordConsentRequest(BaseModel):
    consent_type: str = Field(..., min_length=1, max_length=50)
    granted: bool


class BindDeviceRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=200)
    is_primary: bool = True


# ---------------------------------------------------------------------------
# Consents
# ---------------------------------------------------------------------------

@router.post("/consents")
def create_consent(body: RecordConsentRequest, request: Request, user_id: int = Depends(require_auth)):
    ip_address = request.client.host if request.client else None
    return record_consent(user_id, body.consent_type, body.granted, ip_address=ip_address)


@router.delete("/consents/{consent_type}")
def delete_consent(consent_type: str, user_id: int = Depends(require_auth)):
    return revoke_consent(user_id, consent_type)


@router.get("/consents")
def list_consents(user_id: int = Depends(require_auth)):
    return get_active_consents(user_id)


# ---------------------------------------------------------------------------
# Device binding ("SIM-binding")
# ---------------------------------------------------------------------------

@router.post("/device-binding")
def create_device_binding(body: BindDeviceRequest, user_id: int = Depends(require_auth)):
    """Bind a device_id to the current user.

    On rejection (MOCK fraud-signal heuristics — see kyc_consent_service.py),
    the response body includes a "fraud_signal" field, e.g.
    "cross_user_device_reuse" or "rebind_rate_limit_exceeded", in addition to
    "bound": False and a human-readable "reason".
    """
    return bind_device(user_id, body.device_id, body.is_primary)


@router.get("/device-binding/verify")
def check_device_binding(device_id: str = Query(...), user_id: int = Depends(require_auth)):
    return verify_device_binding(user_id, device_id)


# ---------------------------------------------------------------------------
# Fraud signals (MOCK — see kyc_consent_service.get_fraud_signals_for_user)
# ---------------------------------------------------------------------------

@router.get("/fraud-signals")
def read_fraud_signals(user_id: int = Depends(require_auth)):
    """MOCK DATA - simulated for demo purposes, not a real integration.

    Summary of this user's device-binding fraud-signal audit trail
    (DeviceBindingAttempt), for an account-security screen or admin view.
    """
    return get_fraud_signals_for_user(user_id)
