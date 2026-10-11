"""FINSEC-26: the Key Fact Statement describes the applicant's own loan (APR
as the IRR on the net disbursal, for the requested amount and tenure), and
each loan application stores that KFS and whether it was acknowledged."""
from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    import config.settings

    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # /api/finance/loan-applications is demo-gated (FAKE-23); the KFS route is not


KFS_URL = "/api/v1/compliance/key-fact-statement"
APPS_URL = "/api/finance/loan-applications"
# 10,00,000 at 11.5% with a 2.5% fee over 60 months: monthly IRR of the EMIs
# on the 9,75,000 disbursed is ~1.0517%, i.e. 12.62% nominal a year.
REFERENCE_APR = 12.62


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        user = User(username=f"kfs_{uuid4().hex[:12]}", password_hash="x", display_name="KFS Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.fixture
def offer_id():
    """11.5% / 2.5% fee offer: 50,000 to 25,00,000, 12 to 60 months."""
    import database
    from models.db_models import LoanOffer  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name=f"FINSEC-26 Test Lender {uuid4().hex[:8]}",
            loan_type="personal",
            min_amount=50_000,
            max_amount=25_00_000,
            interest_rate_pct=11.5,
            min_tenure_months=12,
            max_tenure_months=60,
            min_credit_score=700,
            processing_fee_pct=2.5,
            is_active=True,
        )
        session.add(offer)
        session.commit()
        new_id = int(offer.id)  # type: ignore[arg-type]
    yield new_id
    with database.get_session() as session:
        row = session.get(LoanOffer, new_id)
        if row is not None:
            session.delete(row)  # ORM cascade removes this offer's applications
            session.commit()


def test_apr_matches_irr_reference():
    from services.finance_calculators import calculate_apr

    assert calculate_apr(10_00_000, 11.5, 60, 2.5) == pytest.approx(REFERENCE_APR, abs=0.05)
    # The old straight-line formula (rate + fee / years) would give 12.00.
    assert calculate_apr(10_00_000, 11.5, 60, 2.5) > 12.5


def test_zero_rate_with_fee_has_positive_apr():
    from services.finance_calculators import calculate_apr

    assert calculate_apr(1_20_000, 0, 12, 2.0) > 0


def test_kfs_for_requested_amount_and_tenure(client, offer_id):
    resp = client.get(KFS_URL, params={"loan_offer_id": offer_id, "amount": 10_00_000, "tenure_months": 60})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["loan_amount"] == 10_00_000
    assert body["tenure_months"] == 60
    assert body["all_fees"] == pytest.approx(25_000)
    assert body["apr"] == pytest.approx(REFERENCE_APR, abs=0.05)


def _apply(client, headers, offer, **extra):
    payload = {"loan_offer_id": offer, "requested_amount": 10_00_000, "requested_tenure_months": 60, **extra}
    return client.post(APPS_URL, json=payload, headers=headers)


def test_application_stores_acknowledged_kfs(client, offer_id):
    headers = _new_user_headers()
    resp = _apply(client, headers, offer_id, kfs_acknowledged=True)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kfs_apr_pct"] == pytest.approx(REFERENCE_APR, abs=0.05)
    assert body["kfs_total_fees"] == pytest.approx(25_000)
    assert body["kfs_acknowledged_at"] is not None

    stored = client.get(f"{APPS_URL}/{body['id']}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["kfs_apr_pct"] == body["kfs_apr_pct"]
    assert stored.json()["kfs_acknowledged_at"] == body["kfs_acknowledged_at"]


def test_application_without_acknowledgment_keeps_snapshot_only(client, offer_id):
    """Older app builds omit kfs_acknowledged: the KFS is still recorded."""
    resp = _apply(client, _new_user_headers(), offer_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kfs_apr_pct"] == pytest.approx(REFERENCE_APR, abs=0.05)
    assert body["kfs_acknowledged_at"] is None
