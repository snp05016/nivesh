"""FINSEC-19: loan/FD bookings, the FD calculator and the KFS endpoint reject
out-of-range or inactive-product inputs with 422 instead of persisting them
or failing with a 500 (float overflow / Numeric(14,2) overflow)."""
from __future__ import annotations

from typing import cast

import pytest

LOAN_URL = "/api/finance/loan-applications"
FD_URL = "/api/fixed-deposits/bookings"
CALC_URL = "/api/fixed-deposits/calculator"
KFS_URL = "/api/v1/compliance/key-fact-statement"


@pytest.fixture
def loan_offer():
    import database
    from models.db_models import LoanOffer  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name="FINSEC-19 Test NBFC",
            loan_type="personal",
            min_amount=50000,
            max_amount=500000,
            interest_rate_pct=12.5,
            min_tenure_months=12,
            max_tenure_months=60,
            min_credit_score=650,
            processing_fee_pct=1.0,
            is_active=True,
        )
        session.add(offer)
        session.commit()
        offer_id = cast(int, offer.id)
    yield offer_id
    with database.get_session() as session:
        offer = session.get(LoanOffer, offer_id)
        if offer is not None:
            session.delete(offer)  # cascades to applications
            session.commit()


@pytest.fixture
def fd_scheme():
    import database
    from models.db_models import FixedDepositScheme  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        scheme = FixedDepositScheme(
            issuer_name="FINSEC-19 Test Bank",
            min_tenure_months=6,
            max_tenure_months=12,
            min_amount=10000,
            max_amount=1000000,
            interest_rate_pct=6.6,
            senior_citizen_bonus_pct=0.5,
            is_active=True,
        )
        session.add(scheme)
        session.commit()
        scheme_id = cast(int, scheme.id)
    yield scheme_id
    with database.get_session() as session:
        scheme = session.get(FixedDepositScheme, scheme_id)
        if scheme is not None:
            session.delete(scheme)  # cascades to bookings
            session.commit()


def _deactivate(model_name: str, row_id: int) -> None:
    import database
    from models import db_models  # pyright: ignore[reportMissingImports]

    model = getattr(db_models, model_name)
    with database.get_session() as session:
        session.get(model, row_id).is_active = False
        session.commit()


def _count(model_name: str, fk: str, row_id: int) -> int:
    import database
    from models import db_models  # pyright: ignore[reportMissingImports]

    model = getattr(db_models, model_name)
    with database.get_session() as session:
        return session.query(model).filter(getattr(model, fk) == row_id).count()


def _loan(offer_id: int, amount: float = 100000, tenure: int = 24):
    return {"loan_offer_id": offer_id, "requested_amount": amount, "requested_tenure_months": tenure}


def _fd(scheme_id: int, amount: float = 50000, tenure: int = 12):
    return {"scheme_id": scheme_id, "principal_amount": amount, "tenure_months": tenure, "payment_method": "upi"}


# --- Loan applications ------------------------------------------------------

def test_loan_amount_above_max_422(client, auth_headers, loan_offer):
    resp = client.post(LOAN_URL, json=_loan(loan_offer, amount=500001), headers=auth_headers)
    assert resp.status_code == 422, resp.text
    assert _count("LoanApplication", "loan_offer_id", loan_offer) == 0


def test_loan_tenure_below_min_422(client, auth_headers, loan_offer):
    resp = client.post(LOAN_URL, json=_loan(loan_offer, tenure=6), headers=auth_headers)
    assert resp.status_code == 422, resp.text
    assert _count("LoanApplication", "loan_offer_id", loan_offer) == 0


def test_inactive_offer_422(client, auth_headers, loan_offer):
    _deactivate("LoanOffer", loan_offer)
    resp = client.post(LOAN_URL, json=_loan(loan_offer), headers=auth_headers)
    assert resp.status_code == 422, resp.text
    assert _count("LoanApplication", "loan_offer_id", loan_offer) == 0


