"""FINSEC-28: linked-bank lifecycle for the loan marketplace demo: first link is
primary, duplicates are 409, accounts can be unlinked (the primary role moves
to another account) and the primary can be switched, all scoped to the caller."""
from __future__ import annotations

from uuid import uuid4

import pytest

import config.settings
import database
from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    LinkedBankAccount,
    LoanApplication,
    LoanDisbursement,
    LoanOffer,
)

_URL = "/api/finance/linked-bank-accounts"


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # /api/finance is demo-gated (FAKE-23)


def _new_user() -> tuple[int, dict]:
    from models.db_models import User  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        user = User(username=f"bank_{uuid4().hex[:12]}", password_hash="x", display_name="Bank Test")
        session.add(user)
        session.commit()
        uid = int(user.id)  # type: ignore[arg-type]
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _link(client, headers, last4: str) -> dict:
    resp = client.post(_URL, json={"bank_name": "HDFC", "masked_account_number": f"XXXX{last4}"}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _primary_ids(client, headers) -> list[int]:
    return [a["id"] for a in client.get(_URL, headers=headers).json() if a["is_primary"]]


def test_duplicate_link_returns_409(client):
    _, headers = _new_user()
    _link(client, headers, "1111")
    resp = client.post(_URL, json={"bank_name": "HDFC", "masked_account_number": "XXXX1111"}, headers=headers)
    assert resp.status_code == 409, resp.text


def test_first_link_is_primary_second_is_not(client):
    _, headers = _new_user()
    first = _link(client, headers, "1111")
    second = _link(client, headers, "2222")
    assert first["is_primary"] is True
    assert second["is_primary"] is False


def test_unlink_primary_promotes_other(client):
    _, headers = _new_user()
    first = _link(client, headers, "1111")
    second = _link(client, headers, "2222")

    resp = client.delete(f"{_URL}/{first['id']}", headers=headers)

    assert resp.status_code == 204, resp.text
    assert [a["id"] for a in client.get(_URL, headers=headers).json()] == [second["id"]]
    assert _primary_ids(client, headers) == [second["id"]]


def test_unlink_account_with_disbursement_409(client):
    uid, headers = _new_user()
    account = _link(client, headers, "1111")
    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name=f"Bank Test NBFC {uuid4().hex[:8]}", loan_type="personal", min_amount=50_000,
            max_amount=5_00_000, interest_rate_pct=12.0, min_tenure_months=6, max_tenure_months=60,
            min_credit_score=600, processing_fee_pct=1.0, is_active=True,
        )
        session.add(offer)
        session.flush()
        application = LoanApplication(
            user_id=uid, loan_offer_id=offer.id, requested_amount=1_00_000,
            requested_tenure_months=12, status="disbursed",
        )
        session.add(application)
        session.flush()
        session.add(LoanDisbursement(
            loan_application_id=application.id, user_id=uid, linked_bank_account_id=account["id"],
            nbfc_name=offer.nbfc_name, disbursed_amount=1_00_000, status="completed",
        ))
        session.commit()
        offer_id = int(offer.id)  # type: ignore[arg-type]
    try:
        resp = client.delete(f"{_URL}/{account['id']}", headers=headers)

        assert resp.status_code == 409, resp.text
        with database.get_session() as session:
            assert session.get(LinkedBankAccount, account["id"]) is not None
    finally:
        with database.get_session() as session:
            session.query(LoanDisbursement).filter(LoanDisbursement.user_id == uid).delete(synchronize_session=False)
            row = session.get(LoanOffer, offer_id)
            if row is not None:
                session.delete(row)  # ORM cascade removes the application
            session.commit()


def test_set_primary_switches_exactly_one(client):
    _, headers = _new_user()
    first = _link(client, headers, "1111")
    second = _link(client, headers, "2222")

    resp = client.patch(f"{_URL}/{second['id']}/primary", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_primary"] is True
    assert _primary_ids(client, headers) == [second["id"]]
    assert first["id"] not in _primary_ids(client, headers)


def test_other_users_account_404(client):
    _, owner = _new_user()
    _, intruder = _new_user()
    account = _link(client, owner, "1111")

    assert client.delete(f"{_URL}/{account['id']}", headers=intruder).status_code == 404
    assert client.patch(f"{_URL}/{account['id']}/primary", headers=intruder).status_code == 404
    assert _primary_ids(client, owner) == [account["id"]]
