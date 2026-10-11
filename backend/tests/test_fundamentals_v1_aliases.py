"""CMKT-14 / GH-622: /api/v1/fundamentals/* query routes use the requested ticker.

They used to ignore ?ticker= and always return RELIANCE.NS data.
"""
import pytest

import services.fundamentals as fundamentals_service
from database import get_session
from models.db_models import CompanyFinancial, ShareholdingPattern

_TICKERS = ("TCS", "INFY")


@pytest.fixture
def seeded_fundamentals():
    with get_session() as session:
        session.add_all([
            CompanyFinancial(ticker="TCS", period="Q4_2025", revenue=8e10, net_income=1e10),
            CompanyFinancial(ticker="TCS", period="Q1_2026", revenue=1e11, net_income=1.2e10),
            CompanyFinancial(ticker="INFY", period="Q1_2026", revenue=5e10, net_income=6e9),
            ShareholdingPattern(ticker="TCS", quarter="Q1_2026", promoter_pct=71.77,
                                fii_pct=12.5, dii_pct=10.0, public_pct=5.0, pledged_pct=0.0),
        ])
        session.commit()
    yield
    with get_session() as session:
        session.query(CompanyFinancial).filter(CompanyFinancial.ticker.in_(_TICKERS)).delete(synchronize_session=False)
        session.query(ShareholdingPattern).filter(ShareholdingPattern.ticker.in_(_TICKERS)).delete(synchronize_session=False)
        session.commit()


def test_alias_requires_ticker(client):
    assert client.get("/api/v1/fundamentals/financials").status_code == 422


def test_alias_uses_requested_ticker(client, seeded_fundamentals):
    tcs = client.get("/api/v1/fundamentals/financials", params={"ticker": "TCS", "period_type": "QUARTERLY"})
    infy = client.get("/api/v1/fundamentals/financials", params={"ticker": "INFY.NS"})
    assert tcs.status_code == 200, tcs.text
    assert infy.status_code == 200, infy.text
    assert tcs.json() != infy.json()
    assert tcs.json()["ticker"] == "TCS"
    assert infy.json()["ticker"] == "INFY"
    assert "RELIANCE" not in tcs.text and "RELIANCE" not in infy.text

    body = tcs.json()
    assert body["available_periods"] == ["Q1 2026", "Q4 2025"]
    revenue = next(item for item in body["line_items"] if item["label"] == "Revenue")
    assert revenue["values"] == {"Q1 2026": 10000.0, "Q4 2025": 8000.0}  # Crores
    assert revenue["qoq_change_pct"] == {"Q1 2026": 25.0}
    # No nulls inside the maps: iOS decodes them as [String: Double].
    assert all(v is not None for item in body["line_items"] for v in item["values"].values())


def test_alias_404_when_no_data(client):
    resp = client.get("/api/v1/fundamentals/financials", params={"ticker": "ZZZZ"})
    assert resp.status_code == 404
    assert "RELIANCE" not in resp.text


def test_shareholding_maps_db_rows(client, seeded_fundamentals):
    resp = client.get("/api/v1/fundamentals/shareholding", params={"ticker": "tcs"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ticker"] == "TCS"
    assert body["latest_quarter"] == "Q1 2026"
    promoter = next(c for c in body["categories"] if c["name"] == "PROMOTER")
    assert promoter["current_pct"] == 71.77
    assert body["top_holders"] == []
    assert body["holding_trend"][0]["others_pct"] == pytest.approx(0.73)


def test_risk_signals_empty_without_rows():
    resp = fundamentals_service.get_risk_signals_v1("ZZZZ")
    assert resp.ticker == "ZZZZ"
    assert resp.signals == [] and resp.overall_risk_score == 0.0
