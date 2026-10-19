"""FINSEC-22: money and identity actions each write one audit_log_entries row
carrying the user, the client IP and the request id of the call that made it."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

import pytest

import config.settings
import database
from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    AuditLogEntry,
    FixedDepositScheme,
    LoanApplication,
    LoanDisbursement,
    LoanOffer,
    User,
)


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # /api/finance and FD routes are demo-gated


def _new_user() -> int:
    with database.get_session() as session:
        user = User(username=f"audit_{uuid4().hex[:12]}", password_hash="x", display_name="Audit Test")
        session.add(user)
        session.commit()
        return int(user.id)  # type: ignore[arg-type]


def _rows(user_id: int) -> list:
    with database.get_session() as session:
        return session.query(AuditLogEntry).filter(AuditLogEntry.user_id == user_id).all()


@pytest.fixture
def products():
    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name=f"Audit NBFC {uuid4().hex[:8]}", loan_type="personal", min_amount=50_000,
            max_amount=5_00_000, interest_rate_pct=12.0, min_tenure_months=6, max_tenure_months=60,
            min_credit_score=600, processing_fee_pct=1.0, is_active=True,
        )
        scheme = FixedDepositScheme(
            issuer_name=f"Audit Bank {uuid4().hex[:8]}", min_tenure_months=6, max_tenure_months=60,
            min_amount=10_000, max_amount=10_00_000, interest_rate_pct=7.0,
            senior_citizen_bonus_pct=0.5, is_active=True,
        )
        session.add_all([offer, scheme])
        session.commit()
        ids = (int(offer.id), int(scheme.id))  # type: ignore[arg-type]
    yield ids
    with database.get_session() as session:
        app_ids = [a.id for a in session.query(LoanApplication.id).filter(LoanApplication.loan_offer_id == ids[0])]
        if app_ids:
            session.query(LoanDisbursement).filter(LoanDisbursement.loan_application_id.in_(app_ids)).delete(
                synchronize_session=False
            )
        for model, row_id in ((LoanOffer, ids[0]), (FixedDepositScheme, ids[1])):
            row = session.get(model, row_id)
            if row is not None:
                session.delete(row)  # ORM cascade removes applications / bookings
        session.commit()


def test_money_actions_write_one_audit_row_each(client, products, monkeypatch):
    import services.loan_marketplace_service as loan_service

    monkeypatch.setattr(loan_service, "get_mock_credit_score", lambda _uid: 850)
    offer_id, scheme_id = products
    uid = _new_user()
    request_id = f"audit-{uuid4().hex}"
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}", "X-Request-ID": request_id}
    device_id = f"audit-dev-{uuid4().hex}"

    for consent_type in ("credit_check", "sim_binding"):
        r = client.post("/api/kyc/consents", json={"consent_type": consent_type, "granted": True}, headers=headers)
        assert r.status_code == 200, r.text
    assert client.post("/api/kyc/device-binding", json={"device_id": device_id}, headers=headers).status_code == 200
    bank = client.post(
        "/api/finance/linked-bank-accounts",
        json={"bank_name": "HDFC", "masked_account_number": "XXXX4321"}, headers=headers,
    )
    assert bank.status_code == 200, bank.text
    loan = client.post(
        "/api/finance/loan-applications",
        json={"loan_offer_id": offer_id, "requested_amount": 1_00_000, "requested_tenure_months": 24,
              "device_id": device_id},
        headers=headers,
    )
    assert loan.status_code == 200 and loan.json()["status"] == "approved", loan.text
    disb = client.post(f"/api/finance/loan-applications/{loan.json()['id']}/disburse", headers=headers)
    assert disb.status_code == 200, disb.text
    fd = client.post(
        "/api/fixed-deposits/bookings",
        json={"scheme_id": scheme_id, "principal_amount": 1_00_000, "tenure_months": 12,
              "payment_method": "upi", "device_id": device_id},
        headers=headers,
    )
    assert fd.status_code == 200, fd.text

    rows = _rows(uid)
    counts = Counter(r.action for r in rows)
    for action in ("bank_account_linked", "loan_application_submitted", "loan_disbursement_completed",
                   "fd_booked", "device_bound"):
        assert counts[action] == 1, (action, counts)
    assert counts["consent_granted"] == 2
    for row in rows:
        assert row.ip_address == "testclient"
        assert row.details["_ctx"]["request_id"] == request_id


def test_audit_details_json_safe():
    from services.audit_service import audit

    uid = _new_user()
    with database.get_session() as session:
        audit(session, uid, "test_event", {"at": datetime.now(timezone.utc)}, ip_address="10.0.0.9")
        session.commit()
    (row,) = _rows(uid)
    assert isinstance(row.details["at"], str)
    assert row.ip_address == "10.0.0.9"
    assert row.details["_ctx"]["request_id"] == "-"  # outside a request


def test_withdraw_consent_single_audit_row(client):
    from services.kyc_consent_service import record_consent

    uid = _new_user()
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}
    record_consent(uid, "data_sharing", True)

    resp = client.post("/api/v1/compliance/consents/withdraw", json={"consent_type": "data_sharing"}, headers=headers)

    assert resp.status_code == 200, resp.text
    assert [r.action for r in _rows(uid)].count("consent_withdrawn") == 1


def test_login_is_audited(client):
    from services.auth_service import register_user
    from services.disclosure_service import CURRENT_POLICY_VERSION

    username = f"audit_login_{uuid4().hex[:10]}"
    password = "Audit-pass-123"
    uid = register_user(username, password, "Audit Login", CURRENT_POLICY_VERSION, True)["user_id"]

    resp = client.post("/login", json={"username": username, "password": password})

    assert resp.status_code == 200, resp.text
    actions = [r.action for r in _rows(uid)]
    assert actions.count("account_registered") == 1
    assert actions.count("login") == 1
