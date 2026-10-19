"""
Phase 5: Transaction Ledger — unit + API contract tests.

Tests cover:
  - WAC recalculation: two BUYs average correctly
  - SELL reduces shares, WAC cost basis proportionally reduced
  - Position fully closed (SELL all) deletes Portfolio row
  - Pre-ledger holdings (no Transaction rows) get an opening BUY, never wiped
  - adjust_position / close_position (PUT/DELETE) survive the next replay
  - Rows deleted/rewritten outside the ledger are reconciled (ADJUST), not resurrected
  - GET /portfolio/transactions/{ticker} returns correct records

Run from backend/:
    ../venv/bin/pytest tests/test_portfolio_ledger.py -v
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.conftest import REGISTER_CONSENT

# conftest.py patches heavy modules before any app import — rely on that here.
from models.db_models import Base, Portfolio, PortfolioGroup, Transaction
from services.ledger_service import (
    record_transaction, _recalculate_portfolio_snapshot, adjust_position, close_position,
)

# SQLAlchemy 1.x uses untyped Column descriptors; at runtime ORM instance
# attributes are plain Python scalars. This helper satisfies Pyright.
def _f(v) -> float:  # type: ignore[misc]
    return float(v)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(monkeypatch):
    """Ephemeral in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    
    # Mock get_session so services use this in-memory session
    from contextlib import contextmanager
    @contextmanager
    def mock_get_session():
        session = Session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            
    monkeypatch.setattr("database.get_session", mock_get_session)
    
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_group(session, user_id: int = 1) -> PortfolioGroup:
    g = PortfolioGroup(user_id=user_id, name="Test Holdings", is_default=True)
    session.add(g)
    session.flush()
    return g


def _buy(user_id, group_id, ticker, qty, price):
    record_transaction(
        user_id=user_id,
        ticker=ticker,
        transaction_type="BUY",
        quantity=qty,
        price=price,
        group_id=group_id,
        company_name="Test Co",
    )


def _sell(user_id, group_id, ticker, qty, price):
    record_transaction(
        user_id=user_id,
        ticker=ticker,
        transaction_type="SELL",
        quantity=qty,
        price=price,
        group_id=group_id,
        company_name="Test Co",
    )


def _holding(session, user_id, ticker) -> Portfolio | None:
    return session.query(Portfolio).filter_by(
        user_id=user_id, ticker=ticker, group_name="holdings"
    ).first()


# ---------------------------------------------------------------------------
# Unit tests — WAC engine
# ---------------------------------------------------------------------------

class TestWACEngine:
    def test_ledger_single_buy(self, db_session):
        g = _make_group(db_session)
        _buy(user_id=1, group_id=g.id, ticker="TCS.NS", qty=10, price=3500.0)
        db_session.commit()

        h = _holding(db_session, 1, "TCS.NS")
        assert h is not None
        assert round(_f(h.shares), 2) == 10.0
        assert round(_f(h.buy_price), 2) == 3500.0

    def test_ledger_multiple_buys_wac(self, db_session):
        """BUY 10 @ 2000 + BUY 5 @ 2600 → 15 shares @ 2200 WAC."""
        g = _make_group(db_session)
        _buy(user_id=1, group_id=g.id, ticker="RELIANCE.NS", qty=10, price=2000.0)
        _buy(user_id=1, group_id=g.id, ticker="RELIANCE.NS", qty=5, price=2600.0)
        db_session.commit()

        h = _holding(db_session, 1, "RELIANCE.NS")
        assert h is not None
        assert round(float(h.shares), 2) == 15.0
        # total cost = 20000 + 13000 = 33000 → WAC = 33000/15 = 2200
        assert round(float(h.buy_price), 2) == 2200.0

    def test_ledger_partial_sell_maintains_wac(self, db_session):
        """After WAC avg, SELL reduces qty but not WAC."""
        g = _make_group(db_session)
        _buy(user_id=1, group_id=g.id, ticker="ITC.NS", qty=100, price=200.0)
        _sell(user_id=1, group_id=g.id, ticker="ITC.NS", qty=40, price=250.0)
        db_session.commit()

        h = _holding(db_session, 1, "ITC.NS")
        assert h is not None
        assert round(h.shares, 2) == 60.0
        assert round(h.buy_price, 2) == 200.0

    def test_ledger_oversell_raises_error(self, db_session):
        """Selling more than held raises ValueError (short-selling forbidden)."""
        g = _make_group(db_session)
        _buy(user_id=1, group_id=g.id, ticker="HDFCBANK.NS", qty=10, price=1500.0)
        
        with pytest.raises(ValueError, match="only 10.0 shares held"):
            _sell(user_id=1, group_id=g.id, ticker="HDFCBANK.NS", qty=15, price=1600.0)

    def test_transactions_stored_immutably(self, db_session):
        """All transaction records persist regardless of share state."""
        g = _make_group(db_session)
        _buy(1, g.id, "HDFC", 10, 1600.0)
        _sell(1, g.id, "HDFC", 10, 1900.0)
        db_session.commit()

        txns = session_query_all(db_session, "HDFC", 1)
        assert len(txns) == 2
        types = {t.transaction_type for t in txns}
        assert types == {"BUY", "SELL"}

    def test_multiple_tickers_isolated(self, db_session):
        """Transactions for different tickers don't interfere."""
        g = _make_group(db_session)
        _buy(1, g.id, "RELIANCE", 5, 2500.0)
        _buy(1, g.id, "TCS", 5, 3000.0)
        _sell(1, g.id, "RELIANCE", 5, 2600.0)
        db_session.commit()

        h_rel = _holding(db_session, 1, "RELIANCE")
        h_tcs = _holding(db_session, 1, "TCS")
        assert h_rel is None
        assert h_tcs is not None
        assert round(h_tcs.shares, 2) == 5.0


