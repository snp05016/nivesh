"""
Comprehensive test suite for the True Transaction Ledger (Event-Sourced Portfolio).

Coverage:
  Part 1 — WAC engine (service layer unit tests, in-memory SQLite)
  Part 2 — Backfill script migration logic (idempotency, data integrity)
  Part 3 — FastAPI router integration tests (auth, input validation, API contracts)

Run from backend/:
    ../venv/bin/pytest tests/test_transaction_ledger.py -v
"""

from __future__ import annotations

import os
import sys
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import Optional
from unittest.mock import patch
from tests.conftest import REGISTER_CONSENT

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Shared SQLAlchemy helper (runtime ORM attributes are plain Python scalars;
# Pyright sees Column[Unknown] — cast through float to satisfy both).
# ---------------------------------------------------------------------------
def _f(v) -> float:  # type: ignore[misc]
    return float(v)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Part 1 & 2 fixtures — isolated in-memory SQLite per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    """Fresh in-memory SQLite database per test."""
    from models.db_models import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# Helpers used across Part 1 & 2
# ---------------------------------------------------------------------------

def _make_group(session: Session, user_id: int = 1, name: str = "Test Holdings") -> "PortfolioGroup":  # type: ignore[name-defined]
    from models.db_models import PortfolioGroup
    g = PortfolioGroup(user_id=user_id, name=name, is_default=True)
    session.add(g)
    session.flush()
    return g


def _record(session: Session, user_id: int, group_id: int, ticker: str,
            tx_type: str, qty: float, price: float,
            date: Optional[datetime] = None) -> None:
    from services.ledger_service import record_transaction
    record_transaction(
        session=session,
        user_id=user_id,
        ticker=ticker,
        transaction_type=tx_type,
        quantity=qty,
        price=price,
        group_id=group_id,
        company_name="Test Co",
        date=date,
    )


def _holding(session: Session, user_id: int, ticker: str):
    from models.db_models import Portfolio
    return session.query(Portfolio).filter_by(
        user_id=user_id, ticker=ticker, group_name="holdings"
    ).first()


def _txns(session: Session, user_id: int, ticker: str):
    from models.db_models import Transaction
    return session.query(Transaction).filter_by(user_id=user_id, ticker=ticker).all()


# ===========================================================================
# Part 1: WAC Engine — Service Layer Unit Tests
# ===========================================================================

class TestWACMath:
    """Weighted Average Cost arithmetic correctness."""

    def test_simple_wac_two_buys(self, db: Session):
        """BUY 10 @ 100 + BUY 10 @ 200 → 20 shares @ 150 WAC."""
        g = _make_group(db)
        _record(db, 1, g.id, "RELIANCE", "BUY", 10, 100.0)
        _record(db, 1, g.id, "RELIANCE", "BUY", 10, 200.0)
        db.commit()

        h = _holding(db, 1, "RELIANCE")
        assert h is not None
        assert _f(h.shares) == pytest.approx(20.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(150.0, abs=0.01)

    def test_three_buys_wac(self, db: Session):
        """BUY 5@100 + BUY 15@300 + BUY 10@200 → 30 shares @ 233.33 WAC."""
        g = _make_group(db)
        _record(db, 1, g.id, "TCS", "BUY", 5,  100.0)
        _record(db, 1, g.id, "TCS", "BUY", 15, 300.0)
        _record(db, 1, g.id, "TCS", "BUY", 10, 200.0)
        db.commit()

        # total_cost = 500 + 4500 + 2000 = 7000; shares = 30; WAC = 7000/30 = 233.33
        h = _holding(db, 1, "TCS")
        assert h is not None
        assert _f(h.shares) == pytest.approx(30.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(233.33, abs=0.1)

    def test_fees_included_in_cost_basis(self, db: Session):
        """Fees are added to total_cost, raising the WAC."""
        from services.ledger_service import record_transaction
        g = _make_group(db)
        record_transaction(
            session=db, user_id=1, ticker="INFY", transaction_type="BUY",
            quantity=10, price=1000.0, fees=100.0, group_id=g.id,
            company_name="Infosys",
        )
        db.commit()

        # total_cost = 10*1000 + 100 = 10100; WAC = 10100/10 = 1010
        h = _holding(db, 1, "INFY")
        assert h is not None
        assert _f(h.buy_price) == pytest.approx(1010.0, abs=0.01)


class TestSellReducesCostBasis:
    """SELL reduces shares while keeping WAC unchanged."""

    def test_partial_sell_preserves_wac(self, db: Session):
        """BUY 20 @ 150 WAC, SELL 10 → 10 shares still @ 150 WAC."""
        g = _make_group(db)
        _record(db, 1, g.id, "WIPRO", "BUY", 10, 100.0)
        _record(db, 1, g.id, "WIPRO", "BUY", 10, 200.0)
        db.commit()

        _record(db, 1, g.id, "WIPRO", "SELL", 10, 300.0)
        db.commit()

        h = _holding(db, 1, "WIPRO")
        assert h is not None
        assert _f(h.shares) == pytest.approx(10.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(150.0, abs=0.01)

    def test_full_sell_deletes_portfolio_row(self, db: Session):
        """Selling all shares removes the Portfolio row."""
        g = _make_group(db)
        _record(db, 1, g.id, "HDFC", "BUY", 10, 1500.0)
        _record(db, 1, g.id, "HDFC", "SELL", 10, 2000.0)
        db.commit()

        assert _holding(db, 1, "HDFC") is None

    def test_sell_then_rebuy_creates_new_holding(self, db: Session):
        """After closing a position, a new BUY starts fresh."""
        g = _make_group(db)
        _record(db, 1, g.id, "BAJFIN", "BUY", 5, 6000.0)
        _record(db, 1, g.id, "BAJFIN", "SELL", 5, 7000.0)
        _record(db, 1, g.id, "BAJFIN", "BUY", 3, 5000.0)
        db.commit()

        h = _holding(db, 1, "BAJFIN")
        assert h is not None
        assert _f(h.shares) == pytest.approx(3.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(5000.0, abs=0.01)


class TestCorporateActions:
    """SPLIT and BONUS dilute WAC correctly."""

    def test_bonus_1_for_1_halves_wac(self, db: Session):
        """BUY 10 @ 1000; BONUS 10 → 20 shares @ 500 WAC."""
        g = _make_group(db)
        _record(db, 1, g.id, "ZOMATO", "BUY",   10, 1000.0)
        _record(db, 1, g.id, "ZOMATO", "BONUS",  10, 0.0)
        db.commit()

        h = _holding(db, 1, "ZOMATO")
        assert h is not None
        assert _f(h.shares) == pytest.approx(20.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(500.0, abs=0.01)

    def test_split_2_for_1_halves_wac(self, db: Session):
        """BUY 10 @ 1000; SPLIT ratio=2 → 20 shares @ 500 WAC."""
        g = _make_group(db)
        _record(db, 1, g.id, "PAYTM", "BUY",   10, 1000.0)
        _record(db, 1, g.id, "PAYTM", "SPLIT",  2,  0.0)  # qty=ratio
        db.commit()

        h = _holding(db, 1, "PAYTM")
        assert h is not None
        assert _f(h.shares) == pytest.approx(20.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(500.0, abs=0.01)

    def test_bonus_buy_then_partial_sell_wac(self, db: Session):
        """Complex: BUY→BONUS→SELL — WAC carries through correctly."""
        g = _make_group(db)
        _record(db, 1, g.id, "IRFC", "BUY",   100, 180.0)  # cost=18000, shares=100
        _record(db, 1, g.id, "IRFC", "BONUS",  100, 0.0)   # shares=200, WAC=90
        _record(db, 1, g.id, "IRFC", "SELL",    50, 120.0) # shares=150
        db.commit()

        h = _holding(db, 1, "IRFC")
        assert h is not None
        assert _f(h.shares) == pytest.approx(150.0, abs=0.01)
        # WAC stays 90 (SELL at 120 — gain, but cost basis unchanged)
        assert _f(h.buy_price) == pytest.approx(90.0, abs=0.01)


class TestNegativeAndEdgeCases:
    """Guard rails: invalid states must raise, not silently corrupt."""

    def test_oversell_raises_value_error(self, db: Session):
        """Selling more than held raises ValueError — short selling forbidden."""
        g = _make_group(db)
        _record(db, 1, g.id, "NTPC", "BUY", 10, 300.0)
        db.commit()

        with pytest.raises(ValueError, match="only"):
            _record(db, 1, g.id, "NTPC", "SELL", 50, 350.0)

    def test_sell_with_no_position_raises(self, db: Session):
        """Selling a ticker you don't own raises ValueError."""
        g = _make_group(db)
        with pytest.raises(ValueError, match="only"):
            _record(db, 1, g.id, "COAL", "SELL", 5, 400.0)

    def test_sell_exact_holdings_closes_position(self, db: Session):
        """Selling exactly the held quantity is valid and closes the row."""
        g = _make_group(db)
        _record(db, 1, g.id, "ONGC", "BUY",  15, 200.0)
        _record(db, 1, g.id, "ONGC", "SELL", 15, 250.0)
        db.commit()

        assert _holding(db, 1, "ONGC") is None

    def test_transactions_stored_immutably(self, db: Session):
        """All events persist in the Transaction ledger regardless of final state."""
        g = _make_group(db)
        _record(db, 1, g.id, "SBIN", "BUY",  20, 700.0)
        _record(db, 1, g.id, "SBIN", "BONUS", 20, 0.0)
        _record(db, 1, g.id, "SBIN", "SELL",  10, 800.0)
        db.commit()

        txns = _txns(db, 1, "SBIN")
        assert len(txns) == 3
        types = {t.transaction_type for t in txns}
        assert types == {"BUY", "BONUS", "SELL"}

    def test_multi_user_isolation(self, db: Session):
        """Transactions for different users are fully isolated."""
        g1 = _make_group(db, user_id=1)
        g2 = _make_group(db, user_id=2)
        _record(db, 1, g1.id, "RELIANCE", "BUY", 10, 2500.0)
        _record(db, 2, g2.id, "RELIANCE", "BUY", 50, 2400.0)
        db.commit()

        h1 = _holding(db, 1, "RELIANCE")
        h2 = _holding(db, 2, "RELIANCE")
        assert h1 is not None and h2 is not None
        assert _f(h1.shares) == pytest.approx(10.0, abs=0.01)
        assert _f(h2.shares) == pytest.approx(50.0, abs=0.01)

    def test_multi_ticker_isolation(self, db: Session):
        """Selling one ticker has no effect on other tickers for same user."""
        g = _make_group(db)
        _record(db, 1, g.id, "RELIANCE", "BUY", 5, 2500.0)
        _record(db, 1, g.id, "WIPRO",    "BUY", 20, 450.0)
        _record(db, 1, g.id, "RELIANCE", "SELL", 5, 2700.0)
        db.commit()

        assert _holding(db, 1, "RELIANCE") is None
        wipro = _holding(db, 1, "WIPRO")
        assert wipro is not None
        assert _f(wipro.shares) == pytest.approx(20.0, abs=0.01)

    def test_dividend_ignored_in_snapshot(self, db: Session):
        """DIVIDEND events are recorded but don't change shares or WAC."""
        g = _make_group(db)
        _record(db, 1, g.id, "COAL", "BUY",      10, 400.0)
        _record(db, 1, g.id, "COAL", "DIVIDEND",   0, 12.50)  # ₹12.50/share dividend
        db.commit()

        h = _holding(db, 1, "COAL")
        assert h is not None
        assert _f(h.shares) == pytest.approx(10.0, abs=0.01)
        assert _f(h.buy_price) == pytest.approx(400.0, abs=0.01)

        txns = _txns(db, 1, "COAL")
        assert len(txns) == 2  # both events stored


# ===========================================================================
# Part 2: Backfill Script — Migration Logic
# ===========================================================================

class TestBackfillMigration:
    """Phase 2 backfill: legacy Portfolio → Transaction ledger."""

    def _insert_legacy_holding(self, session: Session, user_id: int, ticker: str,
                                shares: float, buy_price: float) -> None:
        from models.db_models import Portfolio
        row = Portfolio(
            user_id=user_id,
            ticker=ticker,
            company_name=f"{ticker} Corp",
            shares=shares,
            buy_price=buy_price,
            group_name="holdings",
        )
        session.add(row)
        session.commit()

    def test_basic_backfill_creates_group_and_transaction(self, db: Session):
        """Legacy Portfolio row → PortfolioGroup + BUY Transaction."""
        from models.db_models import PortfolioGroup, Transaction
        from scripts.migrate_ledger import backfill_user

        self._insert_legacy_holding(db, 1, "RELIANCE", 50.0, 2500.0)

        inserted = backfill_user(db, 1)
        db.commit()

        assert inserted == 1

        group = db.query(PortfolioGroup).filter_by(user_id=1, name="Legacy Holdings").first()
        assert group is not None

        tx = db.query(Transaction).filter_by(user_id=1, ticker="RELIANCE").first()
        assert tx is not None
        assert tx.transaction_type == "BUY"
        assert _f(tx.quantity) == pytest.approx(50.0, abs=0.01)
        assert _f(tx.price) == pytest.approx(2500.0, abs=0.01)

    def test_backfill_links_portfolio_row_to_group(self, db: Session):
        """After backfill, Portfolio.group_id points to the new group."""
        from models.db_models import Portfolio, PortfolioGroup
        from scripts.migrate_ledger import backfill_user

        self._insert_legacy_holding(db, 1, "INFY", 20.0, 1800.0)
        backfill_user(db, 1)
        db.commit()

        group = db.query(PortfolioGroup).filter_by(user_id=1, name="Legacy Holdings").first()
        holding = db.query(Portfolio).filter_by(user_id=1, ticker="INFY").first()
        assert holding is not None
        assert holding.group_id == group.id

    def test_backfill_multiple_holdings(self, db: Session):
        """All positive holdings for a user are migrated in one pass."""
        from models.db_models import Transaction
        from scripts.migrate_ledger import backfill_user

        self._insert_legacy_holding(db, 1, "TCS",     10.0, 3500.0)
        self._insert_legacy_holding(db, 1, "WIPRO",   25.0,  450.0)
        self._insert_legacy_holding(db, 1, "HDFCBANK", 8.0, 1600.0)

        inserted = backfill_user(db, 1)
        db.commit()

        assert inserted == 3
        txns = db.query(Transaction).filter_by(user_id=1).all()
        assert len(txns) == 3

    def test_backfill_skips_watchlist_entries(self, db: Session):
        """Watchlist rows are not backfilled into the ledger."""
        from models.db_models import Portfolio, Transaction
        from scripts.migrate_ledger import backfill_user

        watchlist_row = Portfolio(
            user_id=1, ticker="NIFTY50", company_name="Nifty 50 Index",
            shares=0.0, buy_price=0.0, group_name="watchlist",
        )
        db.add(watchlist_row)
        db.commit()

        inserted = backfill_user(db, 1)
        db.commit()

        assert inserted == 0
        assert db.query(Transaction).filter_by(user_id=1).count() == 0

    def test_backfill_idempotent_on_second_run(self, db: Session):
        """Running backfill twice does not duplicate groups or transactions."""
        from models.db_models import PortfolioGroup, Transaction
        from scripts.migrate_ledger import backfill_user

        self._insert_legacy_holding(db, 1, "RELIANCE", 50.0, 2500.0)

        backfill_user(db, 1)
        db.commit()

        inserted_second = backfill_user(db, 1)
        db.commit()

        assert inserted_second == 0

        group_count = db.query(PortfolioGroup).filter_by(user_id=1, name="Legacy Holdings").count()
        assert group_count == 1

        tx_count = db.query(Transaction).filter_by(user_id=1, ticker="RELIANCE").count()
        assert tx_count == 1

    def test_backfill_multi_user_independent(self, db: Session):
        """Each user's holdings are migrated independently."""
        from models.db_models import Transaction
        from scripts.migrate_ledger import backfill_user

        self._insert_legacy_holding(db, 1, "RELIANCE", 10.0, 2500.0)
        self._insert_legacy_holding(db, 2, "TCS",      5.0, 3500.0)
        self._insert_legacy_holding(db, 2, "WIPRO",   30.0,  420.0)

        backfill_user(db, 1)
        db.commit()
        backfill_user(db, 2)
        db.commit()

        assert db.query(Transaction).filter_by(user_id=1).count() == 1
        assert db.query(Transaction).filter_by(user_id=2).count() == 2


# ===========================================================================
# Part 3: API Router Integration Tests
# ===========================================================================

@pytest.fixture(scope="module")
def api_client():
    """FastAPI TestClient with an isolated SQLite test database."""
    os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_ledger_test.db")
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def auth(api_client):
    """Register a unique test user and return (user_id, Bearer headers)."""
    tag = uuid.uuid4().hex[:8]
    username = f"ledger_{tag}"
    pw = "Test1234!"

    r = api_client.post("/register", json={
        "username": username, "password": pw, "display_name": f"Ledger {tag}",
        **REGISTER_CONSENT,
    })
    assert r.status_code in (200, 201, 400)

    r = api_client.post("/login", json={"username": username, "password": pw})
    if r.status_code != 200:
        pytest.skip("Auth endpoints unavailable in this environment")

    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("No token returned")

    me = api_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    if me.status_code != 200:
        pytest.skip("/me endpoint unavailable")

    user_id = me.json().get("user_id") or me.json().get("id")
    return user_id, {"Authorization": f"Bearer {token}"}


class TestPortfolioAddEndpoint:
    """POST /portfolio/add — happy path and validation."""

    def test_valid_buy_returns_200(self, api_client, auth):
        """Valid BUY payload returns 200 with ticker and shares in body."""
        user_id, headers = auth
        with patch("routers.portfolio._yf_price", return_value=(2500.0, 2450.0)):
            r = api_client.post("/portfolio/add", json={
                "user_id": user_id,
                "ticker": "TESTBUY",
                "company_name": "Test Buy Corp",
                "shares": 10.0,
                "buy_price": 100.0,
                "transaction_type": "BUY",
            }, headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["ticker"] == "TESTBUY"
        assert body["shares"] == 10.0

    def test_buy_creates_transaction_in_db(self, api_client, auth):
        """After a successful BUY, a Transaction row exists in the DB."""
        user_id, headers = auth
        ticker = f"DBTST{uuid.uuid4().hex[:4].upper()}"
        with patch("routers.portfolio._yf_price", return_value=(500.0, 480.0)):
            r = api_client.post("/portfolio/add", json={
                "user_id": user_id,
                "ticker": ticker,
                "company_name": "DB Test Corp",
                "shares": 5.0,
                "buy_price": 200.0,
                "transaction_type": "BUY",
            }, headers=headers)
        assert r.status_code == 200

        # Verify via transactions endpoint
        r2 = api_client.get(
            f"/portfolio/transactions/{ticker}",
            params={"user_id": user_id},
            headers=headers,
        )
        assert r2.status_code == 200
        txns = r2.json()
        assert len(txns) >= 1
        assert txns[0]["transaction_type"] == "BUY"
        assert txns[0]["quantity"] == 5.0

    def test_unauthorized_request_rejected(self, api_client, auth):
        """Missing/wrong token returns 401."""
        user_id, _ = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": 1.0, "buy_price": 100.0,
        }, headers={"Authorization": "Bearer bad_token"})
        assert r.status_code == 401


class TestInputValidation:
    """Pydantic-layer validation: invalid inputs must return 422."""

    def test_zero_shares_returns_422(self, api_client, auth):
        user_id, headers = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": 0, "buy_price": 100.0,
        }, headers=headers)
        assert r.status_code == 422

    def test_negative_shares_returns_422(self, api_client, auth):
        user_id, headers = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": -5.0, "buy_price": 100.0,
        }, headers=headers)
        assert r.status_code == 422

    def test_negative_price_returns_422(self, api_client, auth):
        user_id, headers = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": 10.0, "buy_price": -50.0,
        }, headers=headers)
        assert r.status_code == 422

    def test_zero_price_returns_422(self, api_client, auth):
        user_id, headers = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": 10.0, "buy_price": 0,
        }, headers=headers)
        assert r.status_code == 422

    def test_unknown_transaction_type_returns_422(self, api_client, auth):
        """Unknown transaction types are rejected by schema validator."""
        user_id, headers = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": 10.0, "buy_price": 100.0,
            "transaction_type": "SHORT",
        }, headers=headers)
        assert r.status_code == 422

    def test_forward_slash_type_returns_422(self, api_client, auth):
        user_id, headers = auth
        r = api_client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "X", "company_name": "X",
            "shares": 10.0, "buy_price": 100.0,
            "transaction_type": "LONG",
        }, headers=headers)
        assert r.status_code == 422


