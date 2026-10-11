"""CMON-13 / GH-644: mutual-fund data provenance.

The NAV-history endpoint must never fabricate points (it used to return a
seeded pseudo-random walk), and the seeded sample catalog must be flagged
`is_sample` so clients label it instead of presenting it as live fund data.
"""
from routers.mutual_funds import MutualFundResponse
from services.mutual_fund_service import SAMPLE_SCHEME_CODES

SAMPLE_CODE = "INF209K01157"  # Parag Parikh Flexi Cap — part of the seeded sample catalog


def test_nav_history_never_fabricated(client):
    resp = client.get(f"/api/mutual-funds/{SAMPLE_CODE}/nav-history?days=30")
    assert resp.status_code == 200
    assert resp.json() == []


def test_nav_history_unknown_scheme_404(client):
    resp = client.get("/api/mutual-funds/NOT-A-SCHEME/nav-history?days=30")
    assert resp.status_code == 404


def test_days_over_365_rejected(client):
    resp = client.get(f"/api/mutual-funds/{SAMPLE_CODE}/nav-history?days=400")
    assert resp.status_code == 422


def test_sample_funds_flagged(client):
    resp = client.get("/api/mutual-funds/")
    assert resp.status_code == 200
    rows = resp.json()
    sample_rows = [r for r in rows if r.get("scheme_code") in SAMPLE_SCHEME_CODES]
    assert sample_rows, "seeded sample catalog should be listed"
    assert all(r["is_sample"] is True for r in sample_rows)


def test_sample_fund_detail_flagged(client):
    resp = client.get(f"/api/mutual-funds/{SAMPLE_CODE}")
    assert resp.status_code == 200
    assert resp.json()["is_sample"] is True


def test_non_sample_fund_not_flagged():
    resp = MutualFundResponse.model_validate(
        {"id": 99, "scheme_code": "REAL-AMFI-123", "scheme_name": "Real Fund", "amc_name": "AMC", "category": "Equity"}
    )
    assert resp.is_sample is False
