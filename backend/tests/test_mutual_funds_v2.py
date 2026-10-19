"""Mutual-fund API on the real AMFI universe: paging, Direct/Growth defaults, filters, detail, NAV history."""
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import require_auth
from core.timeutil import ist_today
from models.db_models import DailyPrice, Instrument, MutualFund
from routers import mutual_funds as mf_router
from services import mutual_fund_service
from tests.data_db import patch_get_session

TODAY = ist_today()


@pytest.fixture
def db(monkeypatch):
    factory = patch_get_session(monkeypatch, mutual_fund_service)
    with factory() as s:
        yield s


@pytest.fixture
def api(db):
    app = FastAPI()
    app.include_router(mf_router.router, prefix="/api/mutual-funds")
    app.dependency_overrides[require_auth] = lambda: 1
    return TestClient(app)


def _fund(db, code, name, *, direct=True, growth=True, scheme_type="open", category="Equity", sub="Large Cap Fund",
          amc="Alpha Mutual Fund", isin=None, isin_alt=None, nav_date=None, **kw):
    db.add(MutualFund(
        scheme_code=code, scheme_name=name, fund_name=name, amc_name=amc, amc=amc, category=category,
        sub_category=sub, is_direct_plan=direct, is_growth_plan=growth, scheme_type=scheme_type, nav=10.0,
        nav_date=nav_date or TODAY.isoformat(), nav_source="amfi", is_active=True, **kw))
    db.add(Instrument(asset_class="MF", amfi_scheme_code=code, isin=isin, isin_alt=isin_alt, name=name,
                      source="amfi", status="active"))
    db.commit()


@pytest.fixture
def funds(db):
    _fund(db, "100", "Zeta Direct Growth", isin="INF000Z01011", isin_alt="INF000Z01029")
    _fund(db, "101", "alpha Direct Growth")
    _fund(db, "102", "Beta Regular Growth", direct=False)
    _fund(db, "103", "Gamma Direct IDCW", growth=False)
    _fund(db, "104", "Delta Closed Direct Growth", scheme_type="close")
    _fund(db, "105", "Epsilon Debt Direct Growth", category="Debt", sub="Liquid Fund", amc="Beta Mutual Fund")
    _fund(db, "106", "Stale Direct Growth", nav_date=(TODAY - timedelta(days=120)).isoformat())
    db.add(MutualFund(scheme_code="107", scheme_name="Inactive", fund_name="Inactive", amc_name="x", amc="x",
                      category="Equity", is_direct_plan=True, is_growth_plan=True, scheme_type="open",
                      is_active=False))
    db.commit()


def names(resp):
    return [r["scheme_name"] for r in resp.json()]


def test_default_list_is_direct_growth_open_active_sorted(api, funds):
    resp = api.get("/api/mutual-funds/")
    assert resp.status_code == 200
    assert names(resp) == ["alpha Direct Growth", "Epsilon Debt Direct Growth", "Zeta Direct Growth"]
    assert resp.headers["X-Total-Count"] == "3"


def test_paging_and_widening(api, funds):
    page = api.get("/api/mutual-funds/", params={"limit": 2, "offset": 1})
    assert names(page) == ["Epsilon Debt Direct Growth", "Zeta Direct Growth"]
    assert page.headers["X-Total-Count"] == "3"
    wide = api.get("/api/mutual-funds/", params={"plan": "all", "option": "all", "scheme_type": "all"})
    assert wide.headers["X-Total-Count"] == "6"  # stale and inactive stay hidden
    assert api.get("/api/mutual-funds/", params={"limit": 201}).status_code == 422
    assert api.get("/api/mutual-funds/", params={"offset": 20001}).status_code == 422


def test_category_and_amc_filters(api, funds):
    assert names(api.get("/api/mutual-funds/", params={"category": "Debt"})) == ["Epsilon Debt Direct Growth"]
    assert names(api.get("/api/mutual-funds/", params={"sub_category": "Liquid Fund"})) == ["Epsilon Debt Direct Growth"]
    assert names(api.get("/api/mutual-funds/", params={"amc_name": "Beta Mutual Fund"})) == ["Epsilon Debt Direct Growth"]


def test_isin_code_and_name_search(api, funds):
    assert names(api.get("/api/mutual-funds/", params={"search": "INF000Z01029"})) == ["Zeta Direct Growth"]
    assert names(api.get("/api/mutual-funds/", params={"search": "INF000Z01011"})) == ["Zeta Direct Growth"]
    assert names(api.get("/api/mutual-funds/", params={"search": "101"})) == ["alpha Direct Growth"]
    assert names(api.get("/api/mutual-funds/", params={"search": "debt"})) == ["Epsilon Debt Direct Growth"]
    assert api.get("/api/mutual-funds/", params={"search": "%"}).json() == []


def test_filters_shape(api, funds):
    body = api.get("/api/mutual-funds/filters").json()
    assert body["categories"]["Equity"] == ["Large Cap Fund"]
    assert body["categories"]["Debt"] == ["Liquid Fund"]
    assert body["amcs"] == ["Alpha Mutual Fund", "Beta Mutual Fund"]


def test_detail_has_isins_history_start_and_marks_tracked(api, funds, db):
    inst = db.query(Instrument).filter_by(amfi_scheme_code="100").one()
    db.add(DailyPrice(instrument_id=inst.id, trade_date=TODAY - timedelta(days=3), close=10, source="amfi",
                      ingested_at=datetime(2026, 1, 1)))
    db.commit()
    body = api.get("/api/mutual-funds/100").json()
    assert body["isin_growth"] == "INF000Z01011" and body["isin_reinvest"] == "INF000Z01029"
    assert body["history_start"] == (TODAY - timedelta(days=3)).isoformat()
    assert body["nav_source"] == "amfi" and body["scheme_type"] == "open" and body["is_sample"] is False
    db.expire_all()
    assert db.query(MutualFund).filter_by(scheme_code="100").one().track_nav is True
    assert api.get("/api/mutual-funds/nope").status_code == 404


def test_amfi_detail_has_null_returns(api, funds):
    body = api.get("/api/mutual-funds/101").json()
    assert body["returns_1y"] is None and body["returns_3y"] is None and body["returns_5y"] is None


def test_nav_history_from_daily_prices_and_flag_off(api, funds, db, monkeypatch):
    inst = db.query(Instrument).filter_by(amfi_scheme_code="100").one()
    for offset, nav in ((1, 12.5), (3, 12.0)):
        db.add(DailyPrice(instrument_id=inst.id, trade_date=TODAY - timedelta(days=offset), close=nav,
                          source="amfi", ingested_at=datetime(2026, 1, 1)))
    db.add(DailyPrice(instrument_id=inst.id, trade_date=TODAY - timedelta(days=60), close=9, source="amfi",
                      ingested_at=datetime(2026, 1, 1)))
    db.commit()
    points = api.get("/api/mutual-funds/100/nav-history", params={"days": 30}).json()
    assert points == [{"date": (TODAY - timedelta(days=3)).isoformat(), "nav": 12.0},
                      {"date": (TODAY - timedelta(days=1)).isoformat(), "nav": 12.5}]
    monkeypatch.setenv("FEATURE_DATA_MF_UNIVERSE", "false")
    assert api.get("/api/mutual-funds/100/nav-history").json() == []
    assert api.get("/api/mutual-funds/nope/nav-history").status_code == 404


def test_days_over_365_rejected(api, funds):
    assert api.get("/api/mutual-funds/100/nav-history", params={"days": 400}).status_code == 422
