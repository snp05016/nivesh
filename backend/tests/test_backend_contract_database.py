"""Database invariants, relationships, precision, and documented gaps."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models.db_models import (
    Base,
    AnalysisHistory,
    NetWorthLedger,
    Portfolio,
    PortfolioValuationHistory,
    PriceTarget,
    TradeJournal,
    User,
)


@pytest.fixture()
def isolated_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _user(session, username: str = "db_audit") -> User:
    user = User(username=username, password_hash="hash", display_name="DB Audit")
    session.add(user)
    session.commit()
    return user


def test_core_tables_are_declared_in_metadata():
    expected = {
        "users",
        "portfolio",
        "analysis_history",
        "analysis_jobs",
        "price_targets",
        "trade_journal",
        "device_tokens",
        "portfolio_valuation_history",
        "net_worth_ledger",
        "earnings_alerts",
        "advisor_insights",
        "news_articles",
    }

    assert expected <= set(Base.metadata.tables)


def test_user_delete_cascades_owned_core_rows(isolated_session):
    user = _user(isolated_session, "cascade_user")
    isolated_session.add_all(
        [
            Portfolio(
                user_id=user.id,
                ticker="TCS",
                company_name="Tata Consultancy Services",
                shares=Decimal("2.0000"),
                buy_price=Decimal("3500.2500"),
                group_name="holdings",
            ),
            PriceTarget(user_id=user.id, ticker="TCS", target_price=Decimal("4200.0000"), direction="above"),
            TradeJournal(
                user_id=user.id,
                ticker="TCS",
                action="BUY",
                price_at_time=Decimal("3500.2500"),
                reason_text="Cascade coverage",
            ),
            AnalysisHistory(
                user_id=user.id,
                ticker="TCS",
                analysis_date="2026-06-16",
                signal="BULLISH",
                confidence_pct=70,
                full_json="{}",
            ),
        ]
    )
    isolated_session.commit()

    isolated_session.delete(user)
    isolated_session.commit()

    assert isolated_session.query(Portfolio).count() == 0
    assert isolated_session.query(PriceTarget).count() == 0
    assert isolated_session.query(TradeJournal).count() == 0
    assert isolated_session.query(AnalysisHistory).count() == 0


def test_portfolio_unique_holding_and_positive_checks(isolated_session):
    user = _user(isolated_session, "unique_user")
    holding = Portfolio(
        user_id=user.id,
        ticker="INFY",
        company_name="Infosys Ltd",
        shares=Decimal("1.0000"),
        buy_price=Decimal("1500.0000"),
        group_name="holdings",
    )
    isolated_session.add(holding)
    isolated_session.commit()

    isolated_session.add(
        Portfolio(
            user_id=user.id,
            ticker="INFY",
            company_name="Infosys Ltd",
            shares=Decimal("1.0000"),
            buy_price=Decimal("1500.0000"),
            group_name="holdings",
        )
    )
    with pytest.raises(IntegrityError):
        isolated_session.commit()
    isolated_session.rollback()

    isolated_session.add(
        Portfolio(
            user_id=user.id,
            ticker="ZERO",
            company_name="Zero Shares",
            shares=Decimal("0.0000"),
            buy_price=Decimal("1.0000"),
            group_name="holdings",
        )
    )
    with pytest.raises(IntegrityError):
        isolated_session.commit()


def test_watchlist_zero_sentinel_matches_model_documentation(isolated_session):
    user = _user(isolated_session, "watchlist_sentinel")
    isolated_session.add(
        Portfolio(
            user_id=user.id,
            ticker="RELIANCE",
            company_name="Reliance Industries Ltd",
            shares=Decimal("0.0000"),
            buy_price=Decimal("0.0000"),
            group_name="watchlist",
        )
    )
    isolated_session.commit()


def test_foreign_keys_reject_orphan_user_owned_rows(isolated_session):
    isolated_session.add(
        PriceTarget(
            user_id=999_999,
            ticker="TCS",
            target_price=Decimal("4000.0000"),
            direction="above",
        )
    )

    with pytest.raises(IntegrityError):
        isolated_session.commit()


def test_decimal_money_columns_keep_four_decimal_places(isolated_session):
    user = _user(isolated_session, "decimal_user")
    isolated_session.add(
        Portfolio(
            user_id=user.id,
            ticker="PRECISION",
            company_name="Precision Test Ltd",
            shares=Decimal("1.2345"),
            buy_price=Decimal("9876.5432"),
            group_name="holdings",
        )
    )
    isolated_session.commit()

    row = isolated_session.query(Portfolio).filter_by(ticker="PRECISION").one()
    assert row.shares == Decimal("1.2345")
    assert row.buy_price == Decimal("9876.5432")


def test_unique_snapshot_constraints_for_ledgers(isolated_session):
    user = _user(isolated_session, "ledger_user")
    isolated_session.add_all(
        [
            NetWorthLedger(user_id=user.id, snapshot_date="2026-06-16", total_value_inr=Decimal("100.0000")),
            NetWorthLedger(user_id=user.id, snapshot_date="2026-06-16", total_value_inr=Decimal("101.0000")),
        ]
    )

    with pytest.raises(IntegrityError):
        isolated_session.commit()
    isolated_session.rollback()

    isolated_session.add_all(
        [
            PortfolioValuationHistory(
                user_id=user.id,
                snapshot_date="2026-06-16",
                total_value=Decimal("100.0000"),
                total_invested=Decimal("90.0000"),
                total_pnl=Decimal("10.0000"),
                pnl_percent=Decimal("11.1111"),
            ),
            PortfolioValuationHistory(
                user_id=user.id,
                snapshot_date="2026-06-16",
                total_value=Decimal("101.0000"),
                total_invested=Decimal("90.0000"),
                total_pnl=Decimal("11.0000"),
                pnl_percent=Decimal("12.2222"),
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        isolated_session.commit()


def test_portfolio_valuation_history_rejects_orphan_user_id(isolated_session):
    isolated_session.add(
        PortfolioValuationHistory(
            user_id=999_999,
            snapshot_date="2026-06-16",
            total_value=Decimal("100.0000"),
            total_invested=Decimal("90.0000"),
            total_pnl=Decimal("10.0000"),
            pnl_percent=Decimal("11.1111"),
        )
    )

    with pytest.raises(IntegrityError):
        isolated_session.commit()


def test_model_source_has_no_duplicate_column_assignments():
    source = Path(__file__).resolve().parents[1] / "models" / "db_models.py"
    text = source.read_text()
    class_body = text.split("class AnalysisHistory", 1)[1].split("class SignalEvent", 1)[0]
    assigned_names = re.findall(r"^\s{4}([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Column\(", class_body, re.MULTILINE)
    duplicates = {name for name in assigned_names if assigned_names.count(name) > 1}

    assert duplicates == set()
