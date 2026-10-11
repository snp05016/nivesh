"""FINSEC-18 / GH-665: device binding is server-decided and rejections are 409.

- The server, not the client, decides primacy: a successful bind makes the
  device the user's only primary device and demotes every other one.
- Re-binding the same device works on the create_all schema (conftest DB).
- Fraud-heuristic rejections return HTTP 409 with a structured detail.
- device_id longer than the String(120) column is rejected with 422.
"""
from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy import inspect


def _clear(user_ids) -> None:
    import database
    from models.db_models import DeviceBinding, DeviceBindingAttempt  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        for model in (DeviceBinding, DeviceBindingAttempt):
            session.query(model).filter(model.user_id.in_(user_ids)).delete(synchronize_session=False)
        session.commit()


@pytest.fixture
def clean_bindings(test_user_id):
    _clear([test_user_id])
    yield test_user_id
    _clear([test_user_id])


@pytest.fixture
def other_user():
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        user = User(username=f"_finsec18_{uuid.uuid4().hex[:10]}", password_hash="x", display_name="Other")
        session.add(user)
        session.commit()
        uid = cast(int, user.id)
    _clear([uid])
    yield uid
    _clear([uid])
    with database.get_session() as session:
        session.query(User).filter(User.id == uid).delete(synchronize_session=False)
        session.commit()


def _rows(user_id):
    import database
    from models.db_models import DeviceBinding, DeviceBindingAttempt  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        bindings = {
            b.device_id: bool(b.is_primary)
            for b in session.query(DeviceBinding).filter(DeviceBinding.user_id == user_id).all()
        }
        attempts = session.query(DeviceBindingAttempt).filter(DeviceBindingAttempt.user_id == user_id).count()
    return bindings, attempts


def test_rebind_same_device_twice_ok(client, auth_headers, clean_bindings):
    uid = clean_bindings
    for _ in range(2):
        resp = client.post("/api/kyc/device-binding", json={"device_id": "finsec18-dev-same"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_primary"] is True

    bindings, attempts = _rows(uid)
    assert bindings == {"finsec18-dev-same": True}
    assert attempts == 2


def test_client_cannot_bind_as_non_primary(client, auth_headers, clean_bindings):
    resp = client.post(
        "/api/kyc/device-binding",
        json={"device_id": "finsec18-dev-np", "is_primary": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_primary"] is True


def test_new_device_demotes_previous_primary(client, auth_headers, clean_bindings):
    uid = clean_bindings
    for dev in ("finsec18-dev-A", "finsec18-dev-B"):
        resp = client.post("/api/kyc/device-binding", json={"device_id": dev}, headers=auth_headers)
        assert resp.status_code == 200, resp.text

    bindings, _ = _rows(uid)
    assert bindings == {"finsec18-dev-A": False, "finsec18-dev-B": True}

    verify_a = client.get("/api/kyc/device-binding/verify", params={"device_id": "finsec18-dev-A"}, headers=auth_headers)
    verify_b = client.get("/api/kyc/device-binding/verify", params={"device_id": "finsec18-dev-B"}, headers=auth_headers)
    assert verify_a.status_code == 200 and verify_a.json()["verified"] is False
    assert verify_b.status_code == 200 and verify_b.json()["verified"] is True


def test_cross_user_rejection_returns_409(client, auth_headers, clean_bindings, other_user):
    from services.kyc_consent_service import bind_device

    assert bind_device(other_user, "finsec18-dev-shared")["is_primary"] is True

    resp = client.post("/api/kyc/device-binding", json={"device_id": "finsec18-dev-shared"}, headers=auth_headers)
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["bound"] is False
    assert detail["fraud_signal"] == "cross_user_device_reuse"
    assert detail["reason"]

    bindings, attempts = _rows(clean_bindings)
    assert bindings == {}
    assert attempts == 1

    # The rejection is still audited.
    import database
    from models.db_models import DeviceBindingAttempt  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        outcomes = [
            a.outcome
            for a in session.query(DeviceBindingAttempt).filter(DeviceBindingAttempt.user_id == clean_bindings)
        ]
    assert outcomes == ["rejected_cross_user"]


def test_rate_limit_returns_409(client, auth_headers, clean_bindings, monkeypatch):
    monkeypatch.setattr("services.kyc_consent_service.MAX_BIND_ATTEMPTS_PER_24H", 0)
    resp = client.post("/api/kyc/device-binding", json={"device_id": "gh665-dev-rl"}, headers=auth_headers)
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["fraud_signal"] == "rebind_rate_limit_exceeded"
    assert detail["reason"]


def test_device_id_too_long_422(client, auth_headers, clean_bindings):
    too_long = "x" * 121
    resp = client.post("/api/kyc/device-binding", json={"device_id": too_long}, headers=auth_headers)
    assert resp.status_code == 422
    resp = client.get("/api/kyc/device-binding/verify", params={"device_id": too_long}, headers=auth_headers)
    assert resp.status_code == 422
    assert _rows(clean_bindings) == ({}, 0)


def test_unique_constraint_on_device_bindings_in_db():
    import database

    insp = inspect(database.ENGINE)
    binding_uniques = [sorted(uc["column_names"]) for uc in insp.get_unique_constraints("device_bindings")]
    assert ["device_id", "user_id"] in binding_uniques
    assert insp.get_unique_constraints("device_binding_attempts") == []
