"""Database contract tests for constraints, rollback, and precision."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError


def _username(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def test_get_session_rolls_back_failed_transaction():
    import database
    from models.db_models import User

    username = _username("rollback")

    with pytest.raises(RuntimeError):
        with database.get_session() as session:
            session.add(User(username=username, password_hash="x", display_name="Rollback"))
            raise RuntimeError("force rollback")

    with database.get_session() as session:
        assert session.query(User).filter_by(username=username).count() == 0


def test_user_username_unique_constraint_is_enforced():
    import database
    from models.db_models import User

    username = _username("unique_user")
    with database.get_session() as session:
        session.add(User(username=username, password_hash="x", display_name="First"))
        session.commit()

    with pytest.raises(IntegrityError):
        with database.get_session() as session:
            session.add(User(username=username, password_hash="y", display_name="Second"))
            session.commit()


def test_portfolio_requires_existing_user_id():
    import database
    from models.db_models import Portfolio

    with pytest.raises(IntegrityError):
        with database.get_session() as session:
            session.add(
                Portfolio(
                    user_id=987654321,
                    ticker="RELIANCE",
                    company_name="Reliance Industries Ltd",
                    shares=Decimal("1.0000"),
                    buy_price=Decimal("2500.0000"),
                    group_name="holdings",
                )
            )
            session.commit()


def test_portfolio_duplicate_user_ticker_group_is_rejected():
    import database
    from models.db_models import Portfolio, User

    username = _username("portfolio_unique")
    with database.get_session() as session:
        user = User(username=username, password_hash="x", display_name="Portfolio")
        session.add(user)
        session.flush()
        session.add(
            Portfolio(
                user_id=user.id,
                ticker="TCS",
                company_name="Tata Consultancy Services",
                shares=Decimal("2.0000"),
                buy_price=Decimal("1000.0000"),
                group_name="holdings",
            )
        )
        session.commit()
        user_id = user.id

    with pytest.raises(IntegrityError):
        with database.get_session() as session:
            session.add(
                Portfolio(
                    user_id=user_id,
                    ticker="TCS",
                    company_name="Tata Consultancy Services",
                    shares=Decimal("3.0000"),
                    buy_price=Decimal("1100.0000"),
                    group_name="holdings",
                )
            )
            session.commit()


@pytest.mark.xfail(strict=True, reason="DB-25: money columns are Float; Numeric(18,4) migration pending")
def test_money_columns_round_trip_as_decimal_with_four_places():
    import database
    from models.db_models import Portfolio, User

    username = _username("decimal_money")
    with database.get_session() as session:
        user = User(username=username, password_hash="x", display_name="Decimal")
        session.add(user)
        session.flush()
        holding = Portfolio(
            user_id=user.id,
            ticker="SBIN",
            company_name="State Bank of India",
            shares=Decimal("1.2345"),
            buy_price=Decimal("123.4567"),
            group_name="holdings",
        )
        session.add(holding)
        session.commit()
        holding_id = holding.id

    with database.get_session() as session:
        saved = session.get(Portfolio, holding_id)
        assert saved.shares == Decimal("1.2345")
        assert saved.buy_price == Decimal("123.4567")
