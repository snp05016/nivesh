"""DB-10: consent withdrawal through /api/v1/compliance/consents/withdraw.

withdraw_consent used to commit the revoke, then write an audit row whose JSON
details held datetime objects: the commit raised (500) and the withdrawal was
left unaudited. Repeated grants also stacked several active rows.
"""
from __future__ import annotations

import json
from uuid import uuid4

# pyright: reportMissingImports=false


def _new_user() -> int:
    import database
    from models.db_models import User

    with database.get_session() as session:
        user = User(username=f"consent_{uuid4().hex[:12]}", password_hash="x", display_name="Consent Test")
        session.add(user)
        session.commit()
        return int(user.id)  # type: ignore[arg-type]


def _active(user_id: int, consent_type: str) -> int:
    from services.kyc_consent_service import get_active_consents

    return sum(1 for c in get_active_consents(user_id) if c["consent_type"] == consent_type)


def test_grant_twice_single_active():
    from services.kyc_consent_service import record_consent

    uid = _new_user()
    first = record_consent(uid, "credit_check", True)
    second = record_consent(uid, "credit_check", True)

    assert second["id"] == first["id"]
    assert _active(uid, "credit_check") == 1


def test_record_granted_false_revokes():
    from services.kyc_consent_service import has_active_consent, record_consent

    uid = _new_user()
    record_consent(uid, "data_sharing", True)
    record_consent(uid, "data_sharing", False)

    assert _active(uid, "data_sharing") == 0
    assert has_active_consent(uid, "data_sharing") is False


def test_consent_dict_json_safe():
    from services.kyc_consent_service import record_consent, revoke_consent

    uid = _new_user()
    granted = record_consent(uid, "sim_binding", True)
    revoked = revoke_consent(uid, "sim_binding")

    json.dumps(granted)
    json.dumps(revoked)
    assert isinstance(revoked["revoked_at"], str)


def test_withdraw_returns_200_and_audits(client):
    import database
    from models.db_models import AuditLogEntry
    from services.kyc_consent_service import record_consent

    uid = _new_user()
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}
    record_consent(uid, "credit_check", True)
    record_consent(uid, "credit_check", True)

    resp = client.post("/api/v1/compliance/consents/withdraw", json={"consent_type": "credit_check"}, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] is True
    assert _active(uid, "credit_check") == 0
    with database.get_session() as session:
        rows = session.query(AuditLogEntry).filter_by(user_id=uid, action="consent_withdrawn").all()
        assert len(rows) == 1
        details: dict = dict(rows[0].details)  # type: ignore[arg-type]
        assert details["consent_type"] == "credit_check"
        assert details["revoked_count"] == 1


def test_withdraw_without_active_consent_not_audited(client):
    # FINSEC-16: the trail records real withdrawals only.
    import database
    from models.db_models import AuditLogEntry

    uid = _new_user()
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}

    resp = client.post("/api/v1/compliance/consents/withdraw", json={"consent_type": "credit_check"}, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] is False
    with database.get_session() as session:
        assert session.query(AuditLogEntry).filter_by(user_id=uid, action="consent_withdrawn").count() == 0


def test_regrant_new_policy_version_supersedes():
    from services.disclosure_service import CURRENT_POLICY_VERSION
    from services.kyc_consent_service import get_active_consents, record_consent

    uid = _new_user()
    old = record_consent(uid, "data_sharing", True, policy_version="1999-01-01")
    new = record_consent(uid, "data_sharing", True, policy_version=CURRENT_POLICY_VERSION)

    assert new["id"] != old["id"]
    active = [c for c in get_active_consents(uid) if c["consent_type"] == "data_sharing"]
    assert [c["policy_version"] for c in active] == [CURRENT_POLICY_VERSION]