def session_query_all(session, ticker: str, user_id: int) -> list[Transaction]:
    return session.query(Transaction).filter_by(user_id=user_id, ticker=ticker).all()


# ---------------------------------------------------------------------------
# Pre-ledger holdings + ledger-backed edit/remove
# ---------------------------------------------------------------------------

_OPENING_NOTE = "Opening balance (pre-ledger holding)"


def _seed_legacy_holding(session, group_id, ticker, shares, buy_price, user_id: int = 1):
    """A holdings row with no Transaction rows, as seeds/scripts/the pre-ledger API create."""
    session.add(Portfolio(
        user_id=user_id, ticker=ticker, company_name=f"{ticker} Ltd",
        shares=shares, buy_price=buy_price, group_name="holdings", group_id=group_id,
    ))
    session.commit()


class TestPreLedgerHoldings:
    def test_sell_on_pre_ledger_holding_keeps_remainder(self, db_session):
        """Legacy 100 @ 3200, SELL 10 → 90 @ 3200 (not a deleted position)."""
        g = _make_group(db_session)
        _seed_legacy_holding(db_session, g.id, "TCS", 100, 3200.0)

        _sell(1, g.id, "TCS", 10, 3500.0)
        db_session.commit()

        h = _holding(db_session, 1, "TCS")
        assert h is not None
        assert _f(h.shares) == 90.0
        assert _f(h.buy_price) == 3200.0
        txns = session_query_all(db_session, "TCS", 1)
        assert sorted(t.transaction_type for t in txns) == ["BUY", "SELL"]
        opening = next(t for t in txns if str(t.transaction_type) == "BUY")
        assert str(opening.notes) == _OPENING_NOTE
        assert _f(opening.quantity) == 100.0 and _f(opening.price) == 3200.0

    def test_buy_on_pre_ledger_holding_blends_wac(self, db_session):
        """Legacy 100 @ 3200 + BUY 5 @ 3500 → 105 @ 3214.29 (not 5 @ 3500)."""
        g = _make_group(db_session)
        _seed_legacy_holding(db_session, g.id, "TCS", 100, 3200.0)

        _buy(1, g.id, "TCS", 5, 3500.0)
        db_session.commit()

        h = _holding(db_session, 1, "TCS")
        assert h is not None
        assert _f(h.shares) == 105.0
        assert round(_f(h.buy_price), 2) == 3214.29

    def test_opening_balance_inserted_once(self, db_session):
        g = _make_group(db_session)
        _seed_legacy_holding(db_session, g.id, "SBIN", 290, 600.0)

        _buy(1, g.id, "SBIN", 10, 700.0)
        _buy(1, g.id, "SBIN", 10, 800.0)
        db_session.commit()

        txns = session_query_all(db_session, "SBIN", 1)
        assert len(txns) == 3
        assert sum(1 for t in txns if str(t.notes) == _OPENING_NOTE) == 1
        h = _holding(db_session, 1, "SBIN")
        assert h is not None
        assert _f(h.shares) == 310.0

    def test_recalc_with_empty_ledger_keeps_row(self, db_session):
        g = _make_group(db_session)
        _seed_legacy_holding(db_session, g.id, "INFY", 100, 1500.0)

        _recalculate_portfolio_snapshot(db_session, user_id=1, group_id=int(g.id), ticker="INFY")  # type: ignore[arg-type]
        db_session.commit()

        h = _holding(db_session, 1, "INFY")
        assert h is not None
        assert _f(h.shares) == 100.0
        assert _f(h.buy_price) == 1500.0


