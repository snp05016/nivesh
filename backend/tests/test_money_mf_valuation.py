"""money-mf-valuation: funds valued at NAV, served only to MF-aware clients, and snapshotted."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest

import database
import services.yfinance_client as yfc
from models.db_models import Portfolio, PortfolioValuationHistory, User
from services import money_mf_meta, money_pricing

ISIN = "INF179K01VC4"
LIVE = "2026-10-09T10:15:00+00:00"
TODAY = date(2026, 10, 14)  # a Wednesday


def _user():
    with database.get_session() as session:
        user = User(username=f"mfval_{uuid4().hex[:12]}", password_hash="x", display_name="MF Val")
        session.add(user)
        session.commit()
        uid = int(user.id)
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _seed(uid, with_fund=True):
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker="INFY", company_name="Infosys", shares=10, buy_price=1400.0,
                              group_name="holdings", asset_class="EQ"))
        if with_fund:
            session.add(Portfolio(user_id=uid, ticker=ISIN, company_name="HDFC Flexi Cap", shares=100.0,
                                  buy_price=40.0, group_name="holdings", asset_class="MF"))
        session.commit()


def _scheme(nav=50.0, nav_date=None):
    return money_mf_meta.SchemeInfo(
        isin=ISIN, amfi_code="118955", name="HDFC Flexi Cap", amc="HDFC Mutual Fund", category="Equity",
        sub_category="Flexi Cap", is_direct=True, nav=nav, nav_date=nav_date or TODAY,
    )


@pytest.fixture
def quotes(monkeypatch):
    monkeypatch.setattr(yfc, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(yfc, "_yf_price_with_status", lambda _s: (1520.0, 1500.0, "live", LIVE))
    import routers.portfolio as rp

    monkeypatch.setattr(rp, "_yf_price_with_status", lambda _s: (1520.0, 1500.0, "live", LIVE))
    monkeypatch.setattr(money_pricing, "ist_today", lambda *_a: TODAY)
    state = {"schemes": {ISIN: _scheme()}}
    monkeypatch.setattr(money_mf_meta, "scheme_info", lambda isins: {i: state["schemes"][i] for i in isins if i in state["schemes"]})
    return state


def _get(client, uid, headers, aware=True):
    h = dict(headers)
    if aware:
        h["X-Client-Features"] = "other, asset_class"
    return client.get(f"/portfolio/{uid}", headers=h)


def test_unaware_client_never_sees_funds(client, quotes):
    uid, headers = _user()
    _seed(uid)
    body = _get(client, uid, headers, aware=False).json()
    assert [h["ticker"] for h in body["holdings"]] == ["INFY"]
    assert body["holdings"][0]["asset_class"] == "EQ"
    assert body["total_invested_inr"] == 14000.0


def test_aware_client_gets_fund_at_nav(client, quotes):
    uid, headers = _user()
    _seed(uid)
    body = _get(client, uid, headers).json()
    fund = next(h for h in body["holdings"] if h["ticker"] == ISIN)
    assert fund["asset_class"] == "MF"
    assert fund["price_status"] == "nav" and fund["price_as_of"] == TODAY.isoformat()
    assert fund["current_value_inr"] == 5000.0 and fund["invested_inr"] == 4000.0 and fund["pnl_inr"] == 1000.0
    assert body["unpriced_tickers"] == []
    assert body["total_current_inr"] == 15200.0 + 5000.0


def test_stale_and_missing_nav(client, quotes):
    uid, headers = _user()
    _seed(uid)
    quotes["schemes"][ISIN] = _scheme(nav_date=TODAY - timedelta(days=5))  # 3 weekdays: still fresh
    assert next(h for h in _get(client, uid, headers).json()["holdings"] if h["ticker"] == ISIN)["price_status"] == "nav"
    quotes["schemes"][ISIN] = _scheme(nav_date=TODAY - timedelta(days=7))  # 5 weekdays: stale
    fund = next(h for h in _get(client, uid, headers).json()["holdings"] if h["ticker"] == ISIN)
    assert fund["price_status"] == "stale"

    quotes["schemes"].clear()
    body = _get(client, uid, headers).json()
    fund = next(h for h in body["holdings"] if h["ticker"] == ISIN)
    assert fund["price_status"] == "unavailable" and fund["current_value_inr"] == 4000.0 and fund["pnl_inr"] == 0.0
    assert ISIN in body["unpriced_tickers"]


def test_stock_only_user_unchanged(client, quotes):
    uid, headers = _user()
    _seed(uid, with_fund=False)
    plain = _get(client, uid, headers, aware=False).json()
    aware = _get(client, uid, headers, aware=True).json()
    strip = lambda b: {k: v for k, v in b.items() if k != "as_of"}  # noqa: E731
    assert strip(plain) == strip(aware)
    assert plain["holdings"][0]["current_value_inr"] == 15200.0


@pytest.fixture
def run_snapshot(monkeypatch, quotes):
    import services.portfolio_snapshot as snap

    empty = SimpleNamespace(history=lambda **_kw: pd.DataFrame())
    monkeypatch.setattr(snap.yf, "Ticker", lambda _sym: empty)
    monkeypatch.setattr(snap, "get_current_price", lambda t: {"INFY": 1520.0}.get(t))

    def _run(day):
        class _Frozen(date):
            @classmethod
            def today(cls):
                return day

        monkeypatch.setattr(snap, "date", _Frozen)
        asyncio.run(snap.snapshot_all_users())

    return _run


def test_snapshot_values_fund_at_nav(run_snapshot, quotes):
    uid, _ = _user()
    _seed(uid)
    run_snapshot(date(2026, 10, 9))
    with database.get_session() as session:
        row = session.query(PortfolioValuationHistory).filter_by(user_id=uid).one()
    assert row.total_value == 15200.0 + 5000.0
    assert row.total_invested == 14000.0 + 4000.0


def test_snapshot_skips_user_when_fund_nav_unknown(run_snapshot, quotes):
    """A fund with no NAV counts as unpriced: with a recent snapshot already stored, today's is skipped."""
    uid, _ = _user()
    _seed(uid)
    with database.get_session() as session:
        session.add(PortfolioValuationHistory(user_id=uid, snapshot_date="2026-10-08", total_value=1.0,
                                              total_invested=1.0, total_pnl=0.0, pnl_percent=0.0))
        session.commit()
    quotes["schemes"].clear()
    run_snapshot(date(2026, 10, 9))
    with database.get_session() as session:
        assert session.query(PortfolioValuationHistory).filter_by(user_id=uid).count() == 1
