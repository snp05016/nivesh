"""
test_09_foreign_keys.py
=======================
Tests that PRAGMA foreign_keys=ON is active and that all
ForeignKey constraints in db_models.py are enforced by SQLite.

Covers:
- Portfolio.user_id → users.id
- AnalysisHistory.user_id → users.id
- TradeJournal.user_id → users.id
- PriceTarget.user_id → users.id
- DeviceToken.user_id → users.id
- EarningsAlert.user_id → users.id
- AnalysisJob.user_id → users.id
- NetWorthLedger.user_id → users.id
- PortfolioValuationHistory.user_id → users.id
- TextAdvisoryInsight.advisor_id → advisor_biographies.id
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import (
    TestRunner, make_test_engine, make_session,
    User, Portfolio, AnalysisHistory, TradeJournal, PriceTarget,
    DeviceToken, EarningsAlert, AnalysisJob, NetWorthLedger,
    PortfolioValuationHistory, AdvisorBiography, TextAdvisoryInsight,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

GHOST_USER_ID = 999_999_999  # Non-existent user


def _check_fk_active(session) -> bool:
    """Check if PRAGMA foreign_keys=ON is actually active in this connection."""
    result = session.execute(text("PRAGMA foreign_keys")).scalar()
    return result == 1


def _try_orphan_insert(session, model_class, kwargs: dict, test_name: str, runner: TestRunner, description: str):
    try:
        obj = model_class(**kwargs)
        session.add(obj)
        session.commit()
        runner.fail(
            test_name,
            f"FK NOT enforced: {description} was accepted with non-existent FK. "
            f"PRAGMA foreign_keys may be OFF. Orphaned rows will accumulate and cause "
            f"join failures, incorrect data, and storage bloat."
        )
    except IntegrityError:
        session.rollback()
        runner.ok(test_name, f"Orphaned {model_class.__tablename__} correctly rejected")
    except Exception as e:
        session.rollback()
        runner.fail(test_name, f"Unexpected error: {e}", e)


def run():
    runner = TestRunner("09_foreign_keys")
    runner.setup()
    session = runner.session

    # ---- Check PRAGMA foreign_keys is ON
    is_fk_on = _check_fk_active(session)
    if is_fk_on:
        runner.ok("pragma_foreign_keys_on", "PRAGMA foreign_keys=ON is active")
    else:
        runner.fail(
            "pragma_foreign_keys_on",
            "PRAGMA foreign_keys=OFF — SQLite is not enforcing foreign key constraints! "
            "All FK tests below will report false positives. "
            "Fix: ensure the 'connect' event listener in database.py executes: "
            "PRAGMA foreign_keys=ON"
        )

    # ---- Portfolio: ghost user
    _try_orphan_insert(
        session, Portfolio,
        {"user_id": GHOST_USER_ID, "ticker": "GHOST", "company_name": "Ghost Co",
         "shares": 10.0, "buy_price": 100.0, "group_name": "holdings"},
        "fk_portfolio_user_id",
        runner,
        "Portfolio with non-existent user_id"
    )

    # ---- AnalysisHistory: ghost user
    _try_orphan_insert(
        session, AnalysisHistory,
        {"user_id": GHOST_USER_ID, "ticker": "GHOST", "analysis_date": "2026-06-17",
         "signal": "HOLD", "full_json": "{}", "scan_type": "standard"},
        "fk_analysis_history_user_id",
        runner,
        "AnalysisHistory with non-existent user_id"
    )

    # ---- TradeJournal: ghost user
    _try_orphan_insert(
        session, TradeJournal,
        {"user_id": GHOST_USER_ID, "ticker": "GHOST", "action": "BUY",
         "price_at_time": 100.0, "reason_text": "ghost entry"},
        "fk_trade_journal_user_id",
        runner,
        "TradeJournal with non-existent user_id"
    )

    # ---- PriceTarget: ghost user
    _try_orphan_insert(
        session, PriceTarget,
        {"user_id": GHOST_USER_ID, "ticker": "GHOST", "target_price": 100.0, "direction": "BUY"},
        "fk_price_target_user_id",
        runner,
        "PriceTarget with non-existent user_id"
    )

    # ---- DeviceToken: ghost user
    _try_orphan_insert(
        session, DeviceToken,
        {"user_id": GHOST_USER_ID, "device_token": "ghost_token_abc", "platform": "ios"},
        "fk_device_token_user_id",
        runner,
        "DeviceToken with non-existent user_id"
    )

    # ---- EarningsAlert: ghost user
    _try_orphan_insert(
        session, EarningsAlert,
        {"user_id": GHOST_USER_ID, "ticker": "GHOST", "earnings_date": "2026-07-01"},
        "fk_earnings_alert_user_id",
        runner,
        "EarningsAlert with non-existent user_id"
    )

    # ---- AnalysisJob: ghost user
    _try_orphan_insert(
        session, AnalysisJob,
        {"job_id": "GHOSTJOB1", "user_id": GHOST_USER_ID, "ticker": "GHOST",
         "exchange": "NSE", "scan_type": "standard", "status": "QUEUED",
         "progress_pct": 0, "checkpoints": "[]"},
        "fk_analysis_job_user_id",
        runner,
        "AnalysisJob with non-existent user_id"
    )

    # ---- NetWorthLedger: ghost user
    _try_orphan_insert(
        session, NetWorthLedger,
        {"user_id": GHOST_USER_ID, "snapshot_date": "2026-06-17", "total_value_inr": 100.0},
        "fk_net_worth_ledger_user_id",
        runner,
        "NetWorthLedger with non-existent user_id"
    )

    # ---- PortfolioValuationHistory: ghost user
    _try_orphan_insert(
        session, PortfolioValuationHistory,
        {"user_id": GHOST_USER_ID, "snapshot_date": "2026-06-17",
         "total_value": 100.0, "total_invested": 90.0, "total_pnl": 10.0, "pnl_percent": 11.1},
        "fk_portfolio_valuation_history_user_id",
        runner,
        "PortfolioValuationHistory with non-existent user_id"
    )

    # ---- TextAdvisoryInsight: ghost advisor
    _try_orphan_insert(
        session, TextAdvisoryInsight,
        {"advisor_id": GHOST_USER_ID, "content_text": "Ghost content"},
        "fk_text_advisory_insight_advisor_id",
        runner,
        "TextAdvisoryInsight with non-existent advisor_id"
    )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
