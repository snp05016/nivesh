"""Portfolio X-ray (I28): buckets, AMC and plan mix, concentration and fixed-template facts."""
from __future__ import annotations

from uuid import uuid4

import pytest

import database
from models.db_models import Portfolio, User
from services import money_mf_meta, money_pricing

HDFC, AXIS, ICICI = "INF179K01VC4", "INF846K01DP8", "INF109K01Z48"


def _user():
    with database.get_session() as session:
        user = User(username=f"xray_{uuid4().hex[:12]}", password_hash="x", display_name="Xray")
        session.add(user)
        session.commit()
        uid = int(user.id)
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _hold(uid, ticker, shares, buy, ac="EQ", name=None):
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker=ticker, company_name=name or ticker, shares=shares, buy_price=buy,
                              group_name="holdings", asset_class=ac))
        session.commit()


def _scheme(isin, name, amc, category, direct):
    return money_mf_meta.SchemeInfo(isin=isin, amfi_code="1", name=name, amc=amc, category=category,
                                    sub_category=None, is_direct=direct, nav=10.0, nav_date=None)


@pytest.fixture
def market(monkeypatch):
    monkeypatch.setenv("FEATURE_MONEY_XRAY", "true")
    state = {
        "prices": {"INFY": 100.0, "TCS": 200.0, HDFC: 50.0, AXIS: 20.0, ICICI: 10.0},
        "schemes": {
            HDFC: _scheme(HDFC, "HDFC Flexi Cap Fund", "HDFC Mutual Fund", "Equity", True),
            AXIS: _scheme(AXIS, "Axis Bluechip Fund", "Axis Mutual Fund", "Equity", False),
            ICICI: _scheme(ICICI, "ICICI Prudential Short Term Fund", "ICICI Prudential Mutual Fund", "Debt", True),
        },
    }

    def quotes(rows):
        return {t: (money_pricing.PriceQuote(state["prices"][t], None, "live", None) if t in state["prices"]
                    else money_pricing.UNAVAILABLE) for t, _ac in rows}

    monkeypatch.setattr(money_pricing, "price_quotes", quotes)
    monkeypatch.setattr(money_mf_meta, "scheme_info", lambda isins: {i: state["schemes"][i] for i in isins if i in state["schemes"]})
    return state


def _get(client, headers):
    return client.get("/api/v1/me/portfolio/xray", headers=headers)


def test_flag_off_is_404(client, monkeypatch):
    monkeypatch.delenv("FEATURE_MONEY_XRAY", raising=False)
    _, headers = _user()
    r = _get(client, headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_requires_auth(client, market):
    assert client.get("/api/v1/me/portfolio/xray").status_code == 401


def test_mixed_portfolio(client, market):
    uid, headers = _user()
    _hold(uid, "INFY", 10, 90.0, name="Infosys Ltd")        # 1000
    _hold(uid, "TCS", 5, 150.0, name="TCS Ltd")             # 1000
    _hold(uid, HDFC, 20, 40.0, "MF", "HDFC Flexi Cap")      # 1000 direct equity
    _hold(uid, AXIS, 50, 15.0, "MF", "Axis Bluechip")       # 1000 regular equity
    _hold(uid, ICICI, 200, 9.0, "MF", "ICICI Short Term")   # 2000 direct debt
    body = _get(client, headers).json()

    assert body["total_value_inr"] == 6000.0
    assert [(a["key"], a["value_inr"], a["pct"]) for a in body["allocation"]] == [
        ("stocks", 2000.0, 33.3), ("equity_funds", 2000.0, 33.3), ("debt_funds", 2000.0, 33.3)]
    assert body["allocation"][1]["label"] == "Equity funds"
    assert [(a["name"], a["pct"]) for a in body["amcs"]] == [
        ("ICICI Prudential Mutual Fund", 50.0), ("Axis Mutual Fund", 25.0), ("HDFC Mutual Fund", 25.0)]
    assert body["plans"] == {"direct_pct": 75.0, "regular_pct": 25.0, "unknown_pct": 0.0}
    assert body["top_holdings"][0] == {"ticker": ICICI, "name": "ICICI Prudential Short Term Fund",
                                       "asset_class": "MF", "value_inr": 2000.0, "pct": 33.3}
    assert body["concentration"] == {"largest_ticker": ICICI, "largest_pct": 33.3, "top5_pct": 100.0}
    assert [f["code"] for f in body["facts"]] == ["largest_holding_share", "top5_share", "regular_plan_share"]
    assert body["facts"][0]["text"] == "Your largest holding, ICICI Prudential Short Term Fund, is 33% of your portfolio."
    assert body["facts"][1]["text"] == "Your five largest holdings are 100% of your portfolio."
    assert body["facts"][2]["text"] == "25% of your fund value is in regular plans."
    assert body["unpriced"] == [] and body["commission_drag"] is None
    assert body["as_of"].endswith("Z")


def test_empty_portfolio(client, market):
    _, headers = _user()
    body = _get(client, headers).json()
    assert body["total_value_inr"] == 0.0
    assert body["allocation"] == [] and body["amcs"] == [] and body["top_holdings"] == []
    assert body["plans"] is None and body["facts"] == []
    assert body["concentration"] == {"largest_ticker": None, "largest_pct": 0.0, "top5_pct": 0.0}


def test_unpriced_holding_counted_at_cost_and_listed(client, market):
    uid, headers = _user()
    _hold(uid, "INFY", 10, 100.0, name="Infosys Ltd")   # 1000 live
    _hold(uid, "ZZZ", 10, 50.0, name="Zed Ltd")         # no quote: 500 at cost
    body = _get(client, headers).json()
    assert body["total_value_inr"] == 1500.0
    assert body["unpriced"] == [{"ticker": "ZZZ", "name": "Zed Ltd"}]
    assert body["facts"][-1] == {"code": "unpriced_count", "text": "1 holdings have no current price and are counted at cost."}


def test_no_scheme_metadata_means_unclassified_and_unknown_plans(client, market):
    uid, headers = _user()
    market["schemes"].clear()
    market["prices"][HDFC] = 50.0
    _hold(uid, HDFC, 20, 40.0, "MF", "HDFC Flexi Cap")
    body = _get(client, headers).json()
    assert [a["key"] for a in body["allocation"]] == ["unclassified_funds"]
    assert body["allocation"][0]["label"] == "Funds (category unknown)"
    assert body["plans"] == {"direct_pct": 0.0, "regular_pct": 0.0, "unknown_pct": 100.0}
    assert body["amcs"][0]["name"] == "AMC unknown"
    assert not any(f["code"] == "regular_plan_share" for f in body["facts"])
    assert body["top_holdings"][0]["name"] == "HDFC Flexi Cap"


def test_other_funds_bucket(client, market):
    uid, headers = _user()
    market["schemes"][HDFC] = _scheme(HDFC, "Index Fund", "HDFC Mutual Fund", "Solution Oriented", True)
    _hold(uid, HDFC, 20, 40.0, "MF")
    body = _get(client, headers).json()
    assert body["allocation"][0]["key"] == "other_funds"
    assert body["allocation"][0]["label"] == "Index funds & other funds"


def test_other_users_holdings_not_included(client, market):
    uid, headers = _user()
    other, _ = _user()
    _hold(other, "INFY", 10, 90.0)
    assert _get(client, headers).json()["total_value_inr"] == 0.0
