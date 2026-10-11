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
  * bind_device()'s cross-user-device-reuse and rebind-rate-limit checks are
    genuine detection LOGIC over our own DeviceBinding/DeviceBindingAttempt
    tables, but they remain MOCK DATA heuristics — simulated for demo
    purposes, not a real telecom/SIM-swap-detection integration.

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
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from database import get_session
from models.db_models import DeviceBinding, DeviceBindingAttempt, KYCConsent
from services.disclosure_service import CONSENT_PURPOSES, CURRENT_POLICY_VERSION, notice_hash

CREDIT_CHECK_CONSENT = "credit_check"
# Opt-in (default off) consent to send a user's portfolio data to the LLM
# processors named in disclosure_service ("AI processors"). FINSEC-04.
AI_PROCESSING_CONSENT = "ai_processing"

# Rebind rate-limit heuristic — MOCK DATA, simulated for demo purposes, not a
# real integration. Models a "rapid device churn" fraud signal (SIM-swap
# fraud often involves rapid device changes): more than this many bind
# attempts (successful or rejected) by the same user_id within the trailing
# 24h window trips the rate limit.
MAX_BIND_ATTEMPTS_PER_24H = 5


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _consent_to_dict(consent: KYCConsent) -> dict:
    # ISO strings, not datetimes: the dict also lands in JSON audit columns
    # (compliance_service.withdraw_consent). The HTTP wire format is unchanged.
    return {
        "id": consent.id,
        "user_id": consent.user_id,
        "consent_type": consent.consent_type,
        "granted": consent.granted,
        "granted_at": _iso(consent.granted_at),
        "ip_address": consent.ip_address,
        "revoked_at": _iso(consent.revoked_at),
        "policy_version": consent.policy_version,
        "purpose": consent.purpose,
    }


def _revoke_active(session, user_id: int, consent_type: str, now: datetime) -> int:
    """Set revoked_at on EVERY active (granted, not-yet-revoked) row of
    consent_type for user_id and return how many rows were revoked. Repeated
    grants can leave several active rows, so revoking only the newest would
    keep the consent active. Caller commits.
    """
    return (
        session.query(KYCConsent)
        .filter(
            KYCConsent.user_id == user_id,
            KYCConsent.consent_type == consent_type,
            KYCConsent.granted.is_(True),
            KYCConsent.revoked_at.is_(None),
        )
        .update({KYCConsent.revoked_at: now}, synchronize_session=False)
    )


def record_consent(
    user_id: int,
    consent_type: str,
    granted: bool,
    ip_address: Optional[str] = None,
    policy_version: Optional[str] = None,
    app_version: Optional[str] = None,
) -> dict:
    """Persist a consent record.

    granted=True returns the existing active grant of consent_type when there
    is one (at most one active row per user + type, uq_kyc_consents_active),
    otherwise inserts a new row. granted=False is a withdrawal: it inserts a
    granted=False history row and revokes every active grant of consent_type
    in the same transaction, so the consent stops counting as active (KYC
    gates, GET /api/kyc/consents). Rows are never updated otherwise, so the
    grant/revoke history stays reconstructable.

    FINSEC-09: raises ValueError for a consent_type not in CONSENT_PURPOSES.
    Each row stores its purpose text, the policy_version the client showed
    (NULL when an older client sends none) and app_version. notice_hash is
    set only when policy_version is the current one, because only then do we
    know the exact text the user saw.
    """
    if consent_type not in CONSENT_PURPOSES:
        raise ValueError(f"unknown consent_type '{consent_type}'")
    # The disclaimer screen's not-advice notice is part of the Terms of Use.
    notice_key = "terms_of_use" if consent_type in ("terms", "disclaimer") else "privacy_policy"
    with get_session() as session:
        now = datetime.now(timezone.utc)
        if granted:
            active = _active_row(session, user_id, consent_type)
            if active is not None:
                if policy_version is None or active.policy_version == policy_version:  # pyright: ignore[reportGeneralTypeIssues]
                    return _consent_to_dict(active)
                # Re-consent to a different policy version (FINSEC-09): supersede
                # the old grant so the new version is recorded, still one active row.
                _revoke_active(session, user_id, consent_type, now)
        else:
            _revoke_active(session, user_id, consent_type, now)
        consent = KYCConsent(
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            granted_at=now,
            ip_address=ip_address,
            policy_version=policy_version,
            notice_hash=notice_hash(notice_key) if policy_version == CURRENT_POLICY_VERSION else None,
            purpose=CONSENT_PURPOSES[consent_type],
            app_version=app_version,
        )
        session.add(consent)
        try:
            session.commit()
        except IntegrityError:
            # A concurrent grant (double tap) won uq_kyc_consents_active.
            session.rollback()
            active = _active_row(session, user_id, consent_type) if granted else None
            if active is None:
                raise
            return _consent_to_dict(active)
        session.refresh(consent)
        return _consent_to_dict(consent)


