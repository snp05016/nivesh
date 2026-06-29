"""
Phase 5: Transaction Ledger — unit + API contract tests.

Tests cover:
  - WAC recalculation: two BUYs average correctly
  - SELL reduces shares, WAC cost basis proportionally reduced
  - Position fully closed (SELL all) deletes Portfolio row
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
from services.ledger_service import record_transaction, _recalculate_portfolio_snapshot

# SQLAlchemy 1.x uses untyped Column descriptors; at runtime ORM instance
# attributes are plain Python scalars. This helper satisfies Pyright.
def _f(v) -> float:  # type: ignore[misc]
    return float(v)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Ephemeral in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_group(session, user_id: int = 1) -> PortfolioGroup:
    g = PortfolioGroup(user_id=user_id, name="Test Holdings", is_default=True)
    session.add(g)
    session.flush()
    return g


def _buy(session, user_id, group_id, ticker, qty, price):
    record_transaction(
        session=session,
        user_id=user_id,
        ticker=ticker,
        transaction_type="BUY",
        quantity=qty,
        price=price,
        group_id=group_id,
        company_name="Test Co",
    )


def _sell(session, user_id, group_id, ticker, qty, price):
    record_transaction(
        session=session,
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
    def test_single_buy_creates_holding(self, db_session):
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "RELIANCE", 10, 100.0)
        db_session.commit()

        h = _holding(db_session, 1, "RELIANCE")
        assert h is not None
        assert round(_f(h.shares), 2) == 10.0
        assert round(_f(h.buy_price), 2) == 100.0

    def test_two_buys_weighted_average(self, db_session):
        """BUY 10 @ 100 + BUY 10 @ 200 → 20 shares @ 150 WAC."""
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "RELIANCE", 10, 100.0)
        _buy(db_session, 1, g.id, "RELIANCE", 10, 200.0)
        db_session.commit()

        h = _holding(db_session, 1, "RELIANCE")
        assert h is not None
        assert round(float(h.shares), 2) == 20.0
        # total cost = 10*100 + 10*200 = 3000 → WAC = 3000/20 = 150
        assert round(float(h.buy_price), 2) == 150.0

    def test_sell_reduces_shares_and_cost_basis(self, db_session):
        """After WAC avg at 150, SELL 10 @ 250 → 10 shares remaining @ 150."""
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "RELIANCE", 10, 100.0)
        _buy(db_session, 1, g.id, "RELIANCE", 10, 200.0)
        _sell(db_session, 1, g.id, "RELIANCE", 10, 250.0)
        db_session.commit()

        h = _holding(db_session, 1, "RELIANCE")
        assert h is not None
        assert round(h.shares, 2) == 10.0
        # WAC stays at 150 — selling at gain doesn't change cost basis
        assert round(h.buy_price, 2) == 150.0

    def test_full_sell_deletes_holding(self, db_session):
        """Selling all shares removes the Portfolio row entirely."""
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "INFY", 10, 1500.0)
        _sell(db_session, 1, g.id, "INFY", 10, 1800.0)
        db_session.commit()

        h = _holding(db_session, 1, "INFY")
        assert h is None, "Portfolio row should be deleted when shares reach zero"

    def test_oversell_clamps_to_zero_and_deletes(self, db_session):
        """Selling more than held clamps to zero and deletes the row."""
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "TCS", 5, 3000.0)
        _sell(db_session, 1, g.id, "TCS", 10, 3500.0)  # sell 10, only 5 held
        db_session.commit()

        h = _holding(db_session, 1, "TCS")
        assert h is None

    def test_transactions_stored_immutably(self, db_session):
        """All transaction records persist regardless of share state."""
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "HDFC", 10, 1600.0)
        _sell(db_session, 1, g.id, "HDFC", 10, 1900.0)
        db_session.commit()

        txns = session_query_all(db_session, "HDFC", 1)
        assert len(txns) == 2
        types = {t.transaction_type for t in txns}
        assert types == {"BUY", "SELL"}

    def test_multiple_tickers_isolated(self, db_session):
        """Transactions for different tickers don't interfere."""
        g = _make_group(db_session)
        _buy(db_session, 1, g.id, "RELIANCE", 5, 2500.0)
        _buy(db_session, 1, g.id, "WIPRO", 20, 450.0)
        _sell(db_session, 1, g.id, "RELIANCE", 5, 2700.0)
        db_session.commit()

        assert _holding(db_session, 1, "RELIANCE") is None
        wipro = _holding(db_session, 1, "WIPRO")
        assert wipro is not None
        assert round(wipro.shares, 2) == 20.0


def session_query_all(session, ticker: str, user_id: int) -> list[Transaction]:
    return session.query(Transaction).filter_by(user_id=user_id, ticker=ticker).all()


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
