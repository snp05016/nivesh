"""MATH-17 / AUTH-05: the public SIP calculator rejects inputs that would pin a worker
(years) or overflow to inf (step-up), and still computes valid requests."""
import pytest

URL = "/portfolio/sip-calculator"
VALID = {"monthly_amount": 5000, "expected_return_pct": 12, "years": 10, "step_up_pct": 10}


@pytest.mark.parametrize("override", [
    {"years": 1000},
    {"years": 0},
    {"step_up_pct": 1000},
    {"step_up_pct": -1},
    {"monthly_amount": 0},
    {"monthly_amount": 1e9},
    {"expected_return_pct": 51},
    {"expected_return_pct": -51},
])
def test_sip_calculator_rejects_out_of_range(client, override):
    resp = client.post(URL, json={**VALID, **override})
    assert resp.status_code == 422, resp.text


def test_sip_calculator_valid_request(client):
    resp = client.post(URL, json=VALID)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["yearly_projections"]) == 10
    invested = sum(12 * 5000 * 1.1 ** year for year in range(10))
    assert data["summary"]["total_invested_lakhs"] == round(invested / 1e5, 2)


def test_sip_calculator_worst_case_is_finite(client):
    resp = client.post(URL, json={"monthly_amount": 1e8, "expected_return_pct": 50,
                                  "years": 50, "step_up_pct": 100})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["yearly_projections"]) == 50
