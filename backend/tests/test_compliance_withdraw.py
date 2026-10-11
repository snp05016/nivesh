"""FINSEC-16: POST /api/v1/compliance/consents/withdraw.

withdraw_consent committed the revoke, then wrote datetime objects into the
JSON audit column in a second session, so every real withdrawal returned 500
and lost its audit row, while a no-op withdrawal logged 'consent_withdrawn'.
"""
from __future__ import annotations

import json

import pytest

import database
from models.db_models import AuditLogEntry, KYCConsent  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

_WITHDRAW = "/api/v1/compliance/consents/withdraw"


def _clear(user_id: int) -> None:
    with database.get_session() as session:
        session.query(KYCConsent).filter(KYCConsent.user_id == user_id).delete()
        session.query(AuditLogEntry).filter(
            AuditLogEntry.user_id == user_id, AuditLogEntry.action == "consent_withdrawn"
        ).delete()
        session.commit()


@pytest.fixture
def uid(test_user_id):
    _clear(test_user_id)
    yield test_user_id
    _clear(test_user_id)


def _withdrawn_rows(user_id: int) -> list:
    with database.get_session() as session:
        return session.query(AuditLogEntry).filter(
            AuditLogEntry.user_id == user_id, AuditLogEntry.action == "consent_withdrawn"
        ).all()


def _grant(client, auth_headers, consent_type: str) -> None:
    resp = client.post("/api/kyc/consents", json={"consent_type": consent_type, "granted": True}, headers=auth_headers)
    assert resp.status_code == 200, resp.text


def test_withdraw_returns_200_and_single_audit_row(client, auth_headers, uid):
    _grant(client, auth_headers, "credit_check")

    resp = client.post(_WITHDRAW, json={"consent_type": "credit_check"}, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] is True
    rows = _withdrawn_rows(uid)
    assert len(rows) == 1
    json.dumps(rows[0].details)
    assert rows[0].details["consent_type"] == "credit_check"
    listed = client.get("/api/kyc/consents", headers=auth_headers).json()
    assert "credit_check" not in {c["consent_type"] for c in listed}


def test_second_withdraw_is_noop_without_audit(client, auth_headers, uid):
    _grant(client, auth_headers, "credit_check")
    assert client.post(_WITHDRAW, json={"consent_type": "credit_check"}, headers=auth_headers).status_code == 200

    resp = client.post(_WITHDRAW, json={"consent_type": "credit_check"}, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] is False
    assert len(_withdrawn_rows(uid)) == 1


def test_withdraw_revokes_duplicate_active_rows(client, auth_headers, uid):
    _grant(client, auth_headers, "data_sharing")
    _grant(client, auth_headers, "data_sharing")

    resp = client.post(_WITHDRAW, json={"consent_type": "data_sharing"}, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    with database.get_session() as session:
        rows = session.query(KYCConsent).filter(
            KYCConsent.user_id == uid, KYCConsent.consent_type == "data_sharing"
        ).all()
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)