class TestLedgerBackedEditRemove:
    def test_adjust_then_buy_preserves_edit(self, db_session):
        """PUT 40 @ 55 on a legacy row, then BUY 10 @ 65 → 50 @ 57 (edit kept)."""
        g = _make_group(db_session)
        _seed_legacy_holding(db_session, g.id, "ITC", 100, 50.0)

        assert adjust_position(1, "ITC", 40, 55.0, target_price=70.0, purchase_date="01-Jan-2026") == "ITC Ltd"
        db_session.commit()
        h = _holding(db_session, 1, "ITC")
        assert h is not None
        assert (_f(h.shares), _f(h.buy_price), _f(h.target_price)) == (40.0, 55.0, 70.0)
        assert str(h.purchase_date) == "01-Jan-2026"

        _buy(1, g.id, "ITC", 10, 65.0)
        db_session.commit()

        h = _holding(db_session, 1, "ITC")
        assert h is not None
        assert _f(h.shares) == 50.0
        assert _f(h.buy_price) == 57.0  # (40*55 + 10*65) / 50

    def test_close_then_buy_does_not_resurrect(self, db_session):
        g = _make_group(db_session)
        _buy(1, g.id, "WIPRO", 100, 400.0)

        assert close_position(1, "WIPRO") is True
        db_session.commit()
        assert _holding(db_session, 1, "WIPRO") is None

        _buy(1, g.id, "WIPRO", 5, 450.0)
        db_session.commit()

        h = _holding(db_session, 1, "WIPRO")
        assert h is not None
        assert _f(h.shares) == 5.0
        assert _f(h.buy_price) == 450.0

    def test_row_deleted_outside_ledger_is_not_resurrected(self, db_session):
        """Pre-fix DELETE /portfolio/remove (or populate_portfolio) dropped the row but
        kept the ledger: BUY 5 must give 5 shares, not 100 + 5."""
        g = _make_group(db_session)
        _buy(1, g.id, "TCS", 100, 3200.0)
        db_session.delete(_holding(db_session, 1, "TCS"))
        db_session.commit()

        _buy(1, g.id, "TCS", 5, 3500.0)
        db_session.commit()

        h = _holding(db_session, 1, "TCS")
        assert h is not None
        assert (_f(h.shares), _f(h.buy_price)) == (5.0, 3500.0)
        assert [t.transaction_type for t in session_query_all(db_session, "TCS", 1)] == ["BUY", "ADJUST", "BUY"]

    def test_row_rewritten_outside_ledger_is_kept(self, db_session):
        """A re-seeded / directly edited row (50 @ 300) over a 100 @ 400 ledger: the next
        BUY builds on the row, not on the stale ledger."""
        g = _make_group(db_session)
        _buy(1, g.id, "SBIN", 100, 400.0)
        h = _holding(db_session, 1, "SBIN")
        assert h is not None
        h.shares, h.buy_price = 50.0, 300.0  # type: ignore[assignment]
        db_session.commit()

        _buy(1, g.id, "SBIN", 10, 500.0)
        db_session.commit()

        h = _holding(db_session, 1, "SBIN")
        assert h is not None
        assert (_f(h.shares), _f(h.buy_price)) == (60.0, 333.33)  # (50*300 + 10*500) / 60

    def test_edit_remove_unknown_holding_returns_not_found(self, db_session):
        _make_group(db_session)
        db_session.commit()
        assert adjust_position(1, "NOPE", 10, 100.0) is None
        assert close_position(1, "NOPE") is False
        assert session_query_all(db_session, "NOPE", 1) == []


