"""
test_03_relationships.py
========================
Tests all SQLAlchemy ORM relationships defined in db_models.py:
- Back-populates are bidirectional
- Cascade delete-orphan works (deleting User removes children)
- Foreign key enforcement prevents orphaned child rows
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import (
    TestRunner, make_test_engine, make_session,
    User, Portfolio, AnalysisHistory, TradeJournal, PriceTarget,
    DeviceToken, EarningsAlert, AnalysisJob, NetWorthLedger,
    PortfolioValuationHistory,
)
from sqlalchemy.exc import IntegrityError


def run():
    runner = TestRunner("03_relationships")
    runner.setup()
    session = runner.session

    # ---- Create a user for relationship testing
    user = User(
        username="rel_test_user",
        password_hash="x" * 60,
        display_name="Relationship Test User"
    )
    session.add(user)
    session.commit()
    uid = user.id

    # ---- Portfolio back-populate
    p = Portfolio(
        user_id=uid, ticker="RELTST", company_name="Rel Test Co",
        shares=10, buy_price=200.0, group_name="holdings"
    )
    session.add(p)
    session.commit()
    session.refresh(user)
    if user.portfolio and len(user.portfolio) > 0:
        runner.ok("portfolio_back_populate", f"{len(user.portfolio)} portfolio rows accessible via user.portfolio")
    else:
        runner.fail(
            "portfolio_back_populate",
            "user.portfolio relationship is empty after adding Portfolio row. "
            "back_populates='user' may be missing or incorrect in Portfolio model."
        )

    # ---- TradeJournal back-populate
    tj = TradeJournal(
        user_id=uid, ticker="RELTST", action="BUY",
        price_at_time=200.0, reason_text="Test buy"
    )
    session.add(tj)
    session.commit()
    session.refresh(user)
    if user.trade_journal:
        runner.ok("trade_journal_back_populate")
    else:
        runner.fail("trade_journal_back_populate", "user.trade_journal not accessible via relationship")

    # ---- AnalysisHistory back-populate
    ah = AnalysisHistory(
        user_id=uid, ticker="RELTST", analysis_date="2026-06-01",
        signal="BULLISH", full_json="{}", scan_type="standard"
    )
    session.add(ah)
    session.commit()
    session.refresh(user)
    if user.analysis_history:
        runner.ok("analysis_history_back_populate")
    else:
        runner.fail("analysis_history_back_populate", "user.analysis_history relationship empty after insert")

    # ---- DeviceToken back-populate
    dt = DeviceToken(user_id=uid, device_token="fake_apns_token_abc123", platform="ios")
    session.add(dt)
    session.commit()
    session.refresh(user)
    if user.device_tokens:
        runner.ok("device_tokens_back_populate")
    else:
        runner.fail("device_tokens_back_populate", "user.device_tokens relationship empty after insert")

    # ---- Cascade delete: deleting user removes all child rows
    user_to_delete = User(
        username="cascade_delete_test",
        password_hash="y" * 60,
        display_name="Cascade Delete User"
    )
    session.add(user_to_delete)
    session.commit()
    cuid = user_to_delete.id

    session.add(Portfolio(
        user_id=cuid, ticker="CASCTEST", company_name="Casc Co",
        shares=5, buy_price=100.0, group_name="holdings"
    ))
    session.add(TradeJournal(
        user_id=cuid, ticker="CASCTEST", action="BUY",
        price_at_time=100.0, reason_text="cascade test"
    ))
    session.commit()

    portfolio_count_before = session.query(Portfolio).filter_by(user_id=cuid).count()
    tj_count_before = session.query(TradeJournal).filter_by(user_id=cuid).count()

    session.delete(user_to_delete)
    session.commit()

    portfolio_after = session.query(Portfolio).filter_by(user_id=cuid).count()
    tj_after = session.query(TradeJournal).filter_by(user_id=cuid).count()

    if portfolio_after == 0:
        runner.ok(
            "cascade_delete_portfolio",
            f"Deleted user {cuid}: {portfolio_count_before} portfolio rows orphan-deleted"
        )
    else:
        runner.fail(
            "cascade_delete_portfolio",
            f"Cascade delete FAILED: {portfolio_after} Portfolio rows remain after User deletion. "
            f"These orphaned rows will appear on the next user who gets this user_id (ID reuse)."
        )

    if tj_after == 0:
        runner.ok(
            "cascade_delete_trade_journal",
            f"Trade journal rows correctly cascade-deleted"
        )
    else:
        runner.fail(
            "cascade_delete_trade_journal",
            f"Cascade delete FAILED: {tj_after} TradeJournal rows orphaned after User deletion."
        )

    # ---- FK enforcement: orphan insert should fail
    try:
        session.add(Portfolio(
            user_id=999999, ticker="ORPHAN", company_name="Ghost Co",
            shares=5, buy_price=100.0, group_name="holdings"
        ))
        session.commit()
        runner.fail(
            "fk_enforcement_portfolio",
            "FK NOT enforced: Portfolio row inserted with non-existent user_id=999999. "
            "This means PRAGMA foreign_keys=ON is not active. Orphaned portfolio rows will cause "
            "404s when the portfolio endpoint tries to join on the missing user."
        )
    except IntegrityError as e:
        session.rollback()
        runner.ok("fk_enforcement_portfolio", "FK enforced: orphaned Portfolio rejected")
    except Exception as e:
        session.rollback()
        runner.fail("fk_enforcement_portfolio", f"Unexpected error: {e}", e)

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
