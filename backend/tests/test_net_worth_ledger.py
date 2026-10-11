"""MATH-24: the nightly snapshot writes NetWorthLedger rows (delta vs the previous
row, running peak, top gainer/loser), idempotently per day, so
GET /api/v1/market/net-worth-ledger/{id} returns data instead of a permanent 404."""
from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest


def _make_user(holdings):
    import database
    from models.db_models import Portfolio, User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"nwl_{uuid4().hex[:12]}", password_hash="x", display_name="NWL Test")
        session.add(user)
        session.flush()
        user_id = int(user.id)  # type: ignore[arg-type]
        for ticker, shares in holdings:
            session.add(Portfolio(
                user_id=user_id, ticker=ticker, company_name=f"{ticker} Ltd",
                shares=shares, buy_price=100.0, group_name="holdings",
            ))
        session.commit()
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _ledger(user_id):
    import database
    from models.db_models import NetWorthLedger  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        rows = session.query(NetWorthLedger).filter_by(user_id=user_id).order_by(NetWorthLedger.snapshot_date).all()
        return [
            SimpleNamespace(
                date=r.snapshot_date, total=r.total_value_inr, delta=r.daily_delta_inr, delta_pct=r.daily_delta_pct,
                peak=r.peak_value_inr, gainer=(r.top_gainer_ticker, r.top_gainer_pct),
                loser=(r.top_loser_ticker, r.top_loser_pct),
            )
            for r in rows
        ]


@pytest.fixture
def run_snapshot(monkeypatch):
    """Run snapshot_all_users on a frozen day with fixed prices (no network)."""
    import services.portfolio_snapshot as snap

    empty = SimpleNamespace(history=lambda **_kw: pd.DataFrame())
    monkeypatch.setattr(snap.yf, "Ticker", lambda _sym: empty)  # NIFTY close -> None

    def _run(day: date, prices: dict):
        class _FrozenDate(date):
            @classmethod
            def today(cls):
                return day

        monkeypatch.setattr(snap, "date", _FrozenDate)
        monkeypatch.setattr(snap, "get_current_price", lambda t: prices.get(t))
        asyncio.run(snap.snapshot_all_users())

    return _run


def test_snapshot_writes_ledger_with_delta_peak_and_movers(client, run_snapshot):
    a, b = f"NWA{uuid4().hex[:6].upper()}", f"NWB{uuid4().hex[:6].upper()}"
    uid, headers = _make_user([(a, 10), (b, 5)])

    run_snapshot(date(2026, 10, 8), {a: 100.0, b: 100.0})   # 1000 + 500
    run_snapshot(date(2026, 10, 9), {a: 110.0, b: 95.0})    # 1100 + 475
    run_snapshot(date(2026, 10, 9), {a: 999.0, b: 999.0})   # same-day re-run: no new/changed row
    run_snapshot(date(2026, 10, 10), {a: 100.0, b: 95.0})   # 1000 + 475

    day1, day2, day3 = _ledger(uid)
    assert (day1.date, day1.total, day1.delta, day1.peak) == ("2026-10-08", 1500.0, None, 1500.0)
    assert day1.gainer == (None, None) and day1.loser == (None, None)

    assert (day2.date, day2.total, day2.delta, day2.delta_pct, day2.peak) == ("2026-10-09", 1575.0, 75.0, 5.0, 1575.0)
    assert day2.gainer == (a, 10.0)
    assert day2.loser == (b, -5.0)

    assert (day3.total, day3.delta, day3.peak) == (1475.0, -100.0, 1575.0)  # peak is running max
    assert day3.gainer == (None, None)  # b unchanged, a fell
    assert day3.loser == (a, -9.09)

    r = client.get(f"/api/v1/market/net-worth-ledger/{uid}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["snapshot_date"] == "2026-10-10"
    assert body["total_value_formatted"] == "₹1,475"
    assert body["top_loser_ticker"] == a


def test_ledger_backfilled_when_valuation_row_already_exists(run_snapshot):
    """A day whose PortfolioValuationHistory row exists but ledger row is missing
    (e.g. written before this feature) still gets its ledger row on re-run."""
    import database
    from models.db_models import PortfolioValuationHistory  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    a = f"NWC{uuid4().hex[:6].upper()}"
    uid, _ = _make_user([(a, 2)])
    with database.get_session() as session:
        session.add(PortfolioValuationHistory(
            user_id=uid, snapshot_date="2026-10-08", total_value=1.0,
            total_invested=1.0, total_pnl=0.0, pnl_percent=0.0,
        ))
        session.commit()

    run_snapshot(date(2026, 10, 8), {a: 150.0})

    (row,) = _ledger(uid)
    assert (row.date, row.total) == ("2026-10-08", 300.0)
    with database.get_session() as session:
        assert session.query(PortfolioValuationHistory).filter_by(user_id=uid).count() == 1