class TestTargetAndTradeDate:
    def test_buy_without_target_keeps_existing_target(self, db_session):
        """Omitted (None) or legacy-sentinel 0.0 targets never wipe a real target."""
        gid = int(_make_group(db_session).id)  # type: ignore[arg-type]
        record_transaction(user_id=1, ticker="INFY", transaction_type="BUY", quantity=10,
                           price=1500.0, group_id=gid, company_name="Infosys", target_price=4000.0)
        record_transaction(user_id=1, ticker="INFY", transaction_type="BUY", quantity=1,
                           price=1500.0, group_id=gid, target_price=None)
        record_transaction(user_id=1, ticker="INFY", transaction_type="SELL", quantity=2,
                           price=1600.0, group_id=gid, target_price=0.0)
        db_session.commit()

        h = _holding(db_session, 1, "INFY")
        assert h is not None
        assert (_f(h.shares), _f(h.target_price)) == (9.0, 4000.0)

    def test_zero_target_on_new_row_is_stored_as_none(self, db_session):
        gid = int(_make_group(db_session).id)  # type: ignore[arg-type]
        record_transaction(user_id=1, ticker="TCS", transaction_type="BUY", quantity=1,
                           price=3500.0, group_id=gid, target_price=0.0)
        db_session.commit()

        h = _holding(db_session, 1, "TCS")
        assert h is not None
        assert h.target_price is None

    def test_out_of_order_inserts_follow_trade_dates(self, db_session):
        """MATH-11: a back-dated BUY keeps its trade date; the replay is date-ordered."""
        gid = int(_make_group(db_session).id)  # type: ignore[arg-type]
        for tx_type, qty, when in [("BUY", 10, datetime(2025, 3, 1)), ("BUY", 10, datetime(2025, 1, 1)),
                                   ("SELL", 15, datetime(2025, 4, 1))]:
            record_transaction(user_id=1, ticker="ITC", transaction_type=tx_type, quantity=qty, price=400.0,
                               group_id=gid, date=when.replace(tzinfo=timezone.utc))
        db_session.commit()

        h = _holding(db_session, 1, "ITC")
        assert h is not None and _f(h.shares) == 5.0
        txns = sorted(session_query_all(db_session, "ITC", 1), key=lambda t: int(t.id))  # type: ignore[arg-type]
        assert [t.date.date() for t in txns] == [  # type: ignore[union-attr]
            datetime(2025, 3, 1).date(), datetime(2025, 1, 1).date(), datetime(2025, 4, 1).date(),
        ]

    def test_split_applies_by_trade_date(self, db_session):
        """Pre-split BUY 10, post-split BUY 5, then the 2:1 SPLIT entered last: 25 shares, not 30."""
        gid = int(_make_group(db_session).id)  # type: ignore[arg-type]
        for tx_type, qty, price, when in [("BUY", 10, 200.0, datetime(2023, 1, 1)),
                                          ("BUY", 5, 100.0, datetime(2025, 1, 1)),
                                          ("SPLIT", 2, 0.0, datetime(2024, 1, 1))]:
            record_transaction(user_id=1, ticker="TCS", transaction_type=tx_type, quantity=qty, price=price,
                               group_id=gid, date=when.replace(tzinfo=timezone.utc))
        db_session.commit()

        h = _holding(db_session, 1, "TCS")
        assert h is not None and _f(h.shares) == 25.0

    def test_back_dated_trade_before_edit_is_dated_at_the_edit(self, db_session):
        """An edit (ADJUST) is an absolute restatement: an older trade entered after it
        is applied on top of it, never silently absorbed."""
        gid = int(_make_group(db_session).id)  # type: ignore[arg-type]
        record_transaction(user_id=1, ticker="SBIN", transaction_type="BUY", quantity=10, price=600.0,
                           group_id=gid, date=datetime(2025, 1, 1, tzinfo=timezone.utc))
        db_session.commit()
        assert adjust_position(1, "SBIN", 40, 550.0) is not None
        record_transaction(user_id=1, ticker="SBIN", transaction_type="BUY", quantity=5, price=500.0,
                           group_id=gid, date=datetime(2024, 1, 1, tzinfo=timezone.utc))
        db_session.commit()

        h = _holding(db_session, 1, "SBIN")
        assert h is not None and _f(h.shares) == 45.0

    @pytest.mark.parametrize("raw", ["05-Mar-2025", "2025-03-05"])
    def test_purchase_date_formats(self, raw):
        from services.ledger_service import parse_trade_date

        assert parse_trade_date(raw) == datetime(2025, 3, 5, tzinfo=timezone.utc)

    def test_purchase_date_future_or_garbage_rejected(self):
        from services.ledger_service import parse_trade_date

        future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")
        for bad in (future, "31/12/2024"):
            with pytest.raises(ValueError):
                parse_trade_date(bad)
        assert parse_trade_date("  ") is None

    def test_future_dated_trade_is_clamped_so_remove_sticks(self, db_session):
        """A BUY dated ahead of now must not replay after close_position's ADJUST."""
        gid = int(_make_group(db_session).id)  # type: ignore[arg-type]
        record_transaction(user_id=1, ticker="HDFCBANK", transaction_type="BUY", quantity=5,
                           price=1600.0, group_id=gid,
                           date=datetime.now(timezone.utc) + timedelta(hours=3))
        db_session.commit()

        assert close_position(1, "HDFCBANK") is True
        db_session.commit()
        assert _holding(db_session, 1, "HDFCBANK") is None


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_client():
    """FastAPI TestClient with an isolated SQLite test DB."""
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_test.db")

    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_user(test_client):
    """Register + login a test user, return (user_id, Bearer headers)."""
    import uuid
    tag = uuid.uuid4().hex[:8]
    email = f"ledger_test_{tag}@example.com"
    pw = "Test1234!"

    username = f"ledger_{tag}"
    r = test_client.post("/register", json={
        "username": username, "password": pw, "display_name": f"LedgerTest {tag}",
        **REGISTER_CONSENT,
    })
    assert r.status_code in (200, 201, 400)  # 400 if already exists

    r = test_client.post("/login", json={"username": username, "password": pw})
    assert r.status_code == 200, r.text

    token = r.json().get("access_token") or r.json().get("token")
    assert token, "login returned no token"
    # /login returns the user id (there is no /me route).
    return r.json()["user_id"], {"Authorization": f"Bearer {token}"}


