"""REG-05: demo loan/FD marketplaces use fictional lender names, an IRR-based
APR on the net disbursal, a KFS for the requested terms, APR ranking, and
decision text that does not show the hash-derived score."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

KFS_URL = "/api/v1/compliance/key-fact-statement"
OFFERS_URL = "/api/finance/loan-offers"
_REAL_BRANDS = ("Bajaj", "HDB", "LIC", "Tata", "Muthoot", "HDFC", "SBI", "ICICI", "Shriram", "PNB")


def _make_offer(rate: float, fee: float, min_amount: float = 50_000, min_tenure: int = 12) -> int:
    import database
    from models.db_models import LoanOffer  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name=f"REG-05 Test Lender {uuid4().hex[:8]}",
            loan_type="personal",
            min_amount=min_amount,
            max_amount=25_00_000,
            interest_rate_pct=rate,
            min_tenure_months=min_tenure,
            max_tenure_months=60,
            min_credit_score=700,
            processing_fee_pct=fee,
            is_active=True,
        )
        session.add(offer)
        session.commit()
        return int(offer.id)  # type: ignore[arg-type]


def _delete_offers(ids: list[int]) -> None:
    import database
    from models.db_models import LoanOffer  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        for offer_id in ids:
            row = session.get(LoanOffer, offer_id)
            if row is not None:
                session.delete(row)
        session.commit()


@pytest.fixture
def offers():
    created: list[int] = []

    def make(*args, **kwargs) -> int:
        offer_id = _make_offer(*args, **kwargs)
        created.append(offer_id)
        return offer_id

    yield make
    _delete_offers(created)


def test_apr_irr():
    from services.finance_calculators import calculate_apr

    assert calculate_apr(50_000, 11.5, 12, 2.5) == pytest.approx(16.33, abs=0.01)


def test_apr_no_fee_equals_rate():
    from services.finance_calculators import calculate_apr

    assert calculate_apr(1_00_000, 10, 24, 0) == pytest.approx(10.0, abs=0.01)


def test_emi_matches_closed_form():
    from services.finance_calculators import calculate_emi

    assert calculate_emi(50_000, 11.5, 12) == pytest.approx(4430.75, abs=0.01)
    assert calculate_emi(12_000, 0, 12) == pytest.approx(1000.0)


def test_kfs_uses_requested_terms(client, offers):
    offer_id = offers(11.5, 2.5)

    resp = client.get(KFS_URL, params={"loan_offer_id": offer_id, "amount": 50_000, "tenure_months": 12})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["apr"] == pytest.approx(16.33, abs=0.01)
    assert body["emi"] == pytest.approx(4430.75, abs=0.01)
    assert body["total_repayable"] == pytest.approx(4430.75 * 12 + 1250, abs=0.1)

    longer = client.get(KFS_URL, params={"loan_offer_id": offer_id, "amount": 5_00_000, "tenure_months": 60})
    assert longer.status_code == 200, longer.text
    assert longer.json()["loan_amount"] == 5_00_000
    assert longer.json()["tenure_months"] == 60
    assert longer.json()["apr"] < body["apr"]


def test_no_real_lender_names():
    from services.fixed_deposit_service import _MOCK_FD_SCHEMES
    from services.loan_marketplace_service import _MOCK_LOAN_OFFERS

    names = [o["nbfc_name"] for o in _MOCK_LOAN_OFFERS] + [s["issuer_name"] for s in _MOCK_FD_SCHEMES]
    for name in names:
        assert not any(brand in name for brand in _REAL_BRANDS), name
        assert "fictional" in name


def test_offers_ranked_by_apr(client, offers, monkeypatch):
    import config.settings

    monkeypatch.setattr(config.settings, "DEMO_MODE", True)
    # Lower headline rate but a large fee over a short tenure: higher APR.
    cheap_rate = offers(9.0, 5.0, min_tenure=6)
    low_apr = offers(10.0, 0.0)

    resp = client.get(OFFERS_URL, params={"loan_type": "personal"})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    aprs = [row["max_apr_pct"] for row in rows]
    assert aprs == sorted(aprs)
    ids = [row["id"] for row in rows]
    assert ids.index(low_apr) < ids.index(cheap_rate)
    by_id = {row["id"]: row for row in rows}
    assert by_id[low_apr]["max_apr_pct"] == pytest.approx(10.0, abs=0.01)
    assert by_id[low_apr]["emi_at_min"] > 0


@pytest.mark.parametrize("score", [450, 690, 710, 800])
def test_decision_text_hides_score_and_lender(score):
    from services.loan_marketplace_service import _evaluate_demo_underwriting

    offer = SimpleNamespace(min_credit_score=700, nbfc_name="Demo Lender A (fictional)")
    _status, reason = _evaluate_demo_underwriting(score, offer)  # type: ignore[arg-type]
    assert reason.startswith("MOCK DECISION:")
    assert str(score) not in reason
    assert "Demo Lender" not in reason
