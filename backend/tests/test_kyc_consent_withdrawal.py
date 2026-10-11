"""WIP-02 / FINSEC-08: withdrawing a KYC consent must revoke it.

The iOS toggle withdraws via POST /api/kyc/consents {granted: false}; that
used to append a granted=False row only, leaving earlier grants active (loan
and FD KYC gates stayed open). revoke_consent also revoked only the newest
active row, so a repeated grant survived a DELETE.
"""
from __future__ import annotations

import pytest


def _clear_consents(user_id: int) -> None:
    import database
    from models.db_models import KYCConsent  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        session.query(KYCConsent).filter(KYCConsent.user_id == user_id).delete()
        session.commit()


@pytest.fixture
def clean_consents(test_user_id):
    _clear_consents(test_user_id)
    yield test_user_id
    _clear_consents(test_user_id)


def _active_types(user_id: int) -> set[str]:
    from services.kyc_consent_service import get_active_consents

    return {c["consent_type"] for c in get_active_consents(user_id)}


def test_withdraw_via_record_consent_revokes(clean_consents):
    from services.kyc_consent_service import has_active_credit_check_consent, record_consent

    uid = clean_consents
    record_consent(uid, "credit_check", True)
    record_consent(uid, "credit_check", True)  # two active rows
    record_consent(uid, "data_sharing", True)
    assert has_active_credit_check_consent(uid) is True

    row = record_consent(uid, "credit_check", False)

    assert row["granted"] is False
    assert "credit_check" not in _active_types(uid)
    assert has_active_credit_check_consent(uid) is False
    assert "data_sharing" in _active_types(uid)  # other types untouched


def test_revoke_consent_revokes_all_rows(clean_consents):
    from services.kyc_consent_service import record_consent, revoke_consent

    uid = clean_consents
    record_consent(uid, "data_sharing", True)
    record_consent(uid, "data_sharing", True)

    result = revoke_consent(uid, "data_sharing")

    assert result["revoked"] is True
    assert result["revoked_count"] == 2
    assert result["consent_type"] == "data_sharing"
    assert result["revoked_at"] is not None
    assert "data_sharing" not in _active_types(uid)
    assert revoke_consent(uid, "data_sharing")["revoked"] is False


def test_api_toggle_off(client, auth_headers, clean_consents):
    resp = client.post("/api/kyc/consents", json={"consent_type": "sim_binding", "granted": True}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    listed = client.get("/api/kyc/consents", headers=auth_headers).json()
    assert "sim_binding" in {c["consent_type"] for c in listed}

    resp = client.post("/api/kyc/consents", json={"consent_type": "sim_binding", "granted": False}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"id", "consent_type", "granted", "revoked_at"} <= body.keys()
    assert body["granted"] is False

    listed = client.get("/api/kyc/consents", headers=auth_headers).json()
    assert "sim_binding" not in {c["consent_type"] for c in listed}
