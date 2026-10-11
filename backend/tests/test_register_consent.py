"""REG-12: POST /register needs consent to the current Privacy Policy / Terms
version and an 18+ attestation, records both in the consent ledger, and the
served notices are real text (no demo copy) naming the AI processors.
"""
from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def register(client, monkeypatch):
    import routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_check_rate_limit", lambda *_args, **_kwargs: True)

    def _post(**overrides):
        from services.disclosure_service import CURRENT_POLICY_VERSION

        username = f"reg12_{uuid4().hex[:12]}"
        body = {
            "username": username,
            "password": "abcd1234",
            "display_name": "REG-12",
            "accepted_policy_version": CURRENT_POLICY_VERSION,
            "age_confirmed": True,
        }
        body.update(overrides)
        body = {k: v for k, v in body.items() if v is not None}
        return username, client.post("/register", json=body)

    return _post


def _user_exists(username: str) -> bool:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        return session.query(User).filter_by(username=username.lower()).first() is not None


def _active_consent_types(user_id: int) -> dict[str, str | None]:
    import database
    from models.db_models import KYCConsent  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        rows = session.query(KYCConsent).filter(
            KYCConsent.user_id == user_id,
            KYCConsent.granted.is_(True),
            KYCConsent.revoked_at.is_(None),
        ).all()
        return {str(r.consent_type): r.policy_version for r in rows}  # type: ignore[misc]


@pytest.mark.parametrize("missing", ["accepted_policy_version", "age_confirmed"])
def test_register_without_consent_fields_422(register, missing):
    username, resp = register(**{missing: None})

    assert resp.status_code == 422, resp.text
    assert not _user_exists(username)


def test_register_stale_policy_version_400(register):
    username, resp = register(accepted_policy_version="1999-01-01")

    assert resp.status_code == 400, resp.text
    assert "Privacy Policy" in resp.json()["detail"]
    assert not _user_exists(username)


def test_register_under_18_400(register):
    username, resp = register(age_confirmed=False)

    assert resp.status_code == 400, resp.text
    assert "18" in resp.json()["detail"]
    assert not _user_exists(username)


def test_register_records_notice_terms_and_age(register):
    from services.disclosure_service import CURRENT_POLICY_VERSION

    _, resp = register()

    assert resp.status_code == 200, resp.text
    consents = _active_consent_types(resp.json()["user_id"])
    assert consents == {
        "privacy_notice": CURRENT_POLICY_VERSION,
        "terms": CURRENT_POLICY_VERSION,
        "age_18_plus": CURRENT_POLICY_VERSION,
    }


def test_privacy_policy_is_real_notice(client):
    from services.disclosure_service import CURRENT_POLICY_VERSION

    resp = client.get("/api/v1/compliance/disclosures/privacy_policy")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "demo" not in body["title"].lower()
    assert "MOCK" not in body["body"]
    assert body["version"] == CURRENT_POLICY_VERSION
    text = " ".join([body["body"]] + [s["heading"] + " " + s["text"] for s in body["sections"]])
    # Every LLM processor llm_utils / copilot talk to must be named.
    for processor in ("DeepSeek", "Anthropic", "Apple Push Notification"):
        assert processor in text
    for topic in ("How long we keep it", "Your rights", "Grievance Officer"):
        assert topic in text
    assert "Data Protection Board" in text
    # iOS has no Delete Account control yet: deletion must route to the
    # Grievance Officer, not to a Settings screen that does not exist.
    rights = {s["heading"]: s["text"] for s in body["sections"]}
    for heading in ("How long we keep it", "Your rights"):
        assert "Grievance Officer" in rights[heading]
    assert "deletion (Settings" not in text


@pytest.mark.parametrize("key", ["terms_of_use", "grievance_officer"])
def test_terms_and_grievance_served(client, key):
    resp = client.get(f"/api/v1/compliance/disclosures/{key}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == key
    assert "demo" not in body["title"].lower()
    assert "MOCK" not in body["body"]
