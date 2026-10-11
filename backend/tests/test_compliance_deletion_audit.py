"""WIP-05: both deletion-request routes record the client IP on the audit entry.

DELETE /api/me/account used to call request_account_deletion() without
ip_address, so its AuditLogEntry had a NULL ip_address while
POST /api/v1/compliance/deletion-requests recorded it. Each test uses a
throwaway user so deletion state never leaks into the shared test user.
"""
from __future__ import annotations

from uuid import uuid4


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"del_{uuid4().hex[:12]}", password_hash="x", display_name="Deletion Audit Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _deletion_audit_entry(user_id: int) -> tuple[str | None, dict]:
    import database
    from models.db_models import AuditLogEntry  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        entry = (
            session.query(AuditLogEntry)
            .filter(AuditLogEntry.user_id == user_id, AuditLogEntry.action == "account_deletion_requested")
            .one()
        )
        return entry.ip_address, entry.details  # type: ignore[return-value]  (Column attributes are plain values on instances)


def test_compliance_deletion_request_audit_has_ip_and_reason(client):
    user_id, headers = _new_user()

    resp = client.post("/api/v1/compliance/deletion-requests", json={"reason": "test"}, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] is True
    ip_address, details = _deletion_audit_entry(user_id)
    assert ip_address == "testclient"
    assert details["reason"] == "test"
    assert client.post("/api/v1/compliance/deletion-requests/cancel", headers=headers).status_code == 200


def test_me_account_deletion_audit_has_ip(client):
    user_id, headers = _new_user()

    resp = client.delete("/api/me/account", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] is True
    ip_address, _ = _deletion_audit_entry(user_id)
    assert ip_address == "testclient"
    assert client.post("/api/v1/compliance/deletion-requests/cancel", headers=headers).status_code == 200
