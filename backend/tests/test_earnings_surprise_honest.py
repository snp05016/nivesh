"""FAKE-11 / GH-654: Earnings Surprise reports only real estimate/actual pairs.

No constant 'Q4 FY24' quarter, no fabricated 1D/5D reaction, no mock score or
streak, and nothing synthetic persisted.
"""
import inspect
from datetime import date
from unittest.mock import MagicMock

import services.earnings_surprise as es
from database import get_session
from models.db_models import EarningsSurpriseHistory

_NO_ESTIMATES = {"ticker": "TCS", "company_name": "TCS", "eps_estimate": None, "eps_actual": None}


def test_missing_estimate_returns_none(monkeypatch):
    monkeypatch.setattr(es, "earnings_estimates_endpoint", MagicMock(return_value=_NO_ESTIMATES))
    assert es.compute_surprise_for_ticker("TCS") is None


def test_pair_without_period_returns_none(monkeypatch):
    payload = {"ticker": "TCS", "eps_estimate": 30.0, "eps_actual": 35.0}
    monkeypatch.setattr(es, "earnings_estimates_endpoint", MagicMock(return_value=payload))
    assert es.compute_surprise_for_ticker("TCS") is None


def test_real_pair_uses_fiscal_quarter_and_no_mock_fields(monkeypatch):
    payload = {"ticker": "ZZTEST", "company_name": "ZZ", "eps_estimate": 30.0,
               "eps_actual": 35.0, "period_end": "2026-06-30"}
    monkeypatch.setattr(es, "earnings_estimates_endpoint", MagicMock(return_value=payload))
    r = es.compute_surprise_for_ticker("ZZTEST")
    assert r is not None
    assert r["quarter"] == "Q1 FY27"
    assert r["classification"] == "BEAT"
    assert r["post_price_1d"] is None and r["post_price_5d"] is None
    assert r["historical_score"] is None
    assert r["serial_pattern"] is None  # no stored prior quarters


def test_fy_quarter_label():
    assert es._fy_quarter_label(date(2026, 4, 1)) == "Q1 FY27"
    assert es._fy_quarter_label(date(2026, 12, 31)) == "Q3 FY27"
    assert es._fy_quarter_label(date(2027, 3, 31)) == "Q4 FY27"


def test_no_mock_literals_in_source():
    src = inspect.getsource(es)
    assert "Q4 FY24" not in src
    assert "Mock score" not in src
    assert "iloc[-6]" not in src


def test_surprises_endpoint_empty_without_estimates(client, monkeypatch):
    monkeypatch.setattr(es, "earnings_estimates_endpoint", MagicMock(return_value=_NO_ESTIMATES))
    monkeypatch.setattr(es, "_dc_get", lambda *_a, **_k: None)  # bypass the 1 h cache
    resp = client.get("/api/v1/earnings/surprises")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    with get_session() as session:
        assert session.query(EarningsSurpriseHistory).filter_by(quarter="Q4 FY24").count() == 0


def test_history_does_not_compute_on_miss(client, monkeypatch):
    estimates = MagicMock(return_value=_NO_ESTIMATES)
    monkeypatch.setattr(es, "earnings_estimates_endpoint", estimates)
    resp = client.get("/api/v1/earnings/surprise-history/NOSUCHTICKER")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    estimates.assert_not_called()
