"""FINSEC-09: consent rows record what the user agreed to (policy version,
purpose, notice hash, app version), registration records the privacy notice
server-side, and the Terms of Use disclosure is served.

Throwaway users keep these tests independent of the shared session test user.
"""
from __future__ import annotations

from uuid import uuid4


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"consent_{uuid4().hex[:12]}", password_hash="x", display_name="Consent Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _rows(user_id: int, consent_type: str) -> list[dict]:
    import database
    from models.db_models import KYCConsent  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        rows = (
            session.query(KYCConsent)
            .filter(KYCConsent.user_id == user_id, KYCConsent.consent_type == consent_type)
            .order_by(KYCConsent.id)
            .all()
        )
        return [
            {
                "policy_version": r.policy_version,
                "purpose": r.purpose,
                "notice_hash": r.notice_hash,
                "app_version": r.app_version,
            }
            for r in rows
        ]


def test_consent_persists_version_purpose_hash(client):
    from services.disclosure_service import CURRENT_POLICY_VERSION, notice_hash

    user_id, headers = _new_user()
    resp = client.post(
        "/api/kyc/consents",
        json={"consent_type": "credit_check", "granted": True, "policy_version": CURRENT_POLICY_VERSION},
        headers={**headers, "X-App-Version": "2.0"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["policy_version"] == CURRENT_POLICY_VERSION
    [row] = _rows(user_id, "credit_check")
    assert row["policy_version"] == CURRENT_POLICY_VERSION
    assert row["purpose"]
    assert row["notice_hash"] == notice_hash("privacy_policy")
    assert len(row["notice_hash"]) == 64
    assert row["app_version"] == "2.0"


def test_unknown_consent_type_422(client):
    user_id, headers = _new_user()
    resp = client.post(
        "/api/kyc/consents",
        json={"consent_type": "anything_goes", "granted": True},
        headers=headers,
    )

    assert resp.status_code == 422, resp.text
    assert _rows(user_id, "anything_goes") == []


def test_missing_policy_version_stored_null(client):
    """Shipped clients send no policy_version: still accepted, stored as unknown."""
    user_id, headers = _new_user()
    resp = client.post("/api/kyc/consents", json={"consent_type": "data_sharing", "granted": True}, headers=headers)

    assert resp.status_code == 200, resp.text
    [row] = _rows(user_id, "data_sharing")
    assert row["policy_version"] is None
    assert row["notice_hash"] is None
    assert row["purpose"]


def test_stale_policy_version_has_no_notice_hash(client):
    user_id, headers = _new_user()
    resp = client.post(
        "/api/kyc/consents",
        json={"consent_type": "sim_binding", "granted": True, "policy_version": "1999-01-01"},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    [row] = _rows(user_id, "sim_binding")
    assert row["policy_version"] == "1999-01-01"
    assert row["notice_hash"] is None


def test_register_records_privacy_notice(client, monkeypatch):
    import database
    import routers.auth as auth_router
    from models.db_models import User  # pyright: ignore[reportMissingImports]
    from services.disclosure_service import CURRENT_POLICY_VERSION, notice_hash

    monkeypatch.setattr(auth_router, "_check_rate_limit", lambda *_args, **_kwargs: True)
    username = f"consentreg_{uuid4().hex[:12]}"
    resp = client.post(
        "/register",
        json={
            "username": username,
            "password": "abcd1234",
            "display_name": "Consent Register",
            "accepted_policy_version": CURRENT_POLICY_VERSION,
        },
    )

    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user_id"]
    with database.get_session() as session:
        assert session.query(User).filter_by(id=user_id).first() is not None
    [privacy] = _rows(user_id, "privacy_notice")
    assert privacy["policy_version"] == CURRENT_POLICY_VERSION
    assert privacy["notice_hash"] == notice_hash("privacy_policy")
    [terms] = _rows(user_id, "terms")
    assert terms["notice_hash"] == notice_hash("terms_of_use")


def test_register_without_policy_version_records_nothing(client, monkeypatch):
    import routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_check_rate_limit", lambda *_args, **_kwargs: True)
    resp = client.post(
        "/register",
        json={"username": f"consentold_{uuid4().hex[:12]}", "password": "abcd1234", "display_name": "Old Client"},
    )

    assert resp.status_code == 200, resp.text
    assert _rows(resp.json()["user_id"], "privacy_notice") == []


def test_terms_disclosure_served(client):
    from services.disclosure_service import CURRENT_POLICY_VERSION

    resp = client.get("/api/v1/compliance/disclosures/terms_of_use")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "terms_of_use"
    assert body["version"] == CURRENT_POLICY_VERSION
