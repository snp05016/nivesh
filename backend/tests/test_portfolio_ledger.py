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
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
        assert _f(h.buy_price) == 3214.29

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
def auth_headers(test_client):
    """Register + login a test user, return Bearer headers."""
    import uuid
    tag = uuid.uuid4().hex[:8]
    email = f"ledger_test_{tag}@example.com"
    pw = "Test1234!"

    username = f"ledger_{tag}"
    r = test_client.post("/register", json={
        "username": username, "password": pw, "display_name": f"LedgerTest {tag}"
    })
    assert r.status_code in (200, 201, 400)  # 400 if already exists

    r = test_client.post("/login", json={"username": username, "password": pw})
    if r.status_code != 200:
        pytest.skip("Auth endpoint unavailable in this test environment")

    token = r.json().get("access_token") or r.json().get("token")
    if not token:
        pytest.skip("No token returned — skipping API tests")
    return {"Authorization": f"Bearer {token}"}


class TestTransactionsEndpoint:
    def test_transactions_endpoint_requires_auth(self, test_client):
        """Endpoint rejects missing/invalid tokens with 401."""
        r = test_client.get(
            "/portfolio/transactions/RELIANCE",
            params={"user_id": 999},
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert r.status_code == 401

    def test_transactions_endpoint_returns_list(self, test_client, auth_headers):
        """Authenticated request returns a JSON list (possibly empty)."""
        # Get user_id from /auth/me or similar
        me = test_client.get("/me", headers=auth_headers)
        if me.status_code != 200:
            pytest.skip("No /auth/me endpoint available")
        user_id = me.json().get("user_id") or me.json().get("id")

        r = test_client.get(
            "/portfolio/transactions/TESTSTOCK",
            params={"user_id": user_id},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_no_western_scale_in_responses(self, test_client, auth_headers):
        """Portfolio responses must not contain Million/Billion/Trillion."""
        me = test_client.get("/me", headers=auth_headers)
        if me.status_code != 200:
            pytest.skip("No /auth/me endpoint")
        user_id = me.json().get("user_id") or me.json().get("id")

        r = test_client.get(
            "/portfolio/transactions/TESTSTOCK",
            params={"user_id": user_id},
            headers=auth_headers,
        )
        body = r.text.lower()
        forbidden = ["million", "billion", "trillion"]
        for word in forbidden:
            assert word not in body, f"Western scale word '{word}' found in response"
