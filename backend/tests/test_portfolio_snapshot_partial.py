"""DB-21 / DB-22: the daily snapshot never stores a cost-basis value for a missing
price, a same-day re-run (the retry job) fills the gap, and no DB session is open
while prices are fetched."""
import asyncio
from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import Base, Portfolio, PortfolioValuationHistory, User


@pytest.fixture()
def snap_env(monkeypatch):
    import services.portfolio_snapshot as snap

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    state = {"open": 0}

    @contextmanager
    def _session():
        s = Session()
        state["open"] += 1
        try:
            yield s
        finally:
            state["open"] -= 1
            s.close()

    monkeypatch.setattr(snap, "get_session", _session)
    empty = SimpleNamespace(history=lambda **_kw: pd.DataFrame())
    monkeypatch.setattr(snap.yf, "Ticker", lambda _sym: empty)  # NIFTY close -> None

    with Session() as s:
        user = User(username="snap_user", password_hash="x", display_name="Snap")
        s.add(user)
        s.flush()
        s.add(Portfolio(user_id=user.id, ticker="SNAPA", company_name="A Ltd", shares=2, buy_price=100.0,
                        group_name="holdings"))
        s.add(Portfolio(user_id=user.id, ticker="SNAPB", company_name="B Ltd", shares=4, buy_price=50.0,
                        group_name="holdings"))
        # Recent history: a missing price is a transient miss, so the day is skipped.
        s.add(PortfolioValuationHistory(
            user_id=user.id, snapshot_date=(date.today() - timedelta(days=1)).isoformat(),
            total_value=1.0, total_invested=1.0, total_pnl=0.0, pnl_percent=0.0,
        ))
        s.commit()
        user_id = int(user.id)  # type: ignore[arg-type]

    def _run(prices: dict) -> dict:
        def _price(ticker):
            assert state["open"] == 0, "DB session held open across a price fetch"
            return prices.get(ticker)

        monkeypatch.setattr(snap, "get_current_price", _price)
        return asyncio.run(snap.snapshot_all_users())

    def _today_rows():
        with Session() as s:
            return [
                (r.total_value, r.total_invested)
                for r in s.query(PortfolioValuationHistory).filter_by(
                    user_id=user_id, snapshot_date=date.today().isoformat()
                )
            ]

    yield SimpleNamespace(run=_run, today_rows=_today_rows)
    engine.dispose()


def test_missing_price_skips_then_retry_fills(snap_env):
    first = snap_env.run({"SNAPA": 100.0, "SNAPB": None})
    assert first == {"written": 0, "skipped_partial": 1, "already": 0}
    assert snap_env.today_rows() == []  # never a cost-basis row

    second = snap_env.run({"SNAPA": 110.0, "SNAPB": 60.0})
    assert second == {"written": 1, "skipped_partial": 0, "already": 0}
    assert snap_env.today_rows() == [(2 * 110.0 + 4 * 60.0, 2 * 100.0 + 4 * 50.0)]

    third = snap_env.run({"SNAPA": 999.0, "SNAPB": 999.0})
    assert third == {"written": 0, "skipped_partial": 0, "already": 1}
    assert snap_env.today_rows() == [(460.0, 400.0)]


def test_retry_job_is_scheduled(monkeypatch):
    """The 11:00 UTC snapshot has a 12:00 UTC retry that fills skipped users."""
    import fcntl
    import io

    import services.harvest_worker as hw

    jobs = []

    class _FakeScheduler:
        def __init__(self, **_kwargs):
            pass

        def add_job(self, func, trigger, **kwargs):
            jobs.append((getattr(func, "__wrapped__", func), trigger, kwargs))

        def start(self):
            pass

    monkeypatch.setattr(hw, "AsyncIOScheduler", _FakeScheduler)
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", lambda *_a, **_k: io.StringIO(), raising=False)  # no real lock file
    monkeypatch.setattr(fcntl, "lockf", lambda *_a, **_k: None)
    assert hw.start_scheduler() is True

    hours = sorted(
        kw.get("hour") for func, trigger, kw in jobs
        if trigger == "cron" and getattr(func, "__name__", "") == "snapshot_all_users"
    )
    assert hours == [11, 12]
