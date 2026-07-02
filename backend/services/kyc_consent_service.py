"""KYC consent-management + device-consent ("SIM-binding") service for the
loan marketplace.

Controller-Service-Repository: routers must only validate HTTP input and
call functions here. All session.query() calls for KYCConsent /
DeviceBinding live in this module.

MOCK / DEMO IMPLEMENTATION ONLY
--------------------------------
Every check in this file is simulated for a portfolio/demo build:
  * There is no real telecom SIM-swap-detection API call. verify_device_binding()
    is a MOCK DATA check — simulated for demo purposes, not a real integration —
    that simply compares a submitted device_id against rows we stored ourselves.
  * There is no real credit-bureau / NBFC integration and no real government ID
    is collected or stored anywhere in this module.

INVARIANT (must be enforced by the loan marketplace's application-approval
logic, e.g. services/loan_marketplace_service.py):

    A loan application MUST NOT be approved unless BOTH of the following hold
    for the applicant:
      1. get_active_consents(user_id) contains a consent with
         consent_type == "credit_check" (granted, not revoked), AND
      2. verify_device_binding(user_id, device_id)["verified"] is True.

    This service does not itself enforce the invariant on the approval
    endpoint — it only provides the primitives above. The service/router
    that actually flips a loan application to "approved" must call both
    checks before approving.
"""
from datetime import datetime, timezone
from typing import Optional

from database import get_session
from models.db_models import DeviceBinding, KYCConsent

CREDIT_CHECK_CONSENT = "credit_check"


def _consent_to_dict(consent: KYCConsent) -> dict:
    return {
        "id": consent.id,
        "user_id": consent.user_id,
        "consent_type": consent.consent_type,
        "granted": consent.granted,
        "granted_at": consent.granted_at,
        "ip_address": consent.ip_address,
        "revoked_at": consent.revoked_at,
    }


def record_consent(
    user_id: int,
    consent_type: str,
    granted: bool,
    ip_address: Optional[str] = None,
) -> dict:
    """Persist a new consent record.

    Each call inserts a new row (audit trail) rather than updating an
    existing one, so the full grant/revoke history for a user + consent_type
    is always reconstructable.
    """
    with get_session() as session:
        consent = KYCConsent(
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            granted_at=datetime.now(timezone.utc),
            ip_address=ip_address,
        )
        session.add(consent)
        session.commit()
        session.refresh(consent)
        return _consent_to_dict(consent)


def revoke_consent(user_id: int, consent_type: str) -> dict:
    """Revoke the most recent active (granted, not-yet-revoked) consent of
    consent_type for user_id. Sets revoked_at — never deletes the row, so the
    audit trail is preserved.
    """
    with get_session() as session:
        consent = (
            session.query(KYCConsent)
            .filter(
                KYCConsent.user_id == user_id,
                KYCConsent.consent_type == consent_type,
                KYCConsent.granted.is_(True),
                KYCConsent.revoked_at.is_(None),
            )
            .order_by(KYCConsent.granted_at.desc())
            .first()
        )
        if consent is None:
            return {
                "revoked": False,
                "reason": f"no active '{consent_type}' consent found for user {user_id}",
            }

        consent.revoked_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(consent)
        return {"revoked": True, **_consent_to_dict(consent)}


def get_active_consents(user_id: int) -> list[dict]:
    """Return all consents that are granted and not revoked for user_id."""
    with get_session() as session:
        consents = (
            session.query(KYCConsent)
            .filter(
                KYCConsent.user_id == user_id,
                KYCConsent.granted.is_(True),
                KYCConsent.revoked_at.is_(None),
            )
            .order_by(KYCConsent.granted_at.desc())
            .all()
        )
        return [_consent_to_dict(c) for c in consents]


def has_active_credit_check_consent(user_id: int) -> bool:
    """Convenience helper for the loan-approval invariant: True iff the user
    has an active (granted, not revoked) "credit_check" consent.
    """
    return any(
        c["consent_type"] == CREDIT_CHECK_CONSENT for c in get_active_consents(user_id)
    )


def verify_device_binding(user_id: int, device_id: str) -> dict:
    """MOCK "SIM-binding" style device-consent check.

    SIMULATED FOR DEMO PURPOSES — this is NOT a real telecom SIM-swap-
    detection API. It only compares the submitted device_id against
    DeviceBinding rows this app itself created (e.g. at signup / device
    registration time). A real implementation would call a telecom/NBFC
    partner API to confirm the SIM/device pairing hasn't changed.

    Returns {"verified": bool, "reason": str}.
    """
    with get_session() as session:
        bindings = (
            session.query(DeviceBinding)
            .filter(DeviceBinding.user_id == user_id)
            .all()
        )

        if not bindings:
            return {
                "verified": False,
                "reason": "no device binding on file for this user (mock check)",
            }

        match = next((b for b in bindings if b.device_id == device_id), None)
        if match is None:
            return {
                "verified": False,
                "reason": "submitted device_id does not match any bound device (mock check)",
            }

        if not match.is_primary:
            return {
                "verified": False,
                "reason": "matched device is not the registered primary device (mock check)",
            }

        return {
            "verified": True,
            "reason": "device_id matches registered primary device (mock check)",
        }


def bind_device(user_id: int, device_id: str, is_primary: bool = True) -> dict:
    """MOCK DATA — register a device_id for user_id, simulating the initial
    SIM/device-binding step of KYC onboarding. Not a real telecom call.
    """
    with get_session() as session:
        existing = (
            session.query(DeviceBinding)
            .filter(
                DeviceBinding.user_id == user_id,
                DeviceBinding.device_id == device_id,
            )
            .first()
        )
        if existing is not None:
            existing.is_primary = is_primary
            session.commit()
            session.refresh(existing)
            binding = existing
        else:
            binding = DeviceBinding(
                user_id=user_id,
                device_id=device_id,
                bound_at=datetime.now(timezone.utc),
                is_primary=is_primary,
            )
            session.add(binding)
            session.commit()
            session.refresh(binding)

        return {
            "id": binding.id,
            "user_id": binding.user_id,
            "device_id": binding.device_id,
            "bound_at": binding.bound_at,
            "is_primary": binding.is_primary,
        }
