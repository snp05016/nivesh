"""Compliance API — India DPDP-Act-style right-to-erasure / consent-
withdrawal + audit trailing. /api/v1/compliance/*.

Routers only validate HTTP input; all business logic + DB access lives in
services/compliance_service.py.

Deletion requests are executed by compliance_service.erase_user() (daily
job, after compliance_service.ERASURE_GRACE_DAYS); a pending request can be
cancelled until then.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional

from core.security import require_auth
from services import compliance_service, disclosure_service
from services.product_bounds import ProductBoundsError

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance"])

_VALID_DISCLOSURE_KEYS = (
    "privacy_policy",
    "terms_of_use",
    "grievance_officer",
    "data_sharing_governance",
    "digital_lending_compliance",
    "lending_service_provider",
    "apr_disclosure",
    "sim_binding_fraud_prevention",
)


class DeletionRequestBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class ConsentWithdrawBody(BaseModel):
    consent_type: str = Field(..., min_length=1, max_length=40)


class AuditLogEntryResponse(BaseModel):
    id: int
    user_id: int
    action: str
    details: Optional[dict] = None
    created_at: datetime
    ip_address: Optional[str] = None


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("/deletion-requests")
def request_account_deletion(
    body: DeletionRequestBody,
    request: Request,
    user_id: int = Depends(require_auth),
):
    """Create a pending account-deletion request; the user's data is erased
    once it is compliance_service.ERASURE_GRACE_DAYS old unless cancelled."""
    result = compliance_service.request_account_deletion(
        user_id, reason=body.reason, ip_address=_client_ip(request)
    )
    return result


@router.post("/deletion-requests/cancel")
def cancel_account_deletion(
    request: Request,
    user_id: int = Depends(require_auth),
):
    """Cancel the current pending account-deletion request, if any."""
    result = compliance_service.cancel_deletion_request(user_id, ip_address=_client_ip(request))
    if not result.get("cancelled"):
        raise HTTPException(status_code=404, detail=result.get("reason", "no pending deletion request"))
    return result


@router.get("/deletion-requests/status")
def get_deletion_status(user_id: int = Depends(require_auth)):
    """Return the most recent deletion request (if any) for the current user."""
    status = compliance_service.get_deletion_request_status(user_id)
    if status is None:
        return {"status": None}
    return status


@router.post("/consents/withdraw")
def withdraw_consent(
    body: ConsentWithdrawBody,
    request: Request,
    user_id: int = Depends(require_auth),
):
    """Withdraw a previously-granted KYC consent (e.g. "data_sharing",
    "credit_check", "sim_binding") and log the withdrawal to the audit trail.
    """
    result = compliance_service.withdraw_consent(
        user_id, body.consent_type, ip_address=_client_ip(request)
    )
    return result


@router.get("/audit-trail", response_model=list[AuditLogEntryResponse])
def get_audit_trail(limit: int = 50, user_id: int = Depends(require_auth)):
    """Return the current user's most recent compliance audit log entries,
    newest first."""
    capped_limit = max(1, min(limit, 200))
    return compliance_service.get_audit_trail(user_id, limit=capped_limit)


# ---------------------------------------------------------------------------
# Disclosure content — static, illustrative/demo compliance copy + a
# dynamically-computed Key Fact Statement (KFS) breakdown. Public/unauthed:
# these are informational disclosures, not user-account operations.
# ---------------------------------------------------------------------------

@router.get("/disclosures/{key}")
def get_disclosure_content(key: str):
    """Returns static, illustrative disclosure content for `key`
    (privacy_policy | terms_of_use | grievance_officer | data_sharing_governance | digital_lending_compliance |
    lending_service_provider | apr_disclosure | sim_binding_fraud_prevention).

    privacy_policy, terms_of_use and grievance_officer are the real (interim,
    pending legal review) notices; the lending/KFS keys are still clearly-
    labelled demo copy — see services/disclosure_service.py.
    """
    if key not in _VALID_DISCLOSURE_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown disclosure key '{key}'. Valid keys: {', '.join(_VALID_DISCLOSURE_KEYS)}",
        )
    content = disclosure_service.get_disclosure(key)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Unknown disclosure key '{key}'")
    return content


@router.get("/key-fact-statement")
def get_key_fact_statement(
    loan_offer_id: Optional[int] = None,
    scheme_id: Optional[int] = None,
    amount: Optional[float] = Query(None, gt=0, le=1e11),
    tenure_months: Optional[int] = Query(None, gt=0, le=1200),
):
    """Returns a structured Key Fact Statement (KFS) breakdown — loan_amount,
    interest_rate, all_fees, apr, tenure — computed dynamically from a real
    LoanOffer (loan_offer_id) or FixedDepositScheme (scheme_id).

    Exactly one of loan_offer_id / scheme_id is required. See
    services/disclosure_service.compute_key_fact_statement() and the
    'apr_disclosure' static disclosure for the APR formula used.
    """
    if (loan_offer_id is None) == (scheme_id is None):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of 'loan_offer_id' or 'scheme_id'",
        )
    try:
        kfs = disclosure_service.compute_key_fact_statement(
            loan_offer_id=loan_offer_id,
            scheme_id=scheme_id,
            amount=amount,
            tenure_months=tenure_months,
        )
    except ProductBoundsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if kfs is None:
        raise HTTPException(status_code=404, detail="Loan offer or FD scheme not found")
    return kfs
