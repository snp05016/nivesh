"""I32 Watchlist v2: price-at-add capture and since-added fields (habit-watchlist-backend)."""
import datetime as dt
from typing import Any

import pytest

import services.user_service as user_service
from database import Portfolio, get_session

_TICKERS = ("PAATCS", "PAANOPRICE", "PAALEGACY")


@pytest.fixture
def uid(test_user_id, monkeypatch):
    """Session test user with quota, symbol mapping and ASM/GSM lookup stubbed out."""
    monkeypatch.setattr(user_service.entitlement_service, "enforce_quota", lambda *_a, **_k: None)
    monkeypatch.setattr(user_service, "_to_ns", lambda t: t)
    monkeypatch.setattr(user_service, "_get_asm_gsm_lists", lambda: {"ASM": set(), "GSM": set()})
    monkeypatch.setattr(user_service, "latest_signals_by_ticker", lambda _s, _t: {})
    user_service._watchlist_price_cache.pop(test_user_id, None)
    yield test_user_id
    user_service._watchlist_price_cache.pop(test_user_id, None)
    with get_session() as session:
        session.query(Portfolio).filter(Portfolio.user_id == test_user_id,
                                        Portfolio.ticker.in_(_TICKERS)).delete(synchronize_session=False)
        session.commit()


def _patch_add_price(monkeypatch, quote):
    monkeypatch.setattr(user_service, "_yf_price", lambda _sym: quote)


def _patch_current(monkeypatch, quote):
    # get_watchlist reads quotes through the PERF-07 batch helper.
    monkeypatch.setattr(user_service, "get_quotes", lambda syms: {s: quote for s in syms})


def _row(uid, ticker, group="watchlist") -> Any:
    with get_session() as session:
        r = session.query(Portfolio).filter_by(user_id=uid, ticker=ticker, group_name=group).one()
        return r.added_price


def _item(uid, ticker):
    user_service._watchlist_price_cache.pop(uid, None)
    out = user_service.get_watchlist(uid)
    assert out is not None
    return next(i for i in out["watchlist"] if i["ticker"] == ticker)


def test_add_captures_price_and_get_reports_since_added(uid, monkeypatch):
    _patch_add_price(monkeypatch, (150.0, 148.0))
    resp = user_service.add_to_watchlist(uid, "paatcs", "Tata Consultancy")
    assert resp == {"success": True, "ticker": "PAATCS", "added_price": 150.0}
    assert float(_row(uid, "PAATCS")) == 150.0

    _patch_current(monkeypatch, (165.0, 160.0))
    item = _item(uid, "PAATCS")
    assert item["since_added_pct"] == 10.0
    assert item["added_price"] == 150.0
    assert dt.date.fromisoformat(item["added_at"])
    # Existing fields unchanged.
    assert item["current_price"] == 165.0
    assert item["price_status"] == "live"
    assert item["day_change_pct"] == round(5 / 160 * 100, 2)
    for key in ("company_name", "exchange", "last_signal", "last_signal_date", "asm_gsm_status"):
        assert key in item


def test_current_price_missing_gives_null_since_added(uid, monkeypatch):
    _patch_add_price(monkeypatch, (150.0, 148.0))
    user_service.add_to_watchlist(uid, "PAATCS", "Tata Consultancy")
    _patch_current(monkeypatch, (None, None))
    item = _item(uid, "PAATCS")
    assert item["added_price"] == 150.0
    assert item["since_added_pct"] is None
    assert item["price_status"] == "unavailable"


@pytest.mark.parametrize("quote", [(None, None), (0.0, 0.0)])
def test_no_price_at_add_stores_null(uid, monkeypatch, quote):
    _patch_add_price(monkeypatch, quote)
    resp = user_service.add_to_watchlist(uid, "PAANOPRICE", "No Price Ltd")
    assert resp["success"] is True and resp["added_price"] is None
    assert _row(uid, "PAANOPRICE") is None

    _patch_current(monkeypatch, (120.0, 118.0))
    item = _item(uid, "PAANOPRICE")
    assert item["added_price"] is None
    assert item["since_added_pct"] is None


def test_price_lookup_raising_stores_null(uid, monkeypatch):
    def _boom(_sym):
        raise RuntimeError("provider down")
    monkeypatch.setattr(user_service, "_yf_price", _boom)
    resp = user_service.add_to_watchlist(uid, "PAANOPRICE", "No Price Ltd")
    assert resp["added_price"] is None
    assert _row(uid, "PAANOPRICE") is None


def test_legacy_row_without_added_price(uid, monkeypatch):
    with get_session() as session:
        session.add(Portfolio(user_id=uid, ticker="PAALEGACY", company_name="Legacy Ltd",
                              shares=0, buy_price=0, group_name="watchlist"))
        session.commit()
    _patch_current(monkeypatch, (200.0, 199.0))
    item = _item(uid, "PAALEGACY")
    assert item["added_price"] is None
    assert item["since_added_pct"] is None
    assert dt.date.fromisoformat(item["added_at"])


def test_holdings_row_unaffected(uid, monkeypatch):
    with get_session() as session:
        session.add(Portfolio(user_id=uid, ticker="PAATCS", company_name="Tata Consultancy",
                              shares=5, buy_price=100.0, group_name="holdings"))
        session.commit()
    _patch_add_price(monkeypatch, (150.0, 148.0))
    user_service.add_to_watchlist(uid, "PAATCS", "Tata Consultancy")
    assert _row(uid, "PAATCS", group="holdings") is None
    assert float(_row(uid, "PAATCS")) == 150.0


def test_ist_date_conversion():
    # 20:00 UTC on 1 Oct is 01:30 IST on 2 Oct; naive values are treated as UTC.
    assert user_service._ist_date_iso(dt.datetime(2026, 10, 1, 20, 0)) == "2026-10-02"
    aware = dt.datetime(2026, 10, 1, 20, 0, tzinfo=dt.timezone.utc)
    assert user_service._ist_date_iso(aware) == "2026-10-02"
    assert user_service._ist_date_iso(None) is None
