"""MATH-07: splits/bonuses reach holdings as ledger SPLIT rows, applied only to
shares held before the ex-date, once, from one Yahoo series (no bonus double-read)."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, Portfolio, Transaction
from services.ledger_service import apply_split_events, record_transaction


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def _get_session():
        session = Session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("database.get_session", _get_session)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _buy(ticker, qty, price, when):
    record_transaction(user_id=1, ticker=ticker, transaction_type="BUY", quantity=qty,
                       price=price, company_name="Test Co", date=when)


def _recorded_at(session, ticker, when):
    """Pretend the position's ledger rows were entered in the app at `when`."""
    session.query(Transaction).filter_by(user_id=1, ticker=ticker).update({"created_at": when})
    session.commit()


def _holding(session, ticker):
    session.expire_all()
    return session.query(Portfolio).filter_by(user_id=1, ticker=ticker, group_name="holdings").first()


def _splits(session, ticker):
    return session.query(Transaction).filter_by(user_id=1, ticker=ticker, transaction_type="SPLIT").all()


def test_split_applies_only_before_ex_date(db_session):
    _buy("SPLT", 100, 2000.0, datetime(2026, 1, 10, tzinfo=timezone.utc))
    _buy("SPLT", 10, 1000.0, datetime(2026, 3, 2, tzinfo=timezone.utc))  # on the ex-date: not multiplied
    _recorded_at(db_session, "SPLT", datetime(2026, 1, 10))

    assert apply_split_events(1, "SPLT", [(date(2026, 3, 2), 2.0)]) == 1

    h = _holding(db_session, "SPLT")
    assert float(h.shares) == pytest.approx(210.0)
    assert float(h.buy_price) == pytest.approx((200000 + 10000) / 210, abs=0.01)


def test_idempotent(db_session):
    _buy("IDEM", 100, 2000.0, datetime(2026, 1, 10, tzinfo=timezone.utc))
    _recorded_at(db_session, "IDEM", datetime(2026, 1, 10))
    events = [(date(2026, 3, 2), 2.0)]

    assert apply_split_events(1, "IDEM", events) == 1
    assert apply_split_events(1, "IDEM", events) == 0

    assert len(_splits(db_session, "IDEM")) == 1
    assert float(_holding(db_session, "IDEM").shares) == pytest.approx(200.0)


def test_backdated_buy_recorded_after_ex_date_is_not_multiplied(db_session):
    """Broker-adjusted quantity entered after the bonus, with the original trade date."""
    _buy("BKDT", 200, 750.0, datetime(2018, 5, 1, tzinfo=timezone.utc))  # recorded now, after the ex-date

    assert apply_split_events(1, "BKDT", [(date(2018, 9, 3), 2.0)]) == 0

    assert _splits(db_session, "BKDT") == []
    h = _holding(db_session, "BKDT")
    assert float(h.shares) == pytest.approx(200.0)
    assert float(h.buy_price) == pytest.approx(750.0)


def test_bonus_on_ledgerless_holding_after_it_was_added(db_session):
    """1:1 bonus (Yahoo ratio 2.0): 100 @ 2000 becomes 200 @ 1000, not a -50% loss."""
    db_session.add(Portfolio(user_id=1, ticker="BONX", company_name="Bonus Ltd", shares=100,
                             buy_price=2000.0, group_name="holdings", created_at=datetime(2026, 1, 1)))
    db_session.commit()

    assert apply_split_events(1, "BONX", [(date(2026, 3, 2), 2.0)]) == 1

    h = _holding(db_session, "BONX")
    assert float(h.shares) == pytest.approx(200.0)
    assert float(h.buy_price) == pytest.approx(1000.0)


def test_split_before_holding_was_added_writes_nothing(db_session):
    """The row's share count already reflects an older split; no opening BUY is left behind."""
    db_session.add(Portfolio(user_id=1, ticker="OLDS", company_name="Old Ltd", shares=100,
                             buy_price=500.0, group_name="holdings", created_at=datetime(2026, 6, 1)))
    db_session.commit()

    assert apply_split_events(1, "OLDS", [(date(2026, 3, 2), 2.0)]) == 0

    assert db_session.query(Transaction).filter_by(ticker="OLDS").count() == 0
    assert float(_holding(db_session, "OLDS").shares) == pytest.approx(100.0)


def test_skips_ticker_without_holding(db_session):
    assert apply_split_events(1, "NONE", [(date(2026, 3, 2), 2.0)]) == 0
    assert db_session.query(Transaction).count() == 0


def test_fetch_split_events_tz_aware(monkeypatch):
    import services.portfolio_service as ps

    idx = pd.DatetimeIndex(["2020-01-01", "2026-03-02"]).tz_localize("Asia/Kolkata")
    splits = pd.Series([1.0, 2.0], index=idx)  # ratio 1.0 is a no-op and dropped
    monkeypatch.setattr(ps, "yf", SimpleNamespace(Ticker=lambda sym: SimpleNamespace(splits=splits)))

    assert ps.fetch_split_events("ABC.NS") == [(date(2026, 3, 2), 2.0)]


def test_fetch_split_events_failure_is_empty(monkeypatch):
    import services.portfolio_service as ps

    def _boom(sym):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(ps, "yf", SimpleNamespace(Ticker=_boom))
    assert ps.fetch_split_events("ABC.NS") == []
