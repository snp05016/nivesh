"""Money C11: GET /api/v1/me/holdings/{ticker}, the money router registry and the MF metadata seam.

Runs against the session test DB through the app client. Quotes
(_yf_price_with_status), past closes and Nifty are stubbed: no network.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest
from fastapi import APIRouter

import services.yfinance_client as yfc
from services import money_mf_meta, money_pricing, money_returns

LIVE_AS_OF = "2026-10-09T10:15:00+00:00"


def _user():
    import database
    from models.db_models import User

    with database.get_session() as session:
        user = User(username=f"hold_{uuid4().hex[:12]}", password_hash="x", display_name="Holding Test")
        session.add(user)
        session.commit()
        uid = int(user.id)  # type: ignore[arg-type]
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _seed(uid, ticker="INFY", shares=10.0, buy=1402.0, asset_class="EQ", ledger=True, journal=0):
    import database
    from models.db_models import Portfolio, TradeJournal, Transaction

    with database.get_session() as session:
        session.add(Portfolio(
            user_id=uid, ticker=ticker, company_name=f"{ticker} Ltd", shares=shares, buy_price=buy,
            group_name="holdings", asset_class=asset_class, notes="long term",
        ))
        if ledger:
            session.add_all([
                Transaction(user_id=uid, ticker=ticker, transaction_type="BUY", quantity=10, price=1400.0,
                            fees=20.0, date=datetime(2024, 2, 1, 5, 0), asset_class=asset_class),
                Transaction(user_id=uid, ticker=ticker, transaction_type="DIVIDEND", quantity=10, price=17.0,
                            date=datetime(2024, 8, 1, 5, 0), asset_class=asset_class),
            ])
        for i in range(journal):
            session.add(TradeJournal(
                user_id=uid, ticker=ticker, action="BUY", price_at_time=1400.0,
                reason_text=f"entry {i} " + "margins improving " * 20,
                created_at=datetime(2024, 1, 1 + i, 20, 0),  # 20:00 UTC = next day IST
            ))
        session.commit()


@pytest.fixture()
def stubs(monkeypatch):
    """Live price 1520.1, a Nifty series from 2024, no past closes."""
    quote = {"value": (1520.1, 1500.0, "live", LIVE_AS_OF)}
    monkeypatch.setattr(yfc, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(yfc, "_yf_price_with_status", lambda _sym: quote["value"])
    monkeypatch.setattr(money_pricing, "close_on", lambda _t, _d: None)
    today = money_returns.ist_today()
    monkeypatch.setattr(money_returns, "fetch_nifty_closes",
                        lambda _s: [(date(2024, 1, 31), 21000.0), (today, 25200.0)])
    return quote


def _get(client, ticker, headers):
    return client.get(f"/api/v1/me/holdings/{ticker}", headers=headers)


def test_holding_detail_shape(client, stubs):
    uid, headers = _user()
    _seed(uid, journal=6)

    r = _get(client, "infy", headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"ticker", "name", "asset_class", "position", "returns", "transactions", "dividends",
                         "notes", "target_price", "journal", "stock_report_available"}
    assert (body["ticker"], body["name"], body["asset_class"]) == ("INFY", "INFY Ltd", "EQ")
    assert body["position"] == {
        "quantity": 10.0, "avg_cost": 1402.0, "invested_inr": 14020.0, "price": 1520.1,
        "price_status": "live", "price_as_of": LIVE_AS_OF, "value_inr": 15201.0,
        "pnl_inr": 1181.0, "pnl_pct": 8.42,
    }
    ret = body["returns"]
    assert ret["basis"] == "annualized_xirr"
    assert ret["value_pct"] is not None and ret["nifty_same_flows_pct"] is not None
    assert ret["nifty_available"] is True
    assert ret["since"] == "2024-02-01"
    assert (ret["approximate_start"], ret["start_reason"], ret["unavailable_reason"]) == (False, None, None)
    assert ret["benchmark_label"] == "Nifty 50 price index (excludes dividends)"
    assert [t["type"] for t in body["transactions"]] == ["DIVIDEND", "BUY"]  # newest first
    buy = body["transactions"][1]
    assert (buy["quantity"], buy["price"], buy["fees"], buy["date"], buy["imported"]) == (10.0, 1400.0, 20.0, "2024-02-01", False)
    assert body["dividends"] == {"total_inr": 170.0, "count": 1}
    assert (body["notes"], body["target_price"], body["stock_report_available"]) == ("long term", None, True)
    assert len(body["journal"]) == 5
    assert body["journal"][0]["created_at"] == "2024-01-07"  # newest, IST date
    assert all(len(j["reason_excerpt"]) <= 140 for j in body["journal"])


def test_unpriced_holding_is_valued_at_cost(client, stubs):
    uid, headers = _user()
    _seed(uid)
    stubs["value"] = (None, None, "unavailable", None)

    body = _get(client, "INFY", headers).json()

    pos = body["position"]
    assert (pos["price"], pos["price_status"], pos["price_as_of"]) == (1402.0, "unavailable", None)
    assert (pos["value_inr"], pos["pnl_inr"], pos["pnl_pct"]) == (14020.0, 0.0, 0.0)
    assert body["returns"]["basis"] == "unavailable"
    assert body["returns"]["unavailable_reason"] == "price_unavailable"


def test_fund_holding_is_priced_at_nav_and_has_no_stock_report(client, stubs, monkeypatch):
    uid, headers = _user()
    isin = "INF179K01VC4"
    _seed(uid, ticker=isin, shares=100.0, buy=40.0, asset_class="MF", ledger=False)
    nav_day = money_returns.ist_today()
    monkeypatch.setattr(money_mf_meta, "scheme_info", lambda isins: {isin: money_mf_meta.SchemeInfo(
        isin=isin, amfi_code="119551", name="HDFC Flexi Cap Fund", amc="HDFC Mutual Fund", category="Equity",
        sub_category="Flexi Cap Fund", is_direct=True, nav=45.0, nav_date=nav_day)})

    body = _get(client, isin, headers).json()

    assert body["asset_class"] == "MF" and body["stock_report_available"] is False
    assert body["position"]["price_status"] == "nav"
    assert body["position"]["value_inr"] == 4500.0
    assert body["returns"]["unavailable_reason"] == "start_date_unknown"  # no purchase date entered


def test_not_held_and_invalid_ticker(client, stubs):
    uid, headers = _user()
    _seed(uid)

    r = _get(client, "TCS", headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "NOT_HELD"

    r = _get(client, "A" * 21, headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_TICKER"


def test_requires_auth(client, stubs):
    assert client.get("/api/v1/me/holdings/INFY").status_code == 401


def test_flag_off_is_feature_disabled(client, stubs, monkeypatch):
    uid, headers = _user()
    _seed(uid)
    monkeypatch.setenv("FEATURE_MONEY_HOLDING_DETAIL", "false")

    r = _get(client, "INFY", headers)

    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_other_users_holding_is_never_returned(client, stubs):
    owner, _ = _user()
    _seed(owner, ticker="WIPRO")
    _, other_headers = _user()

    r = _get(client, "WIPRO", other_headers)

    assert r.status_code == 404 and r.json()["detail"]["code"] == "NOT_HELD"


def test_benchmark_rejects_another_users_id(client):
    owner, _ = _user()
    _, other_headers = _user()

    r = client.get("/portfolio/benchmark", params={"user_id": owner}, headers=other_headers)

    assert r.status_code == 403  # FIX ARCH-02


# ---------------------------------------------------------------------------
# MF metadata seam
# ---------------------------------------------------------------------------

def test_scheme_info_is_empty_without_the_instrument_table():
    import models.db_models as db_models

    if hasattr(db_models, "Instrument"):
        pytest.skip("Instrument exists; covered by test_scheme_info_maps_a_seeded_fund")
    assert money_mf_meta.scheme_info(["INF179K01VC4"]) == {}
    assert money_mf_meta.scheme_info([]) == {}


def test_scheme_info_maps_a_seeded_fund():
    import database
    import models.db_models as db_models

    Instrument = getattr(db_models, "Instrument", None)
    if Instrument is None:
        pytest.skip("data-instruments has not landed")
    code, isin, isin_alt = f"9{uuid4().int % 10**6:06d}", "INF000T01AB1", "INF000T01AC9"
    with database.get_session() as session:
        session.add(db_models.MutualFund(
            fund_name="Test Flexi Cap Fund - Direct Plan - Growth", amc="Test MF", category="Equity",
            scheme_code=code, scheme_name="Test Flexi Cap Fund - Direct Plan - Growth", amc_name="Test MF",
            sub_category="Flexi Cap Fund", nav=45.67, nav_date="2026-10-08", is_direct_plan=True,
        ))
        fields = {"asset_class": "MF", "symbol": None, "isin": isin, "isin_alt": isin_alt,
                  "amfi_scheme_code": code, "name": "Test Flexi Cap Fund", "source": "amfi",
                  "status": "active", "last_seen_on": date(2026, 10, 8)}
        session.add(Instrument(**{k: v for k, v in fields.items() if hasattr(Instrument, k)}))
        session.commit()

    info = money_mf_meta.scheme_info([isin, isin_alt, "INF000T01ZZ9"])

    assert set(info) == {isin, isin_alt}
    s = info[isin_alt]
    assert (s.isin, s.amfi_code, s.amc, s.category, s.is_direct, s.nav) == (isin_alt, code, "Test MF", "Equity", True, 45.67)
    assert s.nav_date == date(2026, 10, 8)


# ---------------------------------------------------------------------------
# routers/money.py registry
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_pkg(tmp_path, monkeypatch):
    name = f"money_fake_{uuid4().hex[:8]}"
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "good.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.get('/fake-good')\ndef good():\n    return {}\n"
    )
    (pkg / "broken_dep.py").write_text("import money_fake_dependency_that_does_not_exist\nrouter = None\n")
    (pkg / "broken_name.py").write_text("from fastapi import NoSuchThing\nrouter = None\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


def test_registry_skips_absent_modules_and_includes_present_ones(fake_pkg):
    from routers.money import include_feature

    target = APIRouter()
    assert include_feature(target, "missing", fake_pkg) is False
    assert include_feature(target, "good", fake_pkg) is True
    assert "/fake-good" in {getattr(r, "path", None) for r in target.routes}


def test_registry_reraises_import_errors_inside_a_module(fake_pkg):
    from routers.money import include_feature

    with pytest.raises(ModuleNotFoundError) as exc:
        include_feature(APIRouter(), "broken_dep", fake_pkg)
    assert exc.value.name == "money_fake_dependency_that_does_not_exist"
    with pytest.raises(ImportError):
        include_feature(APIRouter(), "broken_name", fake_pkg)


def test_money_router_is_mounted_once():
    from main import app

    paths = [getattr(r, "path", None) for r in app.routes]
    assert paths.count("/api/v1/me/holdings/{ticker}") == 1


def test_ledger_dates_are_ist(client, stubs):
    """A BUY recorded at 20:00 UTC belongs to the next IST calendar day."""
    import database
    from models.db_models import Transaction

    uid, headers = _user()
    _seed(uid, ledger=False)
    with database.get_session() as session:
        session.add(Transaction(user_id=uid, ticker="INFY", transaction_type="BUY", quantity=10, price=1400.0,
                                fees=20.0, date=datetime(2024, 2, 1, 20, 0)))
        session.commit()

    body = _get(client, "INFY", headers).json()

    assert body["transactions"][0]["date"] == "2024-02-02"
    assert body["returns"]["since"] == "2024-02-02"
