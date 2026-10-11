"""Compliance service — India DPDP-Act-style right-to-erasure / consent-
withdrawal + audit trailing.

Controller-Service-Repository: routers/compliance.py must only validate HTTP
input and call functions here. All session.query() calls for
AuditLogEntry / DataDeletionRequest live in this module.

Right to erasure (DB-06)
------------------------
request_account_deletion() records a "pending" DataDeletionRequest. After
ERASURE_GRACE_DAYS (during which cancel_deletion_request() still works) the
daily scheduler job process_due_deletion_requests() runs erase_user(), which
applies ERASURE_POLICY to every column referencing users.id in one
transaction, tombstones the users row and marks the request "completed".
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from database import get_session
from models.db_models import AuditLogEntry, Base, DataDeletionRequest, User

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
    AuditLogEntry. The data itself is erased later by
    process_due_deletion_requests() once ERASURE_GRACE_DAYS have passed.
    """
    def _existing(session) -> Optional[dict]:
        active = (
            session.query(DataDeletionRequest)
            .filter(
                DataDeletionRequest.user_id == user_id,
                DataDeletionRequest.status.in_(["pending", "processing"]),
            )
            .first()
        )
        if active is None:
            return None
        return {
            "created": False,
            "reason": "an active deletion request already exists for this user",
            **_deletion_request_to_dict(active),
        }

    with get_session() as session:
        existing = _existing(session)
        if existing is not None:
            return existing

        deletion_request = DataDeletionRequest(
            user_id=user_id,
            status="pending",
            requested_at=datetime.now(timezone.utc),
            reason=reason,
        )
        session.add(deletion_request)
        try:
            session.flush()  # assign deletion_request.id before logging
        except IntegrityError:
            # A concurrent request won the uq_data_deletion_active race.
            session.rollback()
            existing = _existing(session)
            if existing is None:
                raise
            return existing

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
    kyc_consent_service.revoke_consent() rather than duplicating the revoke
    logic, and log an AuditLogEntry in the same transaction, so a withdrawal is
    never left unaudited. Nothing is logged when no active consent existed
    (revoked False), so the trail records real withdrawals only.
    """
    with get_session() as session:
        revoke_result = kyc_consent_service.revoke_consent(user_id, consent_type, session=session)
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


# ---------------------------------------------------------------------------
# Right to erasure (DB-06)
# ---------------------------------------------------------------------------

ERASURE_GRACE_DAYS = 7

# Every "<table>.<column>" with a foreign key to users.id, and what erase_user()
# does with the user's rows there:
#   delete  — hard-delete the rows (user-owned personal / financial data)
#   nullify — keep the row, set the column to NULL (de-identified analytics)
#   retain  — keep the row attributed to the tombstoned user (legal / audit
#             evidence, community content); ip_address is cleared where present
# test_account_erasure.py fails when a new users.id FK is missing here.
ERASURE_POLICY: dict[str, str] = {
    "portfolio.user_id": "delete",
    "portfolio_groups.user_id": "delete",
    "portfolio_transactions.user_id": "delete",
    "multi_asset_transactions.user_id": "delete",
    "analysis_history.user_id": "nullify",
    "analysis_jobs.user_id": "nullify",
    "price_targets.user_id": "delete",
    "trade_journal.user_id": "delete",
    "dividend_ledger.user_id": "delete",
    "tax_reports.user_id": "delete",
    "device_tokens.user_id": "delete",
    "portfolio_valuation_history.user_id": "delete",
    "net_worth_ledger.user_id": "delete",
    "earnings_alerts.user_id": "delete",
    "user_preferences.user_id": "delete",
    "user_subscriptions.user_id": "delete",
    "in_app_notifications.user_id": "delete",
    "watchlists.user_id": "delete",
    "forum_threads.user_id": "retain",
    "forum_posts.user_id": "retain",
    "forum_votes.user_id": "retain",  # keeps the denormalised vote counters consistent
    "forum_reports.reporter_user_id": "retain",  # moderation record
    "user_blocks.blocker_user_id": "delete",
    "user_blocks.blocked_user_id": "retain",  # the blocker keeps hiding the retained posts
    "kyc_consents.user_id": "retain",  # consent evidence
    "device_bindings.user_id": "delete",
    "device_binding_attempts.user_id": "delete",
    "linked_bank_accounts.user_id": "delete",
    "loan_applications.user_id": "delete",
    "loan_disbursements.user_id": "delete",
    "finance_tracker_accounts.user_id": "delete",
    "audit_log_entries.user_id": "retain",
    "data_deletion_requests.user_id": "retain",
    "fixed_deposit_bookings.user_id": "delete",
}


def user_fk_columns() -> list:
    """(table, column) for every column with a foreign key to users.id, children
    before parents (reverse dependency order), so deletes never hit an FK."""
    return [
        (table, column)
        for table in reversed(Base.metadata.sorted_tables)
        for column in table.columns
        if any(fk.column.table.name == "users" for fk in column.foreign_keys)
    ]


def erase_user(user_id: int, request_id: Optional[int] = None) -> dict:
    """Erase user_id's personal data per ERASURE_POLICY in one transaction.

    The users row stays as a tombstone (retained rows keep a valid user_id):
    username/display_name are replaced, the password hash is randomised so
    nobody can log in, token_version is bumped and deleted_at is set. When
    request_id is given that DataDeletionRequest must still be pending or
    processing; it is marked "completed" in the same transaction (a request
    cancelled meanwhile aborts the erasure). Returns per-table row counts.

    Raises RuntimeError if a users.id FK has no ERASURE_POLICY entry (before
    touching anything) and LookupError if the user does not exist.
    """
    columns = user_fk_columns()
    missing = sorted(f"{t.name}.{c.name}" for t, c in columns if f"{t.name}.{c.name}" not in ERASURE_POLICY)
    if missing:
        raise RuntimeError(f"no ERASURE_POLICY entry for users.id foreign keys: {missing}")

    now = datetime.now(timezone.utc)
    counts: dict[str, int] = {}
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")

        if request_id is not None:
            claimed = (
                session.query(DataDeletionRequest)
                .filter(
                    DataDeletionRequest.id == request_id,
                    DataDeletionRequest.user_id == user_id,
                    DataDeletionRequest.status.in_(["pending", "processing"]),
                )
                .update(
                    {DataDeletionRequest.status: "completed", DataDeletionRequest.completed_at: now},
                    synchronize_session=False,
                )
            )
            if claimed != 1:
                raise LookupError(f"deletion request {request_id} is not pending for user {user_id}")

        for table, column in columns:
            policy = ERASURE_POLICY[f"{table.name}.{column.name}"]
            match = column == user_id
            if policy == "delete":
                result = session.execute(table.delete().where(match))
            elif policy == "nullify":
                result = session.execute(table.update().where(match).values({column.name: None}))
            elif "ip_address" in table.c:
                result = session.execute(table.update().where(match).values(ip_address=None))
            else:
                continue
            counts[table.name] = counts.get(table.name, 0) + (result.rowcount or 0)  # type: ignore[attr-defined]

        # Random suffix: a real account could already be named deleted_<id>.
        user.username = f"deleted_{user_id}_{secrets.token_hex(4)}"  # type: ignore[assignment]
        user.display_name = "Deleted user"  # type: ignore[assignment]
        user.password_hash = secrets.token_hex(32)  # type: ignore[assignment]
        user.token_version = (user.token_version or 0) + 1  # type: ignore[assignment]
        user.deleted_at = now  # type: ignore[assignment]

        _log_action(
            session,
            user_id=user_id,
            action="account_erased",
            details={"deletion_request_id": request_id, "tables": counts},
        )
        session.commit()

    return {"erased": True, "user_id": user_id, "deletion_request_id": request_id, "tables": counts}


def process_due_deletion_requests(grace_days: int = ERASURE_GRACE_DAYS) -> int:
    """Erase every user whose "pending" request is older than grace_days.

    Run daily by the scheduler (services/harvest_worker.py). Each request is
    erased in its own transaction; a failure is logged and the request stays
    pending for the next run. Returns how many requests were completed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=grace_days)
    with get_session() as session:
        due = [
            (int(r.id), int(r.user_id))  # type: ignore[arg-type]
            for r in session.query(DataDeletionRequest)
            .filter(
                DataDeletionRequest.status == "pending",
                DataDeletionRequest.requested_at <= cutoff,
            )
            .order_by(DataDeletionRequest.id.asc())
            .all()
        ]

    completed = 0
    for request_id, user_id in due:
        try:
            erase_user(user_id, request_id=request_id)
            completed += 1
        except Exception:
            logging.exception("[erasure] deletion request %s (user %s) failed", request_id, user_id)
    return completed
