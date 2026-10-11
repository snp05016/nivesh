"""Compliance service — India DPDP-Act-style right-to-erasure / consent-
withdrawal + audit trailing (demo-grade implementation).

Controller-Service-Repository: routers/compliance.py must only validate HTTP
input and call functions here. All session.query() calls for
AuditLogEntry / DataDeletionRequest live in this module.

DEMO-GRADE IMPLEMENTATION ONLY
-------------------------------
request_account_deletion() only creates/updates a DataDeletionRequest row in
a "pending" -> ... state machine. It does NOT delete, anonymise, or touch any
other row in the database. A real right-to-erasure pipeline would need a
background job (approvals, data export, cascading deletes/anonymisation
across every table referencing the user, notifying downstream processors,
etc.) which is explicitly out of scope for this demo.
"""
from datetime import datetime, timezone
from typing import Optional

from database import get_session
from models.db_models import AuditLogEntry, DataDeletionRequest

# Reuse the existing KYC consent revoke logic rather than duplicating it.
from services import kyc_consent_service


def _audit_to_dict(entry: AuditLogEntry) -> dict:
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "action": entry.action,
        "details": entry.details,
        "created_at": entry.created_at,
        "ip_address": entry.ip_address,
    }


def _deletion_request_to_dict(req: DataDeletionRequest) -> dict:
    return {
        "id": req.id,
        "user_id": req.user_id,
        "status": req.status,
        "requested_at": req.requested_at,
        "completed_at": req.completed_at,
        "reason": req.reason,
    }


def _log_action(
    session,
    user_id: int,
    action: str,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLogEntry:
    """Internal helper — must be called with an already-open session so the
    audit row is written atomically alongside the state change it records.
    """
    entry = AuditLogEntry(
        user_id=user_id,
        action=action,
        details=details or {},
        created_at=datetime.now(timezone.utc),
        ip_address=ip_address,
    )
    session.add(entry)
    return entry


def request_account_deletion(
    user_id: int,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """Create a DataDeletionRequest in "pending" status and log an
    AuditLogEntry.

    DEMO ONLY — this is a workflow/state-machine record. It does NOT
    actually delete any user data. No other table is touched by this call.
    """
    with get_session() as session:
        existing_pending = (
            session.query(DataDeletionRequest)
            .filter(
                DataDeletionRequest.user_id == user_id,
                DataDeletionRequest.status.in_(["pending", "processing"]),
            )
            .first()
        )
        if existing_pending is not None:
            return {
                "created": False,
                "reason": "an active deletion request already exists for this user",
                **_deletion_request_to_dict(existing_pending),
            }

        deletion_request = DataDeletionRequest(
            user_id=user_id,
            status="pending",
            requested_at=datetime.now(timezone.utc),
            reason=reason,
        )
        session.add(deletion_request)
        session.flush()  # assign deletion_request.id before logging

        _log_action(
            session,
            user_id=user_id,
            action="account_deletion_requested",
            details={"deletion_request_id": deletion_request.id, "reason": reason},
            ip_address=ip_address,
        )

        session.commit()
        session.refresh(deletion_request)
        return {"created": True, **_deletion_request_to_dict(deletion_request)}


def cancel_deletion_request(user_id: int, ip_address: Optional[str] = None) -> dict:
    """If a pending DataDeletionRequest exists for user_id, set its status to
    "cancelled" and log an AuditLogEntry.
    """
    with get_session() as session:
        deletion_request = (
            session.query(DataDeletionRequest)
            .filter(
                DataDeletionRequest.user_id == user_id,
                DataDeletionRequest.status == "pending",
            )
            .order_by(DataDeletionRequest.requested_at.desc())
            .first()
        )
        if deletion_request is None:
            return {
                "cancelled": False,
                "reason": f"no pending deletion request found for user {user_id}",
            }

        deletion_request.status = "cancelled"
        session.flush()

        _log_action(
            session,
            user_id=user_id,
            action="account_deletion_cancelled",
            details={"deletion_request_id": deletion_request.id},
            ip_address=ip_address,
        )

        session.commit()
        session.refresh(deletion_request)
        return {"cancelled": True, **_deletion_request_to_dict(deletion_request)}


def withdraw_consent(
    user_id: int,
    consent_type: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Withdraw (revoke) a KYC consent for user_id + consent_type, reusing
    kyc_consent_service's revoke logic rather than duplicating it, and log an
    AuditLogEntry in the same transaction. Nothing is logged when no active
    consent existed (revoked False), so the trail records real withdrawals only.
    """
    with get_session() as session:
        revoke_result = kyc_consent_service.revoke_consent_in_session(session, user_id, consent_type)
        if not revoke_result["revoked"]:
            return revoke_result

        _log_action(
            session,
            user_id=user_id,
            action="consent_withdrawn",
            details={
                "consent_type": consent_type,
                "consent_id": revoke_result["id"],
                "revoked_count": revoke_result["revoked_count"],
                "revoked_at": revoke_result["revoked_at"],
            },
            ip_address=ip_address,
        )
        session.commit()

    return revoke_result


def get_audit_trail(user_id: int, limit: int = 50) -> list[dict]:
    """Return the most recent AuditLogEntry rows for user_id, newest first."""
    with get_session() as session:
        entries = (
            session.query(AuditLogEntry)
            .filter(AuditLogEntry.user_id == user_id)
            .order_by(AuditLogEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_audit_to_dict(e) for e in entries]


def get_deletion_request_status(user_id: int) -> Optional[dict]:
    """Convenience helper: return the most recent DataDeletionRequest for
    user_id (or None), newest first.
    """
    with get_session() as session:
        deletion_request = (
            session.query(DataDeletionRequest)
            .filter(DataDeletionRequest.user_id == user_id)
            .order_by(DataDeletionRequest.requested_at.desc())
            .first()
        )
        if deletion_request is None:
            return None
        return _deletion_request_to_dict(deletion_request)
