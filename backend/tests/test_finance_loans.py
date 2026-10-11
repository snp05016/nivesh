"""GH-662 / FINSEC-27: route-level regression coverage for /api/finance
(loan marketplace + finance tracker).

Each test uses a throwaway user and its own loan offer, so nothing depends on
test order, DEMO_MODE catalog seeding, or the shared session test user.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

_AUTH_ROUTES = [
    ("get", "/api/finance/credit-score"),
    ("get", "/api/finance/loan-applications"),
    ("post", "/api/finance/loan-applications"),
    ("get", "/api/finance/loan-applications/1"),
    ("post", "/api/finance/loan-applications/1/disburse"),
    ("get", "/api/finance/loan-applications/1/disbursement"),
    ("get", "/api/finance/linked-bank-accounts"),
    ("post", "/api/finance/linked-bank-accounts"),
    ("get", "/api/finance/accounts"),
    ("get", "/api/finance/summary"),
    ("get", "/api/finance/spend-categories"),
    ("post", "/api/finance/accounts/link-demo"),
]


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"loan_{uuid4().hex[:12]}", password_hash="x", display_name="Loan Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.fixture
def loan_offer():
    """An active personal-loan offer: 50,000 to 5,00,000, 6 to 60 months, min score 600."""
    import database
    from models.db_models import LoanOffer  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name=f"Test NBFC {uuid4().hex[:8]}",
            loan_type="personal",
            min_amount=50_000,
            max_amount=5_00_000,
            interest_rate_pct=12.0,
            min_tenure_months=6,
            max_tenure_months=60,
            min_credit_score=600,
            processing_fee_pct=1.0,
            is_active=True,
        )
        session.add(offer)
        session.commit()
        offer_id = int(offer.id)  # type: ignore[arg-type]
    yield offer_id
    with database.get_session() as session:
        row = session.get(LoanOffer, offer_id)
        if row is not None:
            session.delete(row)  # ORM cascade removes this offer's applications
            session.commit()


@pytest.fixture
def high_score(monkeypatch):
    """Pin the mock bureau score so demo underwriting would auto-approve."""
    import services.loan_marketplace_service as loan_service

    monkeypatch.setattr(loan_service, "get_mock_credit_score", lambda _user_id: 850)


def _apply(client, headers, offer_id, amount=1_00_000, tenure=24, device_id=None):
    payload = {
        "loan_offer_id": offer_id,
        "requested_amount": amount,
        "requested_tenure_months": tenure,
    }
    if device_id is not None:
        payload["device_id"] = device_id
    return client.post("/api/finance/loan-applications", json=payload, headers=headers)


@pytest.mark.parametrize("method, path", _AUTH_ROUTES)
def test_requires_auth(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401, resp.text


def test_loan_offers_public(client):
    assert client.get("/api/finance/loan-offers").status_code == 200


def test_credit_score_in_range(client):
    resp = client.get("/api/finance/credit-score", headers=_new_user_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["score_range_min"] <= body["credit_score"] <= body["score_range_max"]


def test_loan_kyc_gate_fails_closed(client, loan_offer, high_score):
    """No credit_check consent and no device binding: never auto-approved."""
    resp = _apply(client, _new_user_headers(), loan_offer)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert "KYC" in body["decision_reason"]


def test_loan_approved_with_consent_and_binding(client, loan_offer, high_score):
    headers = _new_user_headers()
    device_id = f"loan-dev-{uuid4().hex}"
    consent = client.post("/api/kyc/consents", json={"consent_type": "credit_check", "granted": True}, headers=headers)
    assert consent.status_code == 200, consent.text
    binding = client.post("/api/kyc/device-binding", json={"device_id": device_id}, headers=headers)
    assert binding.status_code == 200, binding.text

    resp = _apply(client, headers, loan_offer, device_id=device_id)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


@pytest.mark.parametrize("amount, tenure", [(6_00_000, 24), (1_00_000, 3)])
def test_loan_out_of_bounds_422(client, loan_offer, high_score, amount, tenure):
    resp = _apply(client, _new_user_headers(), loan_offer, amount=amount, tenure=tenure)
    assert resp.status_code == 422, resp.text


def test_unknown_offer_404(client):
    resp = _apply(client, _new_user_headers(), 987_654_321)
    assert resp.status_code == 404, resp.text
