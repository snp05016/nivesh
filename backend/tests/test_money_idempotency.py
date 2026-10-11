"""FINSEC-14: loan application and FD booking POSTs honour Idempotency-Key.

A client retry after a lost response used to insert a second application or
booking. The key is stored with UNIQUE(user_id, idempotency_key) and a repeat
returns the original row. (Disbursement idempotency is GH-670,
test_loan_disbursement.py.)

Each test uses a throwaway user and its own offer/scheme.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

import config.settings
import database
from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    FixedDepositBooking,
    FixedDepositScheme,
    LoanApplication,
    LoanOffer,
    User,
)


@pytest.fixture(autouse=True)
def demo_mode(monkeypatch):
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)


@pytest.fixture
def user():
    """(user_id, auth headers) for a throwaway user."""
    with database.get_session() as session:
        row = User(username=f"idem_{uuid4().hex[:12]}", password_hash="x", display_name="Idem Test")
        session.add(row)
        session.commit()
        user_id = int(row.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.fixture
def offer_id():
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
        oid = int(offer.id)  # type: ignore[arg-type]
    yield oid
    with database.get_session() as session:
        row = session.get(LoanOffer, oid)
        if row is not None:
            session.delete(row)  # ORM cascade removes this offer's applications
            session.commit()


@pytest.fixture
def scheme_id():
    with database.get_session() as session:
        scheme = FixedDepositScheme(
            issuer_name=f"Test Bank {uuid4().hex[:8]}",
            min_tenure_months=6,
            max_tenure_months=60,
            min_amount=10_000,
            max_amount=10_00_000,
            interest_rate_pct=7.0,
            senior_citizen_bonus_pct=0.5,
            is_active=True,
        )
        session.add(scheme)
        session.commit()
        sid = int(scheme.id)  # type: ignore[arg-type]
    yield sid
    with database.get_session() as session:
        row = session.get(FixedDepositScheme, sid)
        if row is not None:
            session.delete(row)  # ORM cascade removes this scheme's bookings
            session.commit()


def _apply(client, headers, offer_id, key=None):
    if key is not None:
        headers = {**headers, "Idempotency-Key": key}
    payload = {"loan_offer_id": offer_id, "requested_amount": 1_00_000, "requested_tenure_months": 24}
    return client.post("/api/finance/loan-applications", json=payload, headers=headers)


def _book(client, headers, scheme_id, key=None):
    if key is not None:
        headers = {**headers, "Idempotency-Key": key}
    payload = {"scheme_id": scheme_id, "principal_amount": 1_00_000, "tenure_months": 12, "payment_method": "upi"}
    return client.post("/api/fixed-deposits/bookings", json=payload, headers=headers)


def _count(model, user_id: int) -> int:
    with database.get_session() as session:
        return session.query(model).filter(model.user_id == user_id).count()


def test_loan_application_idempotency_key(client, user, offer_id):
    user_id, headers = user
    key = uuid4().hex

    r1 = _apply(client, headers, offer_id, key)
    r2 = _apply(client, headers, offer_id, key)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]
    assert _count(LoanApplication, user_id) == 1

    r3 = _apply(client, headers, offer_id, uuid4().hex)
    assert r3.status_code == 200, r3.text
    assert r3.json()["id"] != r1.json()["id"]
    assert _count(LoanApplication, user_id) == 2


def test_fd_booking_idempotency_key(client, user, scheme_id):
    user_id, headers = user
    key = uuid4().hex

    r1 = _book(client, headers, scheme_id, key)
    r2 = _book(client, headers, scheme_id, key)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]
    assert _count(FixedDepositBooking, user_id) == 1

    r3 = _book(client, headers, scheme_id, uuid4().hex)
    assert r3.status_code == 200, r3.text
    assert r3.json()["id"] != r1.json()["id"]
    assert _count(FixedDepositBooking, user_id) == 2


def test_no_key_and_blank_key_insert_each_time(client, user, offer_id):
    # Blank keys are stored as NULL, so they never collide on the constraint.
    user_id, headers = user
    ids = {_apply(client, headers, offer_id, key).json()["id"] for key in (None, "", "   ", "")}
    assert len(ids) == 4
    with database.get_session() as session:
        keys = [r.idempotency_key for r in session.query(LoanApplication).filter(LoanApplication.user_id == user_id)]
    assert len(keys) == 4 and all(k is None for k in keys)


def test_same_key_other_user_is_independent(client, user, offer_id):
    _, headers = user
    with database.get_session() as session:
        other = User(username=f"idem_{uuid4().hex[:12]}", password_hash="x", display_name="Idem Other")
        session.add(other)
        session.commit()
        other_id = int(other.id)  # type: ignore[arg-type]
    other_headers = {"Authorization": f"Bearer {database.create_access_token(other_id)}"}
    key = uuid4().hex

    r1 = _apply(client, headers, offer_id, key)
    r2 = _apply(client, other_headers, offer_id, key)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]


def test_unique_constraint_blocks_duplicate_key(user, offer_id):
    user_id, _ = user
    key = uuid4().hex

    def row():
        return LoanApplication(
            user_id=user_id, loan_offer_id=offer_id, requested_amount=1_00_000,
            requested_tenure_months=24, status="submitted", idempotency_key=key,
        )

    with database.get_session() as session:
        session.add(row())
        session.commit()
        session.add(row())
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
