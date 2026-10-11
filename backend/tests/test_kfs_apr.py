"""MATH-12: the KFS APR is the IRR of the net disbursal against the EMI schedule."""
import pytest

from services.disclosure_service import irr_apr_pct

KFS_URL = "/api/v1/compliance/key-fact-statement"


def test_apr_includes_fee_on_amortizing_balance():
    # 11.5%, 2.5% fee, 12 months, Rs 1 lakh: net 97,500 against EMI 8,861.51.
    apr, emi = irr_apr_pct(1_00_000, 2_500, 11.5, 12)
    assert emi == pytest.approx(8861.51, abs=0.01)
    assert apr == pytest.approx(16.33, abs=0.1)  # the old rate + fee/years gave 14.00


def test_short_tenure_high_fee():
    apr, _ = irr_apr_pct(1_00_000, 3_000, 13.75, 6)
    assert apr == pytest.approx(24.5, abs=0.1)  # old formula: 19.75


def test_zero_fee_apr_equals_rate():
    apr, _ = irr_apr_pct(1_00_000, 0, 11.5, 12)
    assert apr == pytest.approx(11.5, abs=0.01)


def test_negative_amount_422(client):
    resp = client.get(KFS_URL, params={"loan_offer_id": 1, "amount": -5})
    assert resp.status_code == 422, resp.text
