"""Results digest (I25): RSS parsing, symbol/period resolution, the jobs and the endpoint. Hermetic."""
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import require_auth
from models.db_models import Instrument, Portfolio, ResultsDigest, User, Watchlist
from routers import results_digest as digest_router
from services import results_digest as rd
from tests.data_db import patch_get_session

BACKEND = Path(__file__).resolve().parent.parent
FEED = (Path(__file__).parent / "fixtures" / "nse_financial_results_rss.xml").read_bytes()
FLAG_ENV = "FEATURE_DATA_RESULTS_DIGEST"
PERIOD = date(2026, 9, 30)


@pytest.fixture
def db(monkeypatch):
    factory = patch_get_session(monkeypatch)
    monkeypatch.delenv(FLAG_ENV, raising=False)
    monkeypatch.delenv(FLAG_ENV + "_USERS", raising=False)
    monkeypatch.setattr(rd, "_feed_state", {"etag": None, "last_modified": None})
    with factory() as s:
        s.add(User(id=1, username="u1", password_hash="x", display_name="U"))
        s.commit()
        yield s


def _eq(db, symbol, name):
    db.add(Instrument(asset_class="EQ", symbol=symbol, name=name, source="t", status="active", series="EQ"))
    db.commit()


def test_source_has_no_generated_text_or_private_api():
    for rel in ("services/results_digest.py", "routers/results_digest.py"):
        text = (BACKEND / rel).read_text()
        assert not re.search(r"^\s*(import|from)\s+\S*(llm|anthropic|openai|deepseek)", text, re.I | re.M), rel
        assert "nseindia.com/api" not in text, rel


def test_parse_reads_both_items_and_skips_malformed():
    items = rd.parse_feed(FEED)
    assert [i["title"] for i in items] == ["Infosys Limited - Financial Results", "Tata Consultancy Services Limited"]
    assert items[0]["published"].utcoffset() == timedelta(hours=5, minutes=30)
    assert rd.parse_feed(b"<not-xml") == []
    assert rd.parse_feed(b'<!DOCTYPE x [<!ENTITY a "b">]><rss/>') == []


def test_period_from_description_and_fallback():
    first, second = rd.parse_feed(FEED)
    assert rd.item_period_end(first) == date(2026, 9, 30)
    assert rd.item_period_end(second) == date(2026, 9, 30)  # fallback: last quarter end before 16 Oct
    future = dict(first, description="for the quarter ended 31-Dec-2026")  # after the publish date: ignored
    assert rd.item_period_end(future) == date(2026, 9, 30)
    july = dict(second, published=datetime(2026, 7, 10, tzinfo=timezone.utc))
    assert rd.item_period_end(july) == date(2026, 6, 30)


def test_symbol_via_link_name_and_ambiguity(db):
    first, second = rd.parse_feed(FEED)
    assert rd.item_symbol(first, db) == "INFY"  # from the link parameter
    assert rd.item_symbol(second, db) is None   # unknown company
    _eq(db, "TCS", "Tata Consultancy Services Ltd.")
    assert rd.item_symbol(second, db) == "TCS"
    _eq(db, "TCS2", "TATA CONSULTANCY SERVICES LIMITED")
    assert rd.item_symbol(second, db) is None   # two rows share the name


def _hold(db, symbol, watch=False):
    if watch:
        db.add(Watchlist(user_id=1, ticker=symbol))
    else:
        db.add(Portfolio(user_id=1, ticker=symbol, company_name=symbol, shares=1, buy_price=1, group_name="holdings"))
    db.commit()