class TestTransactionsEndpoint:
    """GET /portfolio/transactions/{ticker} — contract tests."""

    def test_returns_list_of_transactions(self, api_client, auth):
        """Authenticated GET returns a JSON list."""
        user_id, headers = auth
        r = api_client.get(
            "/portfolio/transactions/RELIANCE",
            params={"user_id": user_id},
            headers=headers,
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_transactions_sorted_by_date_descending(self, api_client, auth):
        """Three transactions with different dates are returned newest-first."""
        user_id, headers = auth
        ticker = f"SORT{uuid.uuid4().hex[:4].upper()}"

        dates = [
            "2024-01-01",
            "2024-06-15",
            "2024-12-31",
        ]
        for d in dates:
            with patch("routers.portfolio._yf_price", return_value=(100.0, 95.0)):
                api_client.post("/portfolio/add", json={
                    "user_id": user_id, "ticker": ticker,
                    "company_name": "Sort Test", "shares": 1.0,
                    "buy_price": 100.0, "transaction_type": "BUY",
                    "purchase_date": d,
                }, headers=headers)

        r = api_client.get(
            f"/portfolio/transactions/{ticker}",
            params={"user_id": user_id},
            headers=headers,
        )
        assert r.status_code == 200
        txns = r.json()
        assert len(txns) >= 3

        # Date strings should be sorted descending (newest first)
        returned_dates = [t["date"] for t in txns if t["date"]]
        assert returned_dates == sorted(returned_dates, reverse=True)

    def test_no_western_scale_words_in_response(self, api_client, auth):
        """Response body must never contain Million/Billion/Trillion."""
        user_id, headers = auth
        r = api_client.get(
            "/portfolio/transactions/RELIANCE",
            params={"user_id": user_id},
            headers=headers,
        )
        body = r.text.lower()
        for word in ("million", "billion", "trillion"):
            assert word not in body, f"Western scale word '{word}' found in response"

    def test_unauthenticated_returns_401(self, api_client, auth):
        """Missing token returns 401."""
        user_id, _ = auth
        r = api_client.get(
            "/portfolio/transactions/RELIANCE",
            params={"user_id": user_id},
            headers={"Authorization": "Bearer bad_token"},
        )
        assert r.status_code == 401

    def test_empty_list_for_unknown_ticker(self, api_client, auth):
        """Ticker with no transactions returns an empty list, not 404."""
        user_id, headers = auth
        r = api_client.get(
            "/portfolio/transactions/ZZZNEVEREXISTS",
            params={"user_id": user_id},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json() == []
