"""PERF-17: alert listing and the poller fetch each unique ticker once.

(One HTTP/2 client per push is covered by tests/test_push_delivery.py.)
"""
import asyncio
import threading
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import Base, PriceTarget, User
from services import alerts_service, notifications_inbox, preferences

_TICKERS = ["TCS", "INFY", "ITC"]


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def _get_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    for mod in (alerts_service, notifications_inbox, preferences):
        monkeypatch.setattr(mod, "get_session", _get_session)
    with _get_session() as s:
        s.add(User(id=1, username="alerts_user", password_hash="x", display_name="Alerts"))
        for i in range(10):  # 10 alerts on 3 tickers, none crossed at price 100
            s.add(PriceTarget(user_id=1, ticker=_TICKERS[i % 3], target_price=200.0 + i,
                              direction="above", triggered=False))
        s.commit()
    yield _get_session
    engine.dispose()


@pytest.fixture()
def price_calls(monkeypatch):
    calls = []
    lock = threading.Lock()

    def _price(sym):
        with lock:
            calls.append(sym)
        return 100.0, 95.0

    monkeypatch.setattr(alerts_service, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(alerts_service, "_yf_price", _price)
    return calls


def test_get_alerts_data_dedupes(db, price_calls):
    rows = alerts_service.get_alerts_data(1)

    assert len(rows) == 10
    assert sorted(price_calls) == sorted(f"{t}.NS" for t in _TICKERS)
    assert all(r["current_price"] == 100.0 for r in rows)
    assert all(r["distance_pct"] is not None for r in rows)


def test_get_alerts_data_one_failing_ticker(db, monkeypatch):
    def _price(sym):
        if sym.startswith("INFY"):
            raise RuntimeError("yahoo down")
        return 100.0, 95.0

    monkeypatch.setattr(alerts_service, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(alerts_service, "_yf_price", _price)

    rows = alerts_service.get_alerts_data(1)
    by_ticker = {r["ticker"]: r["current_price"] for r in rows}
    assert by_ticker == {"TCS": 100.0, "INFY": None, "ITC": 100.0}


def test_poller_fetches_each_ticker_once(db, price_calls, monkeypatch):
    push = AsyncMock()
    monkeypatch.setattr(alerts_service, "_send_apns_push", push)

    asyncio.run(alerts_service._poll_once())

    assert sorted(price_calls) == sorted(f"{t}.NS" for t in _TICKERS)
    push.assert_not_awaited()  # nothing crossed
