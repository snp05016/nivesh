"""
SILENT-01: a failed price lookup must never surface as a ₹0 price / -100% loss.

Unpriced holdings are valued at cost with price_status='unavailable' on
GET /portfolio/{id}; the benchmark returns 503 instead of NIFTY=1.0/cost-basis
numbers; the nightly snapshot never persists a cost-basis valuation (a short
gap, then a row over the priced holdings only).

Run from backend/:
    ../venv/bin/pytest tests/test_portfolio_price_unavailable.py -v
"""

import asyncio
import time
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd


def _make_user_with_holdings(holdings):
    """Create a throwaway user with ledger-less holdings; return (user_id, auth headers)."""
    import database
    from models.db_models import Portfolio, User

    with database.get_session() as session:
        user = User(username=f"price_{uuid4().hex[:12]}", password_hash="test", display_name="Price Test")
        session.add(user)
        session.flush()
        user_id = int(user.id)  # type: ignore[arg-type]
        for ticker, shares, buy_price in holdings:
            session.add(Portfolio(
                user_id=user_id, ticker=ticker, company_name=f"{ticker} Ltd",
                shares=shares, buy_price=buy_price, group_name="holdings",
            ))
        session.commit()
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_unpriced_holding_valued_at_cost_not_zero(client, monkeypatch):
    import routers.portfolio as portfolio_router

    uid, headers = _make_user_with_holdings([("RELIANCE", 10, 2500.0), ("INFY", 4, 1500.0)])
    quotes = {
        "RELIANCE": (2600.0, 2590.0, "live", "2026-10-10T10:00:00+00:00"),
        "INFY": (None, None, "unavailable", None),
    }
    monkeypatch.setattr(portfolio_router, "_to_ns", lambda t: t)
    monkeypatch.setattr(portfolio_router, "_yf_price_with_status", lambda sym: quotes[sym])

    r = client.get(f"/portfolio/{uid}", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    rows = {h["ticker"]: h for h in body["holdings"]}
    infy = rows["INFY"]
    assert infy["current_price"] == 1500.0  # cost basis, never 0.0
    assert infy["price_status"] == "unavailable"
    assert infy["current_value_inr"] == infy["invested_inr"] == 6000.0
    assert infy["pnl_inr"] == 0.0 and infy["pnl_pct"] == 0.0
    assert rows["RELIANCE"]["price_status"] == "live"
    assert rows["RELIANCE"]["price_as_of"] == "2026-10-10T10:00:00+00:00"
    assert body["unpriced_tickers"] == ["INFY"]
    assert body["total_pnl_inr"] == rows["RELIANCE"]["pnl_inr"] == 1000.0
    assert body["total_current_inr"] == 32000.0  # 26000 live + 6000 at cost


def test_compute_holding_pnl_none_price_is_cost_not_zero():
    from services.portfolio_service import compute_holding_pnl

    missing = compute_holding_pnl(10, 100.0, None, None)
    assert missing["current_value_inr"] == missing["invested_inr"] == 1000.0
    assert missing["pnl_inr"] == 0.0 and missing["pnl_pct"] == 0.0
    assert missing["day_change_pct"] == 0.0
    assert missing["price_status"] == "unavailable"

    live = compute_holding_pnl(10, 100.0, 110.0, 100.0)
    assert live["current_value_inr"] == 1100.0
    assert live["pnl_inr"] == 100.0 and live["pnl_pct"] == 10.0
    assert live["day_change_pct"] == 10.0
    assert live["price_status"] == "live"

    assert compute_holding_pnl(10, 100.0, 105.0, 104.0, "stale")["price_status"] == "stale"


def test_yf_price_with_status_falls_back_to_last_good(monkeypatch):
    import services.yfinance_client as yfc

    frames = [pd.DataFrame({"Close": [100.0, 105.0]})]  # first fetch works, the rest come back empty
    ticker = SimpleNamespace(history=lambda **_kw: frames.pop(0) if frames else pd.DataFrame())
    monkeypatch.setattr(yfc.yf, "Ticker", lambda _sym: ticker)
    monkeypatch.setattr(yfc.time, "sleep", lambda _s: None)
    monkeypatch.setattr(yfc, "_LAST_GOOD", {})

    import services.cache_service as cs

    live = yfc._yf_price_with_status("STALETEST.NS")
    cs.cache.invalidate_sync("quote", "STALETEST.NS")  # the 60 s quote cache expires (PERF-07)
    stale = yfc._yf_price_with_status("STALETEST.NS")

    assert live[:3] == (105.0, 100.0, "live")
    assert stale[:3] == (105.0, 100.0, "stale")
    assert stale[3] is not None
    assert yfc._yf_price("STALETEST.NS") == (None, None)  # alert paths never get the stale value

    yfc._LAST_GOOD["STALETEST.NS"] = (105.0, 100.0, time.time() - 5 * 86400)  # older than 4 days
    assert yfc._yf_price_with_status("STALETEST.NS") == (None, None, "unavailable", None)


def test_benchmark_without_nifty_data_returns_503(client, monkeypatch):
    import routers.portfolio_analytics as portfolio_router

    uid, headers = _make_user_with_holdings([("TCS", 2, 3000.0)])
    empty = SimpleNamespace(history=lambda **_kw: pd.DataFrame())
    monkeypatch.setattr(portfolio_router.yf, "Ticker", lambda _sym: empty)

    r = client.get("/portfolio/benchmark", params={"user_id": uid}, headers=headers)

    assert r.status_code == 503


def test_benchmark_excludes_unpriced_holdings(client, monkeypatch):
    import routers.portfolio_analytics as portfolio_router

    uid, headers = _make_user_with_holdings([("TCS", 2, 3000.0), ("INFY", 4, 1500.0)])
    idx = pd.to_datetime([date.today() - timedelta(days=1), date.today()])
    nifty = SimpleNamespace(history=lambda **_kw: pd.DataFrame({"Close": [20000.0, 20100.0]}, index=idx))
    monkeypatch.setattr(portfolio_router.yf, "Ticker", lambda _sym: nifty)
    monkeypatch.setattr(portfolio_router, "_to_ns", lambda t: t)
    monkeypatch.setattr(
        portfolio_router, "get_quotes",
        lambda syms: {s: (3030.0, 3000.0) if s == "TCS" else (None, None) for s in syms},
    )

    r = client.get("/portfolio/benchmark", params={"user_id": uid}, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unpriced_tickers"] == ["INFY"]
    assert body["current_portfolio_value"] == 6060.0  # INFY excluded, not valued at cost


def _add_snapshot(user_id, snapshot_date):
    import database
    from models.db_models import PortfolioValuationHistory

    with database.get_session() as session:
        session.add(PortfolioValuationHistory(
            user_id=user_id, snapshot_date=snapshot_date.isoformat(),
            total_value=1.0, total_invested=1.0, total_pnl=0.0, pnl_percent=0.0,
        ))
        session.commit()


def _today_snapshot(user_id):
    import database
    from models.db_models import PortfolioValuationHistory

    with database.get_session() as session:
        row = session.query(PortfolioValuationHistory).filter_by(
            user_id=user_id, snapshot_date=date.today().isoformat()
        ).first()
        return None if row is None else (row.total_value, row.total_invested)


def test_snapshot_skips_user_when_a_price_is_missing(monkeypatch):
    """Transient miss (history is recent): leave an honest gap, never a cost-basis row."""
    import services.portfolio_snapshot as snap

    uid, _ = _make_user_with_holdings([("PRICEDX", 2, 3000.0), ("MISSINGX", 4, 1500.0)])
    _add_snapshot(uid, date.today() - timedelta(days=1))
    monkeypatch.setattr(snap, "get_current_price", lambda t: 3100.0 if t == "PRICEDX" else None)

    asyncio.run(snap.snapshot_all_users())

    assert _today_snapshot(uid) is None


def test_snapshot_persistent_miss_writes_priced_holdings_only(monkeypatch):
    """A ticker that never prices must not freeze history: once the last row is older
    than _SNAPSHOT_MAX_GAP_DAYS, today's row covers the priced holdings only, with the
    unpriced one left out of value AND invested."""
    import services.portfolio_snapshot as snap

    uid, _ = _make_user_with_holdings([("PRICEDX", 2, 3000.0), ("DELISTEDX", 4, 1500.0)])
    _add_snapshot(uid, date.today() - timedelta(days=snap._SNAPSHOT_MAX_GAP_DAYS + 1))
    monkeypatch.setattr(snap, "get_current_price", lambda t: 3100.0 if t == "PRICEDX" else None)

    asyncio.run(snap.snapshot_all_users())

    assert _today_snapshot(uid) == (6200.0, 6000.0)


def test_snapshot_get_current_price_keeps_suffixed_ticker(monkeypatch):
    """'TCS.NS' must be priced as TCS.NS, not TCS.NS.NS / TCS.NS.BO."""
    import services.portfolio_snapshot as snap

    seen = []
    monkeypatch.setattr(snap, "_yf_price", lambda sym: (seen.append(sym), (3900.0, 3850.0))[1])

    assert snap.get_current_price("TCS.NS") == 3900.0
    assert seen == ["TCS.NS"]


def test_valuation_history_backfill_is_estimated_not_persisted(client, monkeypatch):
    """REL-10: the 30-day back-fill uses today's shares/cost, so it is returned flagged
    as estimated and never written to PortfolioValuationHistory."""
    import database
    import routers.portfolio_analytics as portfolio_router
    from models.db_models import PortfolioValuationHistory

    uid, headers = _make_user_with_holdings([("TCS", 2, 3000.0)])
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=3, freq="D")
    hist = SimpleNamespace(history=lambda **_kw: pd.DataFrame({"Close": [3000.0, 3100.0, 3200.0]}, index=idx))
    monkeypatch.setattr(portfolio_router.yf, "Ticker", lambda _sym: hist)

    r = client.get("/api/v1/portfolio/valuation-history", params={"user_id": uid}, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estimated"] is True
    assert [p["total_value"] for p in body["snapshots"]] == [6000.0, 6200.0, 6400.0]
    with database.get_session() as session:
        assert session.query(PortfolioValuationHistory).filter_by(user_id=uid).count() == 0