def test_poll_keeps_only_held_or_watched_and_is_idempotent(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    monkeypatch.setattr(rd, "fetch_feed", lambda: FEED)
    _eq(db, "TCS", "Tata Consultancy Services Limited")
    _hold(db, "INFY.NS")
    assert rd.poll_feed_job() == {"items": 2, "inserted": 1, "unmatched": 1}
    row = db.query(ResultsDigest).one()
    assert (row.symbol, row.period_end, row.numbers_status) == ("INFY", PERIOD, "pending")
    assert row.filing_url.endswith("?symbol=INFY") and row.announced_at == datetime(2026, 10, 16, 12, 0)
    assert rd.poll_feed_job()["inserted"] == 0
    _hold(db, "TCS", watch=True)
    assert rd.poll_feed_job()["inserted"] == 1
    assert db.query(ResultsDigest).count() == 2


def test_poll_flag_rules(db, monkeypatch):
    monkeypatch.setattr(rd, "fetch_feed", lambda: FEED)
    _hold(db, "INFY")
    assert rd.poll_feed_job() == {"skipped": "flag_off"}
    monkeypatch.setenv(FLAG_ENV + "_USERS", "1")
    assert rd.poll_feed_job()["inserted"] == 1
    monkeypatch.setattr(rd, "fetch_feed", lambda: None)
    assert rd.poll_feed_job() == {"status": "not_modified"}


def _frame(cur_date="2026-09-30", prev_date="2025-09-30", cur=(1000.0, 200.0, 5.5), prev=(800.0, 100.0, 4.0)):
    cols = [pd.Timestamp(cur_date), pd.Timestamp(prev_date)]
    return pd.DataFrame(
        {cols[0]: [cur[0], cur[1], cur[2]], cols[1]: [prev[0], prev[1], prev[2]]},
        index=["Total Revenue", "Net Income", "Diluted EPS"],
    )


def _pending_row(db, announced=datetime(2026, 10, 16, 12, 0), symbol="INFY"):
    db.add(ResultsDigest(symbol=symbol, period_end=PERIOD, filing_url="https://x/y", filing_title="t",
                         announced_at=announced, numbers_status="pending"))
    db.commit()


def test_numbers_in_rupees_with_yoy(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    monkeypatch.setattr(rd, "_quarterly_income", lambda symbol: _frame())
    _pending_row(db)
    assert rd.fill_pending_numbers(today=date(2026, 10, 17))["filled"] == 1
    row = db.query(ResultsDigest).one()
    assert row.numbers_status == "ok" and row.numbers_source == "yahoo_finance" and row.numbers_fetched_at
    assert (row.revenue_inr, row.net_profit_inr, row.eps) == (Decimal("1000.00"), Decimal("200.00"), Decimal("5.50"))
    assert (row.revenue_yoy_pct, row.net_profit_yoy_pct, row.eps_yoy_pct) == (25.0, 100.0, 37.5)


def test_non_positive_previous_gives_no_yoy_and_column_windows(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    # current column 3 days from the period end; year-ago column 9 days from period_end - 365
    frame = _frame(cur_date="2026-09-27", prev_date="2025-10-09", prev=(800.0, -50.0, 0.0))
    monkeypatch.setattr(rd, "_quarterly_income", lambda symbol: frame)
    _pending_row(db)
    rd.fill_pending_numbers(today=date(2026, 10, 17))
    row = db.query(ResultsDigest).one()
    assert row.numbers_status == "ok" and row.revenue_yoy_pct == 25.0
    assert row.net_profit_yoy_pct is None and row.eps_yoy_pct is None


def test_missing_period_stays_pending_then_gives_up_after_ten_days(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    monkeypatch.setattr(rd, "_quarterly_income", lambda symbol: _frame(cur_date="2026-06-30", prev_date="2025-06-30"))
    _pending_row(db)
    assert rd.fill_pending_numbers(today=date(2026, 10, 20))["still_pending"] == 1
    assert db.query(ResultsDigest).one().numbers_status == "pending"
    assert rd.fill_pending_numbers(today=date(2026, 10, 27))["unavailable"] == 1
    db.expire_all()
    assert db.query(ResultsDigest).one().numbers_status == "unavailable"


def test_exception_leaves_row_pending_and_max_calls_caps(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")

    def boom(symbol):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(rd, "_quarterly_income", boom)
    _pending_row(db)
    _pending_row(db, symbol="TCS")
    out = rd.fill_pending_numbers(today=date(2026, 10, 27), max_calls=1)
    assert out["calls"] == 1 and out["still_pending"] == 2
    assert {r.numbers_status for r in db.query(ResultsDigest)} == {"pending"}


def test_fill_skips_without_flag_or_cohort(db):
    _pending_row(db)
    assert rd.fill_pending_numbers() == {"skipped": "flag_off"}


# ── endpoint ────────────────────────────────────────────────────────────────

@pytest.fixture
def api(db):
    current = {"uid": 1}
    app = FastAPI()
    app.include_router(digest_router.router)
    app.dependency_overrides[require_auth] = lambda: current["uid"]
    client = TestClient(app)
    client.current = current
    return client


def test_endpoint_200_404_422(api, db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    db.add(ResultsDigest(symbol="INFY", period_end=date(2026, 6, 30), numbers_status="unavailable",
                         filing_url="https://x/old", created_at=datetime(2026, 7, 1)))
    db.add(ResultsDigest(symbol="INFY", period_end=PERIOD, filing_url="https://x/new", filing_title="Results",
                         announced_at=datetime(2026, 10, 16, 12, 0), numbers_status="ok",
                         revenue_inr=Decimal("1000.00"), net_profit_inr=Decimal("200.00"), eps=Decimal("5.50"),
                         revenue_yoy_pct=25.0, net_profit_yoy_pct=100.0, eps_yoy_pct=37.5,
                         numbers_fetched_at=datetime(2026, 10, 17, 3, 0), created_at=datetime(2026, 10, 16)))
    db.commit()
    body = api.get("/api/v1/stocks/infy.ns/results-digest").json()
    assert body["symbol"] == "INFY" and body["period_end"] == "2026-09-30" and body["filing_url"] == "https://x/new"
    assert body["period_label"] == "Quarter ended 30 Sep 2026"
    assert body["revenue_inr"] == 1000.0 and body["revenue_yoy_pct"] == 25.0 and body["eps"] == 5.5
    assert body["numbers_source_text"] == ("Figures from Yahoo Finance quarterly statements, fetched 17 Oct 2026. "
                                           "The company's exchange filing is the official source.")
    missing = api.get("/api/v1/stocks/NOPE/results-digest")
    assert missing.status_code == 404 and missing.json() == {"detail": {"code": "NO_DIGEST"}}
    bad = api.get("/api/v1/stocks/BAD$SYMBOL/results-digest")
    assert bad.status_code == 422 and bad.json() == {"detail": {"code": "INVALID_SYMBOL"}}


def test_unavailable_text(api, db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    db.add(ResultsDigest(symbol="TCS", period_end=PERIOD, numbers_status="unavailable", created_at=datetime(2026, 10, 1)))
    db.commit()
    assert api.get("/api/v1/stocks/TCS/results-digest").json()["numbers_source_text"] == \
        "Figures aren't available from our data source. See the company's filing."


def test_flag_off_cohort_and_envelope(api, db, monkeypatch):
    db.add(ResultsDigest(symbol="TCS", period_end=PERIOD, numbers_status="pending", created_at=datetime(2026, 10, 1)))
    db.commit()
    off = api.get("/api/v1/stocks/TCS/results-digest")
    assert off.status_code == 404
    assert off.json() == {"detail": {"code": "FEATURE_DISABLED", "feature": "data_results_digest"}}
    monkeypatch.setenv(FLAG_ENV + "_USERS", "1")
    assert api.get("/api/v1/stocks/TCS/results-digest").status_code == 200
    api.current["uid"] = 2
    assert api.get("/api/v1/stocks/TCS/results-digest").status_code == 404
