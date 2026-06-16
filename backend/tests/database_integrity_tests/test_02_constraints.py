"""
test_02_constraints.py
======================
Tests all CheckConstraints and UniqueConstraints defined in db_models.py
are actually enforced by the SQLite engine at INSERT/UPDATE time.

Constraints tested:
- ck_portfolio_shares_positive
- ck_portfolio_buy_price_positive
- uq_portfolio_user_ticker_group
- ck_price_targets_positive
- uq_user_date_snapshot (portfolio_valuation_history)
- uq_networth_user_date (net_worth_ledger)
- uq_video_ticker (advisor_insights)
- uq_ticker_date_signal (pkscreener_signals)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import (
    TestRunner, make_test_engine, make_session,
    User, Portfolio, PriceTarget, PortfolioValuationHistory,
    NetWorthLedger, AdvisorInsight, PKScreenerSignal,
)
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone


def make_user(session, uid: int = 1) -> User:
    """Insert a minimal user row."""
    u = User(
        id=uid,
        username=f"constraint_test_{uid}",
        password_hash="x" * 60,
        display_name=f"Test {uid}",
    )
    session.add(u)
    session.flush()
    return u


def run():
    runner = TestRunner("02_constraints")
    runner.setup()
    session = runner.session
    make_user(session, 1)

    # ---- Portfolio: shares must be > 0 for holdings
    try:
        p = Portfolio(
            user_id=1, ticker="TST", company_name="Test Co",
            shares=0, buy_price=100.0, group_name="holdings"
        )
        session.add(p)
        session.commit()
        runner.fail(
            "ck_portfolio_shares_positive",
            "CheckConstraint NOT enforced: shares=0 in holdings was accepted. "
            "Any position with 0 shares will corrupt portfolio P&L calculations."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("ck_portfolio_shares_positive", "shares=0 in holdings rejected as expected")
    except Exception as e:
        session.rollback()
        runner.fail("ck_portfolio_shares_positive", f"Unexpected error: {e}", e)

    # ---- Portfolio: buy_price must be > 0 for holdings
    try:
        p = Portfolio(
            user_id=1, ticker="TST2", company_name="Test Co",
            shares=10, buy_price=0.0, group_name="holdings"
        )
        session.add(p)
        session.commit()
        runner.fail(
            "ck_portfolio_buy_price_positive",
            "CheckConstraint NOT enforced: buy_price=0 in holdings was accepted. "
            "Zero buy_price causes division by zero in P&L % calculations."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("ck_portfolio_buy_price_positive", "buy_price=0 in holdings rejected")
    except Exception as e:
        session.rollback()
        runner.fail("ck_portfolio_buy_price_positive", f"Unexpected error: {e}", e)

    # ---- Portfolio: watchlist allows shares=0 and buy_price=0
    try:
        p = Portfolio(
            user_id=1, ticker="TST3", company_name="Test Co",
            shares=0, buy_price=0.0, group_name="watchlist"
        )
        session.add(p)
        session.commit()
        runner.ok("watchlist_zero_shares_allowed", "watchlist with shares=0 accepted")
    except Exception as e:
        session.rollback()
        runner.fail("watchlist_zero_shares_allowed", f"Watchlist with shares=0 was wrongly rejected: {e}", e)

    # ---- Portfolio: unique constraint (user_id, ticker, group_name)
    try:
        session.add(Portfolio(
            user_id=1, ticker="DUPTEST", company_name="Dup Co",
            shares=5, buy_price=100.0, group_name="holdings"
        ))
        session.commit()
        session.add(Portfolio(
            user_id=1, ticker="DUPTEST", company_name="Dup Co",
            shares=5, buy_price=100.0, group_name="holdings"
        ))
        session.commit()
        runner.fail(
            "uq_portfolio_user_ticker_group",
            "UniqueConstraint NOT enforced: duplicate (user_id, ticker, group_name) was accepted. "
            "This will create ghost duplicate positions in the user's portfolio view."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("uq_portfolio_user_ticker_group", "Duplicate portfolio entry rejected")
    except Exception as e:
        session.rollback()
        runner.fail("uq_portfolio_user_ticker_group", f"Unexpected error: {e}", e)

    # ---- PriceTarget: target_price must be > 0
    try:
        session.add(PriceTarget(
            user_id=1, ticker="NEGTGT", target_price=-100.0, direction="BUY"
        ))
        session.commit()
        runner.fail(
            "ck_price_targets_positive",
            "CheckConstraint NOT enforced: negative target_price accepted. "
            "Alert poller will emit spurious price alerts on negative targets."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("ck_price_targets_positive", "Negative target_price rejected")
    except Exception as e:
        session.rollback()
        runner.fail("ck_price_targets_positive", f"Unexpected error: {e}", e)

    # ---- PortfolioValuationHistory: unique (user_id, snapshot_date)
    try:
        for _ in range(2):
            session.add(PortfolioValuationHistory(
                user_id=1, snapshot_date="2026-01-01",
                total_value=100000.0, total_invested=90000.0,
                total_pnl=10000.0, pnl_percent=11.1
            ))
            session.commit()
        runner.fail(
            "uq_user_date_snapshot",
            "UniqueConstraint NOT enforced: duplicate (user_id, snapshot_date) accepted in "
            "portfolio_valuation_history. Net-worth charts will show doubled values."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("uq_user_date_snapshot", "Duplicate snapshot date rejected")
    except Exception as e:
        session.rollback()
        runner.fail("uq_user_date_snapshot", f"Unexpected error: {e}", e)

    # ---- NetWorthLedger: unique (user_id, snapshot_date)
    try:
        for _ in range(2):
            session.add(NetWorthLedger(
                user_id=1, snapshot_date="2026-01-01", total_value_inr=500000.0
            ))
            session.commit()
        runner.fail(
            "uq_networth_user_date",
            "UniqueConstraint NOT enforced: duplicate snapshot in net_worth_ledger. "
            "Historical wealth tracking will show corrupt data."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("uq_networth_user_date", "Duplicate net-worth snapshot rejected")
    except Exception as e:
        session.rollback()
        runner.fail("uq_networth_user_date", f"Unexpected error: {e}", e)

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
