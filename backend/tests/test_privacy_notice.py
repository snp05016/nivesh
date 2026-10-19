"""I04 (trust-privacy-notice-be): the privacy notice and terms no longer describe
the demo loan/FD/KYC/device-binding processing, the policy version is bumped
without breaking sign-up for shipped builds, and GET /api/kyc/consent-purposes
lists only the consents a user can toggle.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

PURPOSES_URL = "/api/kyc/consent-purposes"
DISCLOSURE_URL = "/api/v1/compliance/disclosures/{}"
FORBIDDEN = ("loan", "lending", "fixed deposit", "device binding", "device id", "kyc")


def test_consent_purposes_requires_auth(client):
    assert client.get(PURPOSES_URL).status_code == 401


def test_consent_purposes_lists_user_toggles_only(client, auth_headers):
    from services.disclosure_service import CONSENT_PURPOSES, USER_CONSENTS

    resp = client.get(PURPOSES_URL, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    purposes = resp.json()["purposes"]
    types = [p["consent_type"] for p in purposes]
    assert "ai_processing" in types
    # Every registered user consent is listed, in USER_CONSENTS order.
    assert types == [k for k in USER_CONSENTS if k in CONSENT_PURPOSES]
    for hidden in ("privacy_notice", "terms", "disclaimer", "age_18_plus",
                   "credit_check", "sim_binding", "data_sharing"):
        assert hidden not in types
    for p in purposes:
        assert p["title"].strip()
        assert p["purpose"].strip()
        assert p["purpose"] == CONSENT_PURPOSES[p["consent_type"]]


@pytest.mark.parametrize("key", ["privacy_policy", "terms_of_use"])
def test_notice_has_no_demo_processing(client, key):
    from services.disclosure_service import CURRENT_POLICY_VERSION

    resp = client.get(DISCLOSURE_URL.format(key))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == CURRENT_POLICY_VERSION
    parts = [body["title"], body["body"]]
    for section in body["sections"]:
        parts += [section["heading"], section["text"]]
    text = " ".join(parts).lower()
    for word in FORBIDDEN:
        assert word not in text, f"{key} still mentions {word!r}"


@pytest.mark.parametrize("old_version", ["2026-10-11.1", "2026-10-01"])
def test_register_with_previous_policy_version_still_works(client, old_version):
    """Backward-compatibility case: shipped builds send their older
    PolicyVersion.current; sign-up succeeds and records that version."""
    import database
    from models.db_models import KYCConsent  # pyright: ignore[reportMissingImports]
    from services.auth_service import ACCEPTED_POLICY_VERSIONS
    from services.disclosure_service import CURRENT_POLICY_VERSION

    assert old_version != CURRENT_POLICY_VERSION
    assert old_version in ACCEPTED_POLICY_VERSIONS

    resp = client.post("/register", json={
        "username": f"i04_{uuid4().hex[:12]}",
        "password": "abcd1234",
        "display_name": "I04",
        "accepted_policy_version": old_version,
        "age_confirmed": True,
    })

    assert resp.status_code == 200, resp.text
    with database.get_session() as session:
        rows = session.query(KYCConsent).filter(
            KYCConsent.user_id == resp.json()["user_id"],
            KYCConsent.consent_type == "privacy_notice",
        ).all()
        assert [r.policy_version for r in rows] == [old_version]
        assert rows[0].notice_hash is None
