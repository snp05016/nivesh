"""GET /api/v1/stocks/{symbol}/risk-flags: post-trade concentration checks (spec_ai 3.4)."""
import re
import uuid
from datetime import date, timedelta

import pytest

import database
from models.db_models import Portfolio, ResearchReportRow
from services import risk_flags_service

SYMS = ["ABC", "XYZ", "DEF", "GHI", "PQR"]


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("FEATURE_RISK_FLAGS_CONCENTRATION", "true")
    monkeypatch.delenv("FEATURE_RISK_FLAGS_SURVEILLANCE", raising=False)


@pytest.fixture
def seed(test_user_id):
    """seed(holdings, reports): holdings = [(ticker, shares, buy_price)], reports = {symbol: (close, sector)}."""
    def put(holdings, reports):
        yesterday = date.today() - timedelta(days=1)
        with database.get_session() as s:
            for ticker, shares, price in holdings:
                s.add(Portfolio(user_id=test_user_id, ticker=ticker, company_name=ticker, shares=shares,
                                buy_price=price, group_name="holdings"))
            for sym, (close, sector) in reports.items():
                fact = ({"value": close, "status": "ok"} if close is not None
                        else {"value": None, "status": "unavailable"})
                s.add(ResearchReportRow(
                    report_uid=str(uuid.uuid4()), symbol=sym, as_of_date=yesterday, engine_version="t",
                    origin="nightly", status="ok", in_universe=True,
                    report_json={"snapshot": {"last_close": fact}, "sector": sector, "company_name": sym}))
            s.commit()

    yield put
    with database.get_session() as s:
        s.query(Portfolio).filter(Portfolio.user_id == test_user_id).delete()
        s.query(ResearchReportRow).filter(ResearchReportRow.symbol.in_(SYMS)).delete(synchronize_session=False)
        s.commit()


def _get(client, headers, symbol="ABC"):
    return client.get(f"/api/v1/stocks/{symbol}/risk-flags", headers=headers)


def test_requires_token(client):
    assert client.get("/api/v1/stocks/ABC/risk-flags").status_code == 401


def test_flag_off_is_404(client, auth_headers, monkeypatch):
    monkeypatch.setenv("FEATURE_RISK_FLAGS_CONCENTRATION", "false")
    resp = _get(client, auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_bad_symbol_is_422(client, auth_headers):
    resp = client.get("/api/v1/stocks/BAD SYMBOL!/risk-flags", headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["detail"] == {"code": "INVALID_SYMBOL"}


def test_holding_and_sector_flags(client, auth_headers, seed):
    seed([("ABC", 6, 10), ("XYZ", 4, 10)], {"ABC": (10, "IT"), "XYZ": (10, "IT")})
    body = _get(client, auth_headers).json()
    assert body["checks"] == ["concentration"] and body["unavailable"] == []
    by_id = {f["id"]: f for f in body["flags"]}
    assert "60.0%" in by_id["holding_concentration"]["text"]
    assert "by current value" in by_id["holding_concentration"]["text"]
    assert "IT stocks are 100.0%" in by_id["sector_concentration"]["text"]
    assert by_id["holding_concentration"]["as_of"] == (date.today() - timedelta(days=1)).isoformat()
    assert set(by_id["holding_concentration"]) == {"id", "title", "text", "source", "source_url", "as_of"}


def test_lots_are_aggregated(client, auth_headers, seed):
    seed([("ABC.NS", 1, 15), ("ABC", 1, 15), ("DEF", 1, 35), ("GHI", 1, 35)],
         {"ABC": (15, "IT"), "DEF": (35, "Banks"), "GHI": (35, "Auto")})
    flags = _get(client, auth_headers).json()["flags"]
    assert "30.0%" in flags[0]["text"]


def test_missing_report_uses_invested_basis(client, auth_headers, seed):
    seed([("ABC", 6, 10), ("XYZ", 4, 10)], {"ABC": (10, "IT")})
    flag = _get(client, auth_headers).json()["flags"][0]
    assert "by amount invested" in flag["text"] and flag["as_of"] is None


def test_unavailable_close_uses_invested_basis(client, auth_headers, seed):
    seed([("ABC", 6, 10), ("XYZ", 4, 10)], {"ABC": (None, "IT"), "XYZ": (10, "IT")})
    resp = _get(client, auth_headers)
    assert resp.status_code == 200
    assert "by amount invested" in resp.json()["flags"][0]["text"]


def test_unheld_stock_gets_no_flags(client, auth_headers, seed):
    seed([("ABC", 6, 10), ("XYZ", 4, 10)], {"ABC": (10, "IT"), "XYZ": (10, "IT"), "PQR": (10, "IT")})
    assert _get(client, auth_headers, "PQR").json()["flags"] == []


def test_single_holding_has_no_sector_flag(client, auth_headers, seed):
    seed([("ABC", 5, 10)], {"ABC": (10, "IT")})
    flags = _get(client, auth_headers).json()["flags"]
    assert [f["id"] for f in flags] == ["holding_concentration"]
    assert "100.0%" in flags[0]["text"]


def test_at_most_three_flags(test_user_id, monkeypatch):
    monkeypatch.setattr(risk_flags_service, "concentration_flags", lambda *_a: [{"id": str(i)} for i in range(5)])
    assert len(risk_flags_service.risk_flags(test_user_id, "ABC")["flags"]) == 3


def test_flag_text_has_no_advice_words(client, auth_headers, seed):
    seed([("ABC", 6, 10), ("XYZ", 4, 10)], {"ABC": (10, "IT"), "XYZ": (10, "IT")})
    bad = re.compile(r"\b(buy|sell|hold|should|recommend|avoid|risky|safe)\b", re.IGNORECASE)
    for flag in _get(client, auth_headers).json()["flags"]:
        assert not bad.search(flag["title"] + " " + flag["text"])


def test_surveillance_absent_when_unset(client, auth_headers, seed):
    seed([("ABC", 5, 10)], {"ABC": (10, "IT")})
    body = _get(client, auth_headers).json()
    assert "surveillance" not in body["checks"] and body["unavailable"] == []