class TestTransactionsEndpoint:
    def test_transactions_endpoint_requires_auth(self, test_client):
        """Endpoint rejects missing/invalid tokens with 401."""
        r = test_client.get(
            "/portfolio/transactions/RELIANCE",
            params={"user_id": 999},
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert r.status_code == 401

    def test_transactions_endpoint_returns_list(self, test_client, auth_user):
        """Authenticated request returns a JSON list (possibly empty)."""
        user_id, auth_headers = auth_user

        r = test_client.get(
            "/portfolio/transactions/TESTSTOCK",
            params={"user_id": user_id},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_no_western_scale_in_responses(self, test_client, auth_user):
        """Portfolio responses must not contain Million/Billion/Trillion."""
        user_id, auth_headers = auth_user

        r = test_client.get(
            "/portfolio/transactions/TESTSTOCK",
            params={"user_id": user_id},
            headers=auth_headers,
        )
        body = r.text.lower()
        forbidden = ["million", "billion", "trillion"]
        for word in forbidden:
            assert word not in body, f"Western scale word '{word}' found in response"


# ---------------------------------------------------------------------------
# DB-09: date-ordered validation, (user, ticker) replay key, idempotency,
# single default group, 422 instead of 500
# ---------------------------------------------------------------------------

from datetime import timedelta  # noqa: E402

from sqlalchemy.exc import IntegrityError  # noqa: E402

from services.ledger_service import LedgerError  # noqa: E402


def _trade(user_id, group_id, ticker, tx_type, qty, price, date=None, client_request_id=None):
    return record_transaction(
        user_id=user_id, ticker=ticker, transaction_type=tx_type, quantity=qty, price=price,
        group_id=group_id, company_name="Test Co", date=date, client_request_id=client_request_id,
    )


class TestLedgerConsistency:
    def test_backdated_sell_before_buy_rejected(self, db_session):
        g = _make_group(db_session)
        db_session.commit()
        now = datetime.now(timezone.utc)
        _trade(1, g.id, "TCS", "BUY", 10, 3500.0, date=now)

        with pytest.raises(LedgerError, match="only 0.0 shares held"):
            _trade(1, g.id, "TCS", "SELL", 5, 3600.0, date=now - timedelta(days=1))

        assert [t.transaction_type for t in session_query_all(db_session, "TCS", 1)] == ["BUY"]
        h = _holding(db_session, 1, "TCS")
        assert h is not None and _f(h.shares) == 10.0

    def test_sell_invalidating_later_sell_rejected(self, db_session):
        """BUY 100 (t-3), SELL 80 (t-1); a SELL 30 backdated to t-2 would leave the
        t-1 SELL short, so it is rejected."""
        g = _make_group(db_session)
        db_session.commit()
        now = datetime.now(timezone.utc)
        _trade(1, g.id, "INFY", "BUY", 100, 1500.0, date=now - timedelta(days=3))
        _trade(1, g.id, "INFY", "SELL", 80, 1600.0, date=now - timedelta(days=1))

        with pytest.raises(LedgerError):
            _trade(1, g.id, "INFY", "SELL", 30, 1550.0, date=now - timedelta(days=2))

        assert len(session_query_all(db_session, "INFY", 1)) == 2
        h = _holding(db_session, 1, "INFY")
        assert h is not None and _f(h.shares) == 20.0

    def test_two_groups_same_ticker_single_row(self, db_session):
        default = _make_group(db_session)
        other = PortfolioGroup(user_id=1, name="Speculative", is_default=False)
        db_session.add(other)
        db_session.commit()

        _trade(1, default.id, "SBIN", "BUY", 10, 600.0)
        _trade(1, other.id, "SBIN", "BUY", 5, 700.0)

        rows = db_session.query(Portfolio).filter_by(user_id=1, ticker="SBIN", group_name="holdings").all()
        assert len(rows) == 1
        assert _f(rows[0].shares) == 15.0
        assert round(_f(rows[0].buy_price), 2) == 633.33  # (10*600 + 5*700) / 15

    def test_idempotent_replay(self, db_session):
        g = _make_group(db_session)
        db_session.commit()

        first = _trade(1, g.id, "ITC", "BUY", 10, 400.0, client_request_id="req-1")
        again = _trade(1, g.id, "ITC", "BUY", 10, 400.0, client_request_id="req-1")

        assert int(again.id) == int(first.id)  # type: ignore[arg-type]
        assert len(session_query_all(db_session, "ITC", 1)) == 1
        h = _holding(db_session, 1, "ITC")
        assert h is not None and _f(h.shares) == 10.0

    def test_fractional_sell_closes_position(self, db_session):
        """The read model keeps full precision, so selling every fractional unit closes it (MATH-20)."""
        g = _make_group(db_session)
        db_session.commit()

        _buy(1, g.id, "NIFTYBEES", 10.125, 250.0)
        db_session.commit()
        h = _holding(db_session, 1, "NIFTYBEES")
        assert h is not None and _f(h.shares) == pytest.approx(10.125, abs=1e-9)

        _sell(1, g.id, "NIFTYBEES", 10.125, 260.0)
        db_session.commit()
        assert _holding(db_session, 1, "NIFTYBEES") is None

    def test_wac_keeps_precision(self, db_session):
        """WAC is stored unrounded: (900.09 + 100.003) / 10 = 100.0093, not 100.01 (MATH-20)."""
        g = _make_group(db_session)
        db_session.commit()

        for price in (100.0, 100.01, 100.02):
            _buy(1, g.id, "IDEA", 3, price)
        _buy(1, g.id, "IDEA", 1, 100.003)
        db_session.commit()

        h = _holding(db_session, 1, "IDEA")
        assert h is not None
        assert abs(_f(h.buy_price) - 100.0093) < 1e-6
        assert _f(h.shares) == 10.0

    def test_default_group_unique(self, db_session):
        _make_group(db_session)
        db_session.commit()

        db_session.add(PortfolioGroup(user_id=1, name="Legacy Holdings", is_default=True))
        with pytest.raises(IntegrityError):
            db_session.flush()


def _api_user_headers() -> tuple[int, dict]:
    import database
    from uuid import uuid4
    from models.db_models import User

    with database.get_session() as session:
        user = User(username=f"ledger_{uuid4().hex[:12]}", password_hash="x", display_name="Ledger API")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


class TestAddEndpointErrors:
    def test_add_nan_shares_422(self, client):
        user_id, headers = _api_user_headers()
        # Raw body: the JSON encoder refuses NaN, the server's json.loads accepts it.
        body = (
            f'{{"user_id": {user_id}, "ticker": "TCS", "company_name": "TCS",'
            ' "shares": NaN, "buy_price": 100.0}'
        )

        resp = client.post("/portfolio/add", content=body,
                           headers={**headers, "Content-Type": "application/json"})

        assert resp.status_code == 422, resp.text

    def test_oversell_returns_422(self, client):
        from unittest.mock import patch

        user_id, headers = _api_user_headers()
        payload = {"user_id": user_id, "ticker": "HDFCBANK", "company_name": "HDFC Bank",
                   "shares": 10.0, "buy_price": 1500.0}
        with patch("routers.portfolio._yf_price", return_value=(1550.0, 1540.0)):
            bought = client.post("/portfolio/add", json=payload, headers=headers)
            oversold = client.post("/portfolio/add", json={**payload, "shares": 15.0, "transaction_type": "SELL"},
                                   headers=headers)

        assert bought.status_code == 200, bought.text
        assert oversold.status_code == 422, oversold.text
        assert "only 10.0 shares held" in oversold.json()["detail"]

    def test_paper_trade_rejected_without_ledger_write(self, client):
        """Paper trades would merge into the real holding row, so they are refused (MATH-10)."""
        from services.ledger_service import get_transactions_for_ticker

        user_id, headers = _api_user_headers()
        payload = {"user_id": user_id, "ticker": "INFY", "company_name": "Infosys",
                   "shares": 10.0, "buy_price": 1500.0, "is_virtual": True}

        resp = client.post("/portfolio/add", json=payload, headers=headers)

        assert resp.status_code == 400, resp.text
        assert "Paper trades" in resp.json()["detail"]
        assert get_transactions_for_ticker(user_id, "INFY") == []

    def test_idempotency_key_header_dedupes(self, client):
        from unittest.mock import patch
        from services.ledger_service import get_transactions_for_ticker

        user_id, headers = _api_user_headers()
        payload = {"user_id": user_id, "ticker": "WIPRO", "company_name": "Wipro",
                   "shares": 3.0, "buy_price": 450.0}
        with patch("routers.portfolio._yf_price", return_value=(455.0, 450.0)):
            for _ in range(2):
                resp = client.post("/portfolio/add", json=payload, headers={**headers, "Idempotency-Key": "retry-1"})
                assert resp.status_code == 200, resp.text

        assert len(get_transactions_for_ticker(user_id, "WIPRO")) == 1


@pytest.mark.skipif(
    not __import__("os").environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="row-level concurrency needs Postgres (SQLite serialises writers)",
)
def test_concurrent_sells_exactly_one_succeeds():
    import threading

    user_id, _ = _api_user_headers()
    record_transaction(user_id=user_id, ticker="NTPC", transaction_type="BUY", quantity=100, price=300.0)
    outcomes: list[str] = []

    def sell():
        try:
            record_transaction(user_id=user_id, ticker="NTPC", transaction_type="SELL", quantity=60, price=310.0)
            outcomes.append("ok")
        except LedgerError:
            outcomes.append("rejected")

    threads = [threading.Thread(target=sell) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["ok", "rejected"]


# ---------------------------------------------------------------------------
# GH-647: record_transaction(session=...) writes into the caller's session
# ---------------------------------------------------------------------------

def test_record_transaction_with_session_leaves_commit_to_caller(db_session):
    tx = record_transaction(user_id=1, ticker="SESS", transaction_type="BUY", quantity=5,
                            price=100.0, company_name="Test Co", session=db_session)
    assert tx.id is not None  # flushed
    assert _holding(db_session, 1, "SESS") is not None

    db_session.rollback()  # the caller owns the transaction
    assert db_session.query(Transaction).filter_by(ticker="SESS").count() == 0
    assert _holding(db_session, 1, "SESS") is None
