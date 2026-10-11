"""GH-662 / FINSEC-27: route-level regression coverage for /api/fixed-deposits.

Each test uses a throwaway user and its own FD scheme, so nothing depends on
test order, DEMO_MODE catalog seeding, or the shared session test user.
"""
from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    import config.settings

    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # /api/fixed-deposits is demo-gated (FAKE-23)


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"fd_{uuid4().hex[:12]}", password_hash="x", display_name="FD Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _make_scheme(is_active: bool = True) -> int:
    """A 7.00% scheme: 10,000 to 10,00,000, 6 to 60 months."""
    import database
    from models.db_models import FixedDepositScheme  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        scheme = FixedDepositScheme(
            issuer_name=f"Test Bank {uuid4().hex[:8]}",
            min_tenure_months=6,
            max_tenure_months=60,
            min_amount=10_000,
            max_amount=10_00_000,
            interest_rate_pct=7.0,
            senior_citizen_bonus_pct=0.5,
            is_active=is_active,
        )
        session.add(scheme)
        session.commit()
        return int(scheme.id)  # type: ignore[arg-type]


@pytest.fixture
def schemes():
    """Factory for test schemes; deletes them (and their bookings) afterwards."""
    import database
    from models.db_models import FixedDepositScheme  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    created: list[int] = []

    def _factory(is_active: bool = True) -> int:
        created.append(_make_scheme(is_active))
        return created[-1]

    yield _factory
    with database.get_session() as session:
        for scheme_id in created:
            row = session.get(FixedDepositScheme, scheme_id)
            if row is not None:
                session.delete(row)  # ORM cascade removes this scheme's bookings
        session.commit()


def _book(client, headers, scheme_id, principal=1_00_000, tenure=12, device_id=None):
    payload = {
        "scheme_id": scheme_id,
        "principal_amount": principal,
        "tenure_months": tenure,
        "payment_method": "upi",
    }
    if device_id is not None:
        payload["device_id"] = device_id
    return client.post("/api/fixed-deposits/bookings", json=payload, headers=headers)


def test_schemes_public(client):
    assert client.get("/api/fixed-deposits/schemes").status_code == 200


def test_calculator_public_quarterly_compounding(client):
    resp = client.post(
        "/api/fixed-deposits/calculator",
        json={"principal_amount": 1_00_000, "tenure_months": 12, "interest_rate_pct": 7.0},
    )
    assert resp.status_code == 200, resp.text
    # 1,00,000 * (1 + 0.07/4) ** 4
    assert resp.json()["maturity_amount"] == pytest.approx(107185.90, abs=0.01)


@pytest.mark.parametrize("method", ["get", "post"])
def test_bookings_require_auth(client, method):
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)("/api/fixed-deposits/bookings", **kwargs)
    assert resp.status_code == 401, resp.text


def test_booking_without_binding_fails_closed(client, schemes):
    resp = _book(client, _new_user_headers(), schemes(), device_id=f"fd-dev-{uuid4().hex}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "failed"
    assert "KYC" in body["decision_reason"]


def test_booking_confirmed_with_consent_and_binding(client, schemes):
    headers = _new_user_headers()
    device_id = f"fd-dev-{uuid4().hex}"
    consent = client.post("/api/kyc/consents", json={"consent_type": "sim_binding", "granted": True}, headers=headers)
    assert consent.status_code == 200, consent.text
    binding = client.post("/api/kyc/device-binding", json={"device_id": device_id}, headers=headers)
    assert binding.status_code == 200, binding.text

    resp = _book(client, headers, schemes(), device_id=device_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["maturity_amount"] > body["principal_amount"]
    listed = client.get("/api/fixed-deposits/bookings", headers=headers)
    assert [b["id"] for b in listed.json()] == [body["id"]]


@pytest.mark.parametrize("principal, tenure", [(5_000, 12), (20_00_000, 12), (1_00_000, 3), (1_00_000, 120)])
def test_booking_out_of_range_422(client, schemes, principal, tenure):
    resp = _book(client, _new_user_headers(), schemes(), principal=principal, tenure=tenure)
    assert resp.status_code == 422, resp.text


def test_booking_inactive_scheme_422(client, schemes):
    resp = _book(client, _new_user_headers(), schemes(is_active=False))
    assert resp.status_code == 422, resp.text


def test_booking_unknown_scheme_404(client):
    resp = _book(client, _new_user_headers(), 987_654_321)
    assert resp.status_code == 404, resp.text