def _active_row(session, user_id: int, consent_type: str) -> Optional[KYCConsent]:
    return (
        session.query(KYCConsent)
        .filter(
            KYCConsent.user_id == user_id,
            KYCConsent.consent_type == consent_type,
            KYCConsent.granted.is_(True),
            KYCConsent.revoked_at.is_(None),
        )
        .first()
    )


def revoke_consent(user_id: int, consent_type: str, session=None) -> dict:
    """Revoke every active (granted, not-yet-revoked) consent of consent_type
    for user_id. Sets revoked_at — never deletes rows, so the audit trail is
    preserved. Returns the newest revoked row plus revoked_count.

    With ``session`` the caller owns the transaction (no commit here), so it
    can write its audit row atomically with the revoke (compliance_service).
    """
    if session is None:
        with get_session() as own_session:
            result = _revoke(own_session, user_id, consent_type)
            own_session.commit()
            return result
    return _revoke(session, user_id, consent_type)


def _revoke(session, user_id: int, consent_type: str) -> dict:
    count = _revoke_active(session, user_id, consent_type, datetime.now(timezone.utc))
    if count == 0:
        return {
            "revoked": False,
            "revoked_count": 0,
            "consent_type": consent_type,
            "revoked_at": None,
            "reason": f"no active '{consent_type}' consent found for user {user_id}",
        }
    newest = (
        session.query(KYCConsent)
        .filter(
            KYCConsent.user_id == user_id,
            KYCConsent.consent_type == consent_type,
            KYCConsent.granted.is_(True),
        )
        .order_by(KYCConsent.granted_at.desc(), KYCConsent.id.desc())
        .first()
    )
    return {"revoked": True, "revoked_count": count, **_consent_to_dict(newest)}  # type: ignore[arg-type]


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


def has_active_consent(user_id: int, consent_type: str) -> bool:
    """True iff the user's newest consent_type row is granted and not revoked.

    Newest row wins, so a later POST with granted=false (what the iOS toggle
    sends) withdraws an earlier grant without needing DELETE.
    """
    with get_session() as session:
        latest = (
            session.query(KYCConsent)
            .filter(KYCConsent.user_id == user_id, KYCConsent.consent_type == consent_type)
            .order_by(KYCConsent.id.desc())
            .first()
        )
        return bool(latest and latest.granted and latest.revoked_at is None)


def has_active_credit_check_consent(user_id: int) -> bool:
    """Convenience helper for the loan-approval invariant: True iff the user
    has an active (granted, not revoked) "credit_check" consent.
    """
    return has_active_consent(user_id, CREDIT_CHECK_CONSENT)


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


def check_kyc_gate(user_id: int, device_id: Optional[str], consent_type: str, action: str) -> tuple[bool, str]:
    """Enforce the KYC/Security invariant above for any gated product:
    an active (granted, not revoked) consent_type consent must exist AND
    verify_device_binding(user_id, device_id)["verified"] must be True.
    Fails closed. `action` ("application", "booking") only labels the reason.

    Returns (passed, reason). MOCK DATA — device_id/consent checks are
    simulated for demo purposes, not a real KYC/SIM-binding integration.
    """
    active_consents = get_active_consents(user_id)
    if not any(c["consent_type"] == consent_type for c in active_consents):
        return False, f"no active '{consent_type}' KYC consent on file for this user (mock KYC gate)"

    if not device_id:
        return False, f"no device_id supplied with {action}; device binding could not be verified (mock KYC gate)"

    binding_result = verify_device_binding(user_id, device_id)
    if not binding_result["verified"]:
        return False, f"device binding check failed: {binding_result['reason']} (mock KYC gate)"

    return True, "KYC consent + device binding verified (mock KYC gate)"


def _log_bind_attempt(session, user_id: int, device_id: str, outcome: str, reason: Optional[str]) -> None:
    """MOCK DATA — simulated for demo purposes, not a real integration.

    Append-only audit row for every bind_device() call. Never updated or
    deleted, so the full attempt history (successful or rejected) remains
    inspectable for the fraud-signal heuristics below.
    """
    attempt = DeviceBindingAttempt(
        user_id=user_id,
        device_id=device_id,
        attempted_at=datetime.now(timezone.utc),
        outcome=outcome,
        reason=reason,
    )
    session.add(attempt)


