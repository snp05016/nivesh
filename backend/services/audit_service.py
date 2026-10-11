"""Audit trail writer for money and identity actions (FINSEC-22).

audit() adds one AuditLogEntry to the caller's open session and never
commits, so the row lands atomically with the state change it records.
The request id and user agent come from CorrelationIDMiddleware's context
variables, and the IP defaults to the request's client address.

Only actions by a known user are audited: user_id is NOT NULL, so failed
logins for unknown usernames are not recorded here (auth_service logs them).
"""
import json
from datetime import datetime, timezone
from typing import Optional

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
