"""money-tax-api: FY capital-gains working for listed shares, JSON and CSV (seeded ledgers, no network)."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from uuid import uuid4

import pytest

import database
from models.db_models import Portfolio, Transaction, User
from services import money_market_series as mms

URL = "/api/v1/me/tax/capital-gains"


def _user():
    with database.get_session() as session:
        user = User(username=f"tax_{uuid4().hex[:12]}", password_hash="x", display_name="Tax")
        session.add(user)
        session.commit()
        uid = int(user.id)
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _tx(uid, ticker, kind, when, qty, price=0.0, fees=0.0, notes=None, ac="EQ"):
    with database.get_session() as session:
        session.add(Transaction(user_id=uid, ticker=ticker, transaction_type=kind, quantity=qty, price=price, fees=fees,
                                date=datetime(*when), notes=notes, asset_class=ac))
        session.commit()


def _holding(uid, ticker, name, purchase_date=None, shares=1.0):
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker=ticker, company_name=name, shares=shares, buy_price=1.0,
                              group_name="holdings", purchase_date=purchase_date))
        session.commit()


@pytest.fixture(autouse=True)
def world(monkeypatch):
    monkeypatch.setenv("FEATURE_MONEY_TAX_REPORT", "true")
    state = {"allowed": True, "highs": {}, "calls": []}

    def raw_highs(items):
        state["calls"].append(items)
        return {i["key"]: {"key": i["key"], "status": "ok", "high": state["highs"][i["key"]], "close": 1.0}
                for i in items if i["key"] in state["highs"]}

    monkeypatch.setattr(mms, "display_allowed", lambda: state["allowed"])
    monkeypatch.setattr(mms, "raw_highs", raw_highs)
    return state


def _get(client, headers, fy="2025-26"):
    return client.get(f"{URL}?fy={fy}", headers=headers)


def test_flag_off_is_404(client, monkeypatch):
    monkeypatch.delenv("FEATURE_MONEY_TAX_REPORT", raising=False)
    _, headers = _user()
    r = _get(client, headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
    assert client.get(f"{URL}.csv?fy=2025-26", headers=headers).status_code == 404


def test_requires_auth(client):
    assert client.get(f"{URL}?fy=2025-26").status_code == 401


@pytest.mark.parametrize("fy", ["", "2025", "2025-27", "2017-18", "2099-00", "abcd-ef"])
def test_invalid_fy_is_422(client, fy):
    _, headers = _user()
    for path in (URL, URL + ".csv"):
        r = client.get(f"{path}?fy={fy}", headers=headers)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_FY"


def test_stcg_with_fees(client):
    uid, headers = _user()
    _tx(uid, "INFY", "BUY", (2025, 5, 10), 10, 1000.0, fees=20.0)
    _tx(uid, "INFY", "SELL", (2025, 12, 1), 10, 1200.0, fees=15.0)
    body = _get(client, headers).json()
    assert body["rules_version"] == "in-cg-2026.1" and body["fy"] == "2025-26"
    [row] = body["rows"]
    assert (row["term"], row["section"], row["rate_period"]) == ("STCG", "111A", "post_2024_07_23")
    assert row["sale_value_inr"] == 12000.0 and row["cost_of_acquisition_inr"] == 10020.0
    assert row["transfer_expenses_inr"] == 15.0 and row["gain_inr"] == 1965.0
    assert row["needs_review"] is False and row["review_reasons"] == []
    assert body["summary"]["stcg"] == {"pre_2024_07_23": 0.0, "post_2024_07_23": 1965.0}
    assert body["summary"]["ltcg_exemption_limit_inr"] == 125000.0
    assert body["scope_note"] == "Listed shares only. Mutual funds are not covered yet."
    assert body["disclaimer"].startswith("Informational working from your Nivesh transactions. Not tax advice.")


def test_grandfathered_cost_uses_nse_high(client, world):
    uid, headers = _user()
    world["highs"]["ITC"] = 800.0
    _tx(uid, "ITC", "BUY", (2017, 6, 1), 100, 500.0)
    _tx(uid, "ITC", "SELL", (2025, 9, 1), 100, 1000.0)
    [row] = _get(client, headers).json()["rows"]
    assert row["term"] == "LTCG" and row["section"] == "112A"
    assert row["cost_of_acquisition_inr"] == 50000.0
    assert row["fmv_per_unit"] == 800.0 and row["fmv_total_inr"] == 80000.0
    assert row["cost_used_inr"] == 80000.0 and row["gain_inr"] == 20000.0
    assert "fmv_nse_high" in row["review_reasons"] and row["needs_review"] is True


def test_split_after_2018_divides_the_2018_high(client, world):
    uid, headers = _user()
    world["highs"]["TCS"] = 2400.0
    _tx(uid, "TCS", "BUY", (2017, 6, 1), 100, 500.0)
    _tx(uid, "TCS", "SPLIT", (2019, 6, 1), 2)
    _tx(uid, "TCS", "SELL", (2025, 9, 1), 200, 1500.0)
    [row] = _get(client, headers).json()["rows"]
    assert row["quantity"] == 200.0 and row["fmv_per_unit"] == 1200.0 and row["fmv_total_inr"] == 240000.0
    assert row["cost_used_inr"] == 240000.0 and row["gain_inr"] == 60000.0


def test_bonus_lot_splits_terms_and_is_flagged(client):
    uid, headers = _user()
    _tx(uid, "WIPRO", "BUY", (2023, 1, 2), 10, 100.0)
    _tx(uid, "WIPRO", "BONUS", (2025, 8, 1), 10)
    _tx(uid, "WIPRO", "SELL", (2025, 12, 1), 20, 200.0)
    rows = _get(client, headers).json()["rows"]
    assert [(r["term"], r["quantity"], r["cost_used_inr"]) for r in rows] == [("LTCG", 10.0, 1000.0), ("STCG", 10.0, 0.0)]
    assert rows[1]["review_reasons"] == ["stt_on_acquisition_unverified"] and rows[0]["review_reasons"] == []


def test_adjust_only_position_is_not_computed(client):
    uid, headers = _user()
    _tx(uid, "HDFCBANK", "ADJUST", (2025, 6, 1), 10, 1500.0)
    _tx(uid, "HDFCBANK", "SELL", (2025, 12, 1), 10, 1700.0)
    body = _get(client, headers).json()
    assert body["rows"] == []
    assert body["not_computed"] == [{"symbol": "HDFCBANK", "sold_on": "2025-12-01", "quantity": 10.0,
                                     "reason": "acquisition_date_uncertain"}]
    assert body["summary"]["not_computed"] == 1


def test_opening_balance_needs_the_entered_purchase_date(client):
    uid, headers = _user()
    _holding(uid, "SBIN", "State Bank", purchase_date="2022-02-03")
    _tx(uid, "SBIN", "BUY", (2025, 6, 1), 10, 400.0, notes="Opening balance (pre-ledger holding)")
    _tx(uid, "SBIN", "SELL", (2025, 12, 1), 10, 700.0)
    _tx(uid, "RELIANCE", "BUY", (2025, 6, 1), 10, 400.0, notes="Opening balance (pre-ledger holding)")
    _tx(uid, "RELIANCE", "SELL", (2025, 12, 1), 10, 700.0)
    body = _get(client, headers).json()
    [row] = body["rows"]
    assert row["symbol"] == "SBIN" and row["acquired_on"] == "2022-02-03" and row["term"] == "LTCG"
    assert row["review_reasons"] == ["user_entered_date", "stt_on_acquisition_unverified"]
    assert [n["symbol"] for n in body["not_computed"]] == ["RELIANCE"]


def test_etf_heuristic_is_not_computed(client):
    uid, headers = _user()
    _holding(uid, "NIFTYBEES", "Nippon Nifty BeES")
    _tx(uid, "NIFTYBEES", "BUY", (2025, 5, 1), 10, 250.0)
    _tx(uid, "NIFTYBEES", "SELL", (2025, 12, 1), 10, 270.0)
    _tx(uid, "XYZ", "BUY", (2025, 5, 1), 10, 250.0)
    _tx(uid, "XYZ", "SELL", (2025, 12, 1), 10, 270.0)
    _holding(uid, "XYZ", "Gold ETF Fund")
    body = _get(client, headers).json()
    assert body["rows"] == []
    assert {n["reason"] for n in body["not_computed"]} == {"etf_category_unverified"}
    assert len(body["not_computed"]) == 2


def test_new_act_sections_from_april_2026(client):
    uid, headers = _user()
    _tx(uid, "AAA", "BUY", (2025, 5, 10), 10, 100.0)
    _tx(uid, "AAA", "SELL", (2026, 4, 15), 10, 120.0)
    _tx(uid, "BBB", "BUY", (2024, 1, 10), 10, 100.0)
    _tx(uid, "BBB", "SELL", (2026, 4, 15), 10, 150.0)
    rows = _get(client, headers, "2026-27").json()["rows"]
    assert {(r["symbol"], r["term"], r["section"]) for r in rows} == {("AAA", "STCG", "196"), ("BBB", "LTCG", "198")}
    assert _get(client, headers, "2025-26").json()["rows"] == []


def test_fy_filter_and_exemption_by_fy(client):
    uid, headers = _user()
    _tx(uid, "AAA", "BUY", (2022, 1, 10), 100, 100.0)
    _tx(uid, "AAA", "SELL", (2024, 2, 1), 50, 3000.0)    # FY 2023-24, LTCG 145000 -> above Rs 1,00,000 limit
    _tx(uid, "AAA", "SELL", (2025, 2, 1), 50, 3000.0)    # FY 2024-25
    old = _get(client, headers, "2023-24").json()
    assert old["summary"]["ltcg"]["post_2024_07_23"] == 0.0 and old["summary"]["ltcg"]["pre_2024_07_23"] == 145000.0
    assert old["summary"]["ltcg_exemption_limit_inr"] == 100000.0 and old["summary"]["ltcg_above_exemption_inr"] == 45000.0
    new = _get(client, headers, "2024-25").json()
    assert new["summary"]["ltcg"]["post_2024_07_23"] == 145000.0
    assert new["summary"]["ltcg_exemption_limit_inr"] == 125000.0 and new["summary"]["ltcg_above_exemption_inr"] == 20000.0


def test_raw_highs_called_once_for_three_grandfathered_tickers(client, world):
    uid, headers = _user()
    for ticker in ("AAA", "BBB", "CCC"):
        world["highs"][ticker] = 100.0
        _tx(uid, ticker, "BUY", (2016, 1, 5), 10, 50.0)
        _tx(uid, ticker, "SELL", (2025, 8, 5), 10, 200.0)
    rows = _get(client, headers).json()["rows"]
    assert len(rows) == 3
    assert len(world["calls"]) == 1
    assert sorted(i["symbol"] for i in world["calls"][0]) == ["AAA", "BBB", "CCC"]
    assert {i["date"] for i in world["calls"][0]} == {"2018-01-31"}


def test_fmv_unavailable_when_display_not_allowed(client, world):
    uid, headers = _user()
    world["allowed"] = False
    _tx(uid, "ITC", "BUY", (2017, 6, 1), 100, 500.0)
    _tx(uid, "ITC", "SELL", (2025, 9, 1), 100, 1000.0)
    body = _get(client, headers).json()
    assert body["rows"] == [] and body["not_computed"][0]["reason"] == "fmv_unavailable"
    assert world["calls"] == []


def test_possible_intraday_is_flagged(client):
    uid, headers = _user()
    _tx(uid, "AAA", "BUY", (2025, 1, 5), 10, 100.0)
    _tx(uid, "AAA", "BUY", (2025, 12, 1), 5, 150.0)
    _tx(uid, "AAA", "SELL", (2025, 12, 1), 10, 160.0)
    [row] = _get(client, headers).json()["rows"]
    assert "possible_intraday" in row["review_reasons"]


def test_funds_and_dividends_are_out_of_scope(client):
    uid, headers = _user()
    _tx(uid, "INF179K01VC4", "BUY", (2025, 5, 1), 10, 40.0, ac="MF")
    _tx(uid, "INF179K01VC4", "SELL", (2025, 12, 1), 10, 50.0, ac="MF")
    _tx(uid, "INFY", "BUY", (2025, 5, 1), 10, 100.0)
    _tx(uid, "INFY", "DIVIDEND", (2025, 8, 1), 10, 5.0)
    body = _get(client, headers).json()
    assert body["rows"] == [] and body["not_computed"] == []


def test_csv_lines_and_row_count(client, world):
    uid, headers = _user()
    _tx(uid, "INFY", "BUY", (2025, 5, 10), 10, 1000.0, fees=20.0)
    _tx(uid, "INFY", "SELL", (2025, 12, 1), 10, 1200.0, fees=15.0)
    _tx(uid, "HDFCBANK", "ADJUST", (2025, 6, 1), 10, 1500.0)
    _tx(uid, "HDFCBANK", "SELL", (2025, 12, 1), 10, 1700.0)
    r = client.get(f"{URL}.csv?fy=2025-26", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == "attachment; filename=nivesh_capital_gains_FY2025-26.csv"
    assert r.headers["cache-control"] == "no-store"
    lines = r.text.split("\n")
    assert lines[0] == ("# Nivesh capital gains working FY 2025-26 (rules in-cg-2026.1). Listed shares only. "
                        "Informational only; verify with a chartered accountant.")
    assert lines[1] == ("fy,term,section,rate_period,symbol,name,quantity,acquired_on,sold_on,sale_value_inr,"
                        "cost_of_acquisition_inr,fmv_31jan2018_per_unit,fmv_total_inr,cost_used_inr,transfer_expenses_inr,"
                        "gain_inr,needs_review,review_reasons")
    rows = list(csv.reader(io.StringIO("\n".join(lines[1:]))))
    assert len(rows) == 1 + 2   # header, one computed row, one not-computed row
    assert rows[1][4] == "INFY" and rows[1][15] == "1965.00" and rows[1][16] == "false"
    assert rows[2][4] == "HDFCBANK" and rows[2][15] == "" and rows[2][17] == "acquisition_date_uncertain"


def test_other_users_ledgers_are_not_included(client):
    uid, headers = _user()
    other, _ = _user()
    _tx(other, "INFY", "BUY", (2025, 5, 10), 10, 1000.0)
    _tx(other, "INFY", "SELL", (2025, 12, 1), 10, 1200.0)
    assert _get(client, headers).json()["rows"] == []