def bind_device(user_id: int, device_id: str, is_primary: bool = True) -> dict:
    """MOCK DATA — register a device_id for user_id, simulating the initial
    SIM/device-binding step of KYC onboarding. Not a real telecom call.

    Adds two genuine (though still MOCK / demo-only) fraud-detection LOGIC
    checks on top of the plain existence check, both audited via
    DeviceBindingAttempt:

      1. Cross-user device reuse: if device_id is already bound as the
         PRIMARY device of a DIFFERENT user_id, this looks like someone
         reusing another person's already-registered primary device to try
         to KYC-bind a new account — the bind is rejected.
      2. Rebind rate limiting: if this user_id has made more than
         MAX_BIND_ATTEMPTS_PER_24H bind attempts (successful or rejected) in
         the trailing 24h, further attempts are rejected as a "rapid device
         churn" heuristic (SIM-swap fraud often involves rapid device
         changes).

    On rejection, returns {"bound": False, "reason": str, "fraud_signal": str}
    and does NOT create/update the DeviceBinding row. On success, returns the
    same shape as before ({"id", "user_id", "device_id", "bound_at",
    "is_primary"}) for backward compatibility with existing callers.

    The server decides primacy (FINSEC-18): a successful bind always makes
    this device the user's only primary device and demotes every other one
    in the same transaction. ``is_primary`` is accepted for signature
    compatibility but ignored.
    """
    with get_session() as session:
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        attempts_24h = (
            session.query(DeviceBindingAttempt)
            .filter(
                DeviceBindingAttempt.user_id == user_id,
                DeviceBindingAttempt.attempted_at >= window_start,
            )
            .count()
        )
        if attempts_24h >= MAX_BIND_ATTEMPTS_PER_24H:
            reason = (
                f"more than {MAX_BIND_ATTEMPTS_PER_24H} device bind attempts by "
                f"this user in the last 24h (mock rapid-device-churn check)"
            )
            _log_bind_attempt(session, user_id, device_id, "rejected_rate_limit", reason)
            session.commit()
            return {
                "bound": False,
                "reason": reason,
                "fraud_signal": "rebind_rate_limit_exceeded",
            }

        cross_user_primary = (
            session.query(DeviceBinding)
            .filter(
                DeviceBinding.device_id == device_id,
                DeviceBinding.is_primary.is_(True),
                DeviceBinding.user_id != user_id,
            )
            .first()
        )
        if cross_user_primary is not None:
            reason = (
                "device_id is already registered as the primary device of a "
                "different user (mock cross-user device reuse check)"
            )
            _log_bind_attempt(session, user_id, device_id, "rejected_cross_user", reason)
            session.commit()
            return {
                "bound": False,
                "reason": reason,
                "fraud_signal": "cross_user_device_reuse",
            }

        existing = (
            session.query(DeviceBinding)
            .filter(
                DeviceBinding.user_id == user_id,
                DeviceBinding.device_id == device_id,
            )
            .first()
        )
        session.query(DeviceBinding).filter(
            DeviceBinding.user_id == user_id,
            DeviceBinding.device_id != device_id,
            DeviceBinding.is_primary.is_(True),
        ).update({DeviceBinding.is_primary: False}, synchronize_session=False)
        if existing is not None:
            existing.is_primary = True
            binding = existing
        else:
            binding = DeviceBinding(
                user_id=user_id,
                device_id=device_id,
                bound_at=datetime.now(timezone.utc),
                is_primary=True,
            )
            session.add(binding)

        _log_bind_attempt(session, user_id, device_id, "bound", None)
        session.commit()
        session.refresh(binding)

        return {
            "id": binding.id,
            "user_id": binding.user_id,
            "device_id": binding.device_id,
            "bound_at": binding.bound_at,
            "is_primary": binding.is_primary,
        }


def get_fraud_signals_for_user(user_id: int) -> dict:
    """MOCK DATA — simulated for demo purposes, not a real integration.

    Summarizes the DeviceBindingAttempt audit trail for user_id into a
    fraud-signal snapshot suitable for an account-security screen or admin
    view. Not a real fraud-scoring model — just aggregate counts over the
    mock heuristics enforced in bind_device().
    """
    with get_session() as session:
        # Filter in SQL like bind_device(): attempted_at loads as a naive
        # datetime, so comparing it to this aware cutoff in Python raises.
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        base = session.query(DeviceBindingAttempt).filter(DeviceBindingAttempt.user_id == user_id)
        recent = base.filter(DeviceBindingAttempt.attempted_at >= window_start)

        total_bind_attempts_24h = recent.count()
        cross_user_rejections_total = base.filter(
            DeviceBindingAttempt.outcome == "rejected_cross_user"
        ).count()
        rate_limit_hits_24h = recent.filter(
            DeviceBindingAttempt.outcome == "rejected_rate_limit"
        ).count()
        is_flagged = base.filter(DeviceBindingAttempt.outcome != "bound").first() is not None

        return {
            "user_id": user_id,
            "total_bind_attempts_24h": total_bind_attempts_24h,
            "cross_user_rejections_total": cross_user_rejections_total,
            "rate_limit_hits_24h": rate_limit_hits_24h,
            "is_flagged": is_flagged,
        }