def test_loan_amount_above_overflow_cap_422(client, auth_headers, loan_offer):
    resp = client.post(LOAN_URL, json=_loan(loan_offer, amount=5e12), headers=auth_headers)
    assert resp.status_code == 422, resp.text


def test_valid_application_still_200(client, auth_headers, loan_offer):
    resp = client.post(LOAN_URL, json=_loan(loan_offer), headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["requested_amount"] == 100000
    assert _count("LoanApplication", "loan_offer_id", loan_offer) == 1


# --- FD bookings ------------------------------------------------------------

def test_fd_booking_out_of_range_422(client, auth_headers, fd_scheme):
    resp = client.post(FD_URL, json=_fd(fd_scheme, tenure=120), headers=auth_headers)
    assert resp.status_code == 422, resp.text
    resp = client.post(FD_URL, json=_fd(fd_scheme, amount=5000), headers=auth_headers)
    assert resp.status_code == 422, resp.text
    assert _count("FixedDepositBooking", "scheme_id", fd_scheme) == 0


def test_fd_inactive_scheme_422(client, auth_headers, fd_scheme):
    _deactivate("FixedDepositScheme", fd_scheme)
    resp = client.post(FD_URL, json=_fd(fd_scheme), headers=auth_headers)
    assert resp.status_code == 422, resp.text
    assert _count("FixedDepositBooking", "scheme_id", fd_scheme) == 0


def test_fd_booking_huge_tenure_422_not_500(client, auth_headers, fd_scheme):
    resp = client.post(FD_URL, json=_fd(fd_scheme, tenure=10**7), headers=auth_headers)
    assert resp.status_code == 422, resp.text


# --- FD calculator (unauthenticated) -----------------------------------------

def test_fd_calculator_huge_tenure_422_not_500(client):
    resp = client.post(CALC_URL, json={"principal_amount": 100000, "tenure_months": 10**7, "interest_rate_pct": 7})
    assert resp.status_code == 422, resp.text


def test_fd_calculator_huge_rate_422_not_500(client):
    resp = client.post(CALC_URL, json={"principal_amount": 100000, "tenure_months": 12, "interest_rate_pct": 1e6})
    assert resp.status_code == 422, resp.text


def test_fd_calculator_valid_200(client):
    resp = client.post(CALC_URL, json={"principal_amount": 100000, "tenure_months": 12, "interest_rate_pct": 7})
    assert resp.status_code == 200, resp.text
    assert resp.json()["maturity_amount"] > 100000


def test_calculate_fd_maturity_overflow_raises_valueerror():
    from services.fixed_deposit_service import calculate_fd_maturity

    with pytest.raises(ValueError):
        calculate_fd_maturity(principal=100000, tenure_months=1200, interest_rate_pct=1e6)


# --- Key Fact Statement -------------------------------------------------------

def test_kfs_amount_outside_offer_range_422(client, loan_offer):
    resp = client.get(KFS_URL, params={"loan_offer_id": loan_offer, "amount": 10_000_000})
    assert resp.status_code == 422, resp.text


def test_kfs_tenure_outside_scheme_range_422(client, fd_scheme):
    resp = client.get(KFS_URL, params={"scheme_id": fd_scheme, "tenure_months": 120})
    assert resp.status_code == 422, resp.text


def test_kfs_amount_above_overflow_cap_422(client, loan_offer):
    resp = client.get(KFS_URL, params={"loan_offer_id": loan_offer, "amount": 5e12})
    assert resp.status_code == 422, resp.text


def test_kfs_in_range_and_default_200(client, loan_offer):
    resp = client.get(KFS_URL, params={"loan_offer_id": loan_offer, "amount": 200000, "tenure_months": 36})
    assert resp.status_code == 200, resp.text
    assert resp.json()["loan_amount"] == 200000
    assert resp.json()["tenure_months"] == 36

    resp = client.get(KFS_URL, params={"loan_offer_id": loan_offer})
    assert resp.status_code == 200, resp.text
    assert resp.json()["loan_amount"] == 50000
