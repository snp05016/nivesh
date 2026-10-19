"""Audit trail writer for money and identity actions (FINSEC-22).

audit() adds one AuditLogEntry to the caller's open session and never
commits, so the row lands atomically with the state change it records.
The request id and user agent come from CorrelationIDMiddleware's context
variables, and the IP defaults to the request's client address.

Only actions by a known user are audited: user_id is NOT NULL, so failed
logins for unknown usernames are not recorded here (auth_service logs them).
"""
import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from database import get_session
from models.db_models import AuditLogEntry
from services.error_telemetry import request_client_context_var, request_id_context_var


def audit(
    session,
    user_id: int,
    action: str,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLogEntry:
    # JSON column: datetimes/Decimals would make the commit raise (FINSEC-16).
    safe = json.loads(json.dumps(details or {}, default=str))
    client = request_client_context_var.get() or {}
    request_id = request_id_context_var.get()  # client-supplied X-Request-ID: cap before storing
    safe["_ctx"] = {"request_id": request_id[:64] if request_id else None, "user_agent": client.get("user_agent")}
    entry = AuditLogEntry(
        user_id=user_id,
        action=action,
        details=safe,
        created_at=datetime.now(timezone.utc),
        ip_address=ip_address or client.get("ip"),
    )
    session.add(entry)
    return entry


# ponytail: per-process throttle; correct for the single worker (FIX:REL-08); move to Redis if workers > 1
_throttle_lock = threading.Lock()
_last_written: dict[tuple, float] = {}
_THROTTLE_MAX_KEYS = 1000


def audit_now(user_id: int, action: str, details: Optional[dict] = None, *, min_interval_s: int = 0) -> None:
    """Write one audit row in its own transaction. Fails closed: an exception propagates, so a
    caller that audits before reading returns no data when the row cannot be written.

    With min_interval_s > 0, an identical (user_id, action, details) written by this process
    within that many seconds is skipped (the admin console polls some lists every 10 s).
    """
    key = (user_id, action, json.dumps(details, sort_keys=True, default=str))
    if min_interval_s > 0:
        with _throttle_lock:
            last = _last_written.get(key)
        if last is not None and time.monotonic() - last < min_interval_s:
            return
    with get_session() as session:
        audit(session, user_id, action, details)
        session.commit()
    if min_interval_s > 0:
        with _throttle_lock:
            if len(_last_written) > _THROTTLE_MAX_KEYS:
                _last_written.clear()
            _last_written[key] = time.monotonic()


def list_entries(action_prefix: Optional[str] = None, limit: int = 100, before_id: Optional[int] = None) -> list[dict]:
    """Newest audit rows first. The actor is the row's user_id; the target is in details."""
    limit = max(1, min(int(limit), 200))
    with get_session() as session:
        q = session.query(AuditLogEntry)
        if action_prefix:
            escaped = action_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            q = q.filter(AuditLogEntry.action.like(escaped + "%", escape="\\"))
        if before_id is not None:
            q = q.filter(AuditLogEntry.id < before_id)
        rows = q.order_by(AuditLogEntry.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "actor_user_id": r.user_id,
                "action": r.action,
                "details": r.details,
                "created_at": _iso(r.created_at),
                "ip_address": r.ip_address,
            }
            for r in rows
        ]


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"
