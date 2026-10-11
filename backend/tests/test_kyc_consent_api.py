"""GH-662 / FINSEC-27: route-level regression coverage for /api/kyc.

Throwaway users keep every test under the 5-binds-per-24h fraud heuristic and
independent of the shared session test user. Consent withdrawal has its own
module (test_kyc_consent_withdrawal.py).
"""
from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    import config.settings

    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # GET /api/kyc/fraud-signals is demo-gated (FAKE-23)


_AUTH_ROUTES = [
    ("post", "/api/kyc/consents"),
    ("get", "/api/kyc/consents"),
    ("delete", "/api/kyc/consents/credit_check"),
    ("post", "/api/kyc/device-binding"),
    ("get", "/api/kyc/device-binding/verify?device_id=x"),
    ("get", "/api/kyc/fraud-signals"),
]


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"kyc_{uuid4().hex[:12]}", password_hash="x", display_name="KYC Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _bind(client, headers, device_id):
    return client.post("/api/kyc/device-binding", json={"device_id": device_id}, headers=headers)


@pytest.mark.parametrize("method, path", _AUTH_ROUTES)
def test_requires_auth(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401, resp.text


def test_granted_consent_is_listed_active(client):
    headers = _new_user_headers()
    resp = client.post("/api/kyc/consents", json={"consent_type": "data_sharing", "granted": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["granted"] is True

    listed = client.get("/api/kyc/consents", headers=headers)

    assert listed.status_code == 200, listed.text
    assert [c["consent_type"] for c in listed.json()] == ["data_sharing"]


def test_bind_same_device_twice(client):
    """GH-664: re-binding the same device must not raise IntegrityError (500)."""
    headers = _new_user_headers()
    device_id = f"kyc-dev-{uuid4().hex}"

    first = _bind(client, headers, device_id)
    second = _bind(client, headers, device_id)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    verify = client.get("/api/kyc/device-binding/verify", params={"device_id": device_id}, headers=headers)
    assert verify.json()["verified"] is True


def test_cross_user_device_reuse_rejected(client):
    device_id = f"kyc-dev-{uuid4().hex}"
    assert _bind(client, _new_user_headers(), device_id).status_code == 200

    other = _new_user_headers()
    resp = _bind(client, other, device_id)

    # GH-665 moves fraud rejections from 200 {"bound": false, ...} to
    # 409 {"detail": {"reason", "fraud_signal"}}; accept either contract.
    assert resp.status_code in (200, 409), resp.text
    body = resp.json()
    rejection = body["detail"] if resp.status_code == 409 else body
    if resp.status_code == 200:
        assert body["bound"] is False
    assert rejection["fraud_signal"] == "cross_user_device_reuse"
    verify = client.get("/api/kyc/device-binding/verify", params={"device_id": device_id}, headers=other)
    assert verify.json()["verified"] is False


def test_unbound_device_not_verified(client):
    resp = client.get(
        "/api/kyc/device-binding/verify",
        params={"device_id": f"kyc-dev-{uuid4().hex}"},
        headers=_new_user_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verified"] is False
