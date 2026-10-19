"""money-commission-drag: validated TER rows, the 45-day rule and the X-ray block (no network)."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

import database
from models.db_models import Portfolio, User
from services import money_commission as mc
from services import money_mf_meta, money_pricing

TODAY = date(2026, 10, 12)
REG, DIR_ = "INF846K01DP8", "INF846K01EW1"
REG2, DIR2 = "INF109K01Z48", "INF109K01Z55"
HEADER = "regular_isin,direct_isin,scheme_name,amc,regular_ter_pct,direct_ter_pct,as_of,source_url\n"


@pytest.fixture(autouse=True)
def clear_cache():
    mc.load_rows.cache_clear()
    yield
    mc.load_rows.cache_clear()


def _csv(tmp_path: Path, *lines: str) -> str:
    path = tmp_path / f"ter_{uuid4().hex[:6]}.csv"
    path.write_text(HEADER + "".join(line + "\n" for line in lines))
    return str(path)


def _fund(isin, value, direct=False, name="Fund"):
    return {"isin": isin, "name": name, "value_inr": value, "is_direct": direct}


def test_shipped_csv_is_header_only_and_unavailable():
    assert mc.load_rows(str(mc.CSV_PATH)) == ()
    assert mc.commission_drag([_fund(REG, 100000)], today=TODAY) == {"available": False, "reason": "ter_data_missing"}


def test_gap_and_annual_cost(tmp_path):
    path = _csv(tmp_path, f"{REG},{DIR_},Axis Bluechip,Axis,1.60,1.00,2026-09-30,")
    out = mc.commission_drag([_fund(REG, 100000.0, name="Axis Bluechip Fund")], path=path, today=TODAY)
    assert out["available"] is True and out["as_of"] == "2026-09-30"
    assert out["source"] == "AMC expense-ratio disclosures"
    assert out["source_url"] == "https://www.amfiindia.com/ter-of-mf-schemes"
    assert out["total_annual_cost_inr"] == 600.0 and out["uncovered_regular_funds"] == 0
    assert out["funds"] == [{"isin": REG, "name": "Axis Bluechip Fund", "value_inr": 100000.0, "regular_ter_pct": 1.6,
                             "direct_ter_pct": 1.0, "gap_pp": 0.6, "annual_cost_inr": 600.0}]


def test_uncovered_direct_and_unknown_plans(tmp_path):
    path = _csv(tmp_path, f"{REG},{DIR_},Axis Bluechip,Axis,1.60,1.00,2026-09-30,")
    funds = [_fund(REG, 100000.0), _fund(REG2, 50000.0), _fund(DIR_, 70000.0, direct=True), _fund("INF000000000", 1.0, direct=None)]
    out = mc.commission_drag(funds, path=path, today=TODAY)
    assert out["uncovered_regular_funds"] == 1 and len(out["funds"]) == 1


def test_no_regular_funds_is_unavailable(tmp_path):
    path = _csv(tmp_path, f"{REG},{DIR_},Axis Bluechip,Axis,1.60,1.00,2026-09-30,")
    assert mc.commission_drag([_fund(DIR_, 1000.0, direct=True)], path=path, today=TODAY) == {
        "available": False, "reason": "no_regular_funds"}


def test_stale_file_hides_the_card(tmp_path):
    old = (TODAY - timedelta(days=46)).isoformat()
    path = _csv(tmp_path, f"{REG},{DIR_},Axis,Axis,1.60,1.00,{old},")
    assert mc.commission_drag([_fund(REG, 1000.0)], path=path, today=TODAY) == {"available": False, "reason": "ter_data_stale"}
    fresh = (TODAY - timedelta(days=45)).isoformat()
    path = _csv(tmp_path, f"{REG},{DIR_},Axis,Axis,1.60,1.00,{fresh},")
    assert mc.commission_drag([_fund(REG, 1000.0)], path=path, today=TODAY)["available"] is True


def test_invalid_rows_are_skipped(tmp_path):
    future = (date.today() + timedelta(days=30)).isoformat()
    path = _csv(
        tmp_path,
        f"BAD,{DIR_},x,Axis,1.60,1.00,2026-09-30,",                    # bad ISIN
        f"{REG},{DIR_},x,Axis,1.00,1.60,2026-09-30,",                  # direct > regular
        f"{REG},{DIR_},x,Axis,3.50,1.00,2026-09-30,",                  # TER above 3
        f"{REG},{DIR_},x,Axis,0,0,2026-09-30,",                        # not positive
        f"{REG},{DIR_},x,Axis,1.6,1.0,{future},",                      # as_of in the future
        f"{REG},{DIR_},x,Axis,abc,1.0,2026-09-30,",                    # not a number
        f"{REG},{DIR_},x,Axis,1.6,1.0,30-09-2026,",                    # bad date
        f"{REG2},{DIR2},Good,ICICI,1.50,0.90,2026-09-29,",
    )
    rows = mc.load_rows(path)
    assert [r["regular_isin"] for r in rows] == [REG2]


def test_missing_file_is_unavailable(tmp_path):
    assert mc.commission_drag([_fund(REG, 1000.0)], path=str(tmp_path / "nope.csv"), today=TODAY)["reason"] == "ter_data_missing"


# --- X-ray integration --------------------------------------------------------------------------

def _user():
    with database.get_session() as session:
        user = User(username=f"drag_{uuid4().hex[:12]}", password_hash="x", display_name="Drag")
        session.add(user)
        session.commit()
        uid = int(user.id)
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


@pytest.fixture
def xray_world(monkeypatch, tmp_path):
    monkeypatch.setenv("FEATURE_MONEY_XRAY", "true")
    path = _csv(tmp_path, f"{REG},{DIR_},Axis Bluechip,Axis,1.60,1.00,{date.today().isoformat()},")
    monkeypatch.setattr(mc, "CSV_PATH", Path(path))
    monkeypatch.setattr(money_pricing, "price_quotes",
                        lambda rows: {t: money_pricing.PriceQuote(20.0, None, "nav", None) for t, _ in rows})
    scheme = money_mf_meta.SchemeInfo(isin=REG, amfi_code="1", name="Axis Bluechip Fund", amc="Axis Mutual Fund",
                                      category="Equity", sub_category=None, is_direct=False, nav=20.0, nav_date=None)
    monkeypatch.setattr(money_mf_meta, "scheme_info", lambda isins: {i: scheme for i in isins if i == REG})
    uid, headers = _user()
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker=REG, company_name="Axis", shares=5000, buy_price=15.0,
                              group_name="holdings", asset_class="MF"))
        session.commit()
    return uid, headers


def test_xray_drag_null_with_flag_off(client, xray_world, monkeypatch):
    monkeypatch.delenv("FEATURE_MONEY_COMMISSION_DRAG", raising=False)
    _, headers = xray_world
    assert client.get("/api/v1/me/portfolio/xray", headers=headers).json()["commission_drag"] is None


def test_xray_drag_filled_with_flag_on(client, xray_world, monkeypatch):
    monkeypatch.setenv("FEATURE_MONEY_COMMISSION_DRAG", "true")
    _, headers = xray_world
    # the module reads CSV_PATH at call time through load_rows' default argument; clear the cache for the patched path
    mc.load_rows.cache_clear()
    drag = client.get("/api/v1/me/portfolio/xray", headers=headers).json()["commission_drag"]
    assert drag["available"] is True
    assert drag["total_annual_cost_inr"] == 600.0  # 100,000 x 0.6 points
    assert drag["funds"][0]["isin"] == REG
