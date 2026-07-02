"""Compliance API — India DPDP-Act-style right-to-erasure / consent-
withdrawal + audit trailing. /api/v1/compliance/*.

Routers only validate HTTP input; all business logic + DB access lives in
services/compliance_service.py.

DEMO-GRADE: the deletion-request endpoints only drive a request/workflow
state machine (DataDeletionRequest.status). No real, irreversible data
deletion is performed anywhere in this router or its service.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from core.security import require_auth
from services import compliance_service

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance"])


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
    """Create a pending account-deletion request (DEMO — workflow state
    only, does NOT delete any data)."""
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
