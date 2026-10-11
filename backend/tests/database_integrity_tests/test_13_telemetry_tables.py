"""
test_13_telemetry_tables.py
============================
Tests the telemetry/error-log tables and their helper functions:
- MarketErrorLog + log_market_error()
- EarningsErrorLog + log_earnings_error()
- NotificationErrorLog + log_notification_error()
- IdeasErrorLog + log_ideas_error()

These functions are designed to be non-fatal (swallow their own errors).
Tests verify:
1. Each log_*() helper successfully inserts a row into its table
2. The error text is truncated at 2000 chars (guard against runaway text)
3. Swallowing works — an exception inside the helper does not propagate
4. The inserted rows are queryable
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from _base import TestRunner, make_test_engine, Base, make_session
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from models.db_models import (
    MarketErrorLog, EarningsErrorLog, NotificationErrorLog, IdeasErrorLog,
)


def run():
    runner = TestRunner("13_telemetry_tables")
    runner.setup()
    engine = runner.engine

    # We need to patch database.get_session() to use our test engine
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextmanager
    def test_get_session():
        s = SessionFactory()
        try:
            yield s
        except Exception as _e:
            s.rollback()
            raise
        finally:
            s.close()

    # Monkey-patch the get_session used by the log_* helpers
    import database as db_module
    original_get_session = db_module.get_session
    db_module.get_session = test_get_session

    try:
        # ---- Test log_market_error() inserts a row
        from database import log_market_error
        log_market_error(
            component="test_component",
            error_message="Test market error for integrity test",
            context_ticker="RELIANCE"
        )
        s = SessionFactory()
        row = s.query(MarketErrorLog).filter_by(component="test_component").first()
        s.close()
        if row:
            runner.ok("log_market_error_inserts", f"Row inserted: component={row.component}, ticker={row.context_ticker}")
        else:
            runner.fail("log_market_error_inserts", "log_market_error() did not insert a row into market_error_logs")

        # ---- Test 2000-char truncation
        long_msg = "X" * 5000
        log_market_error(component="truncation_test", error_message=long_msg)
        s2 = SessionFactory()
        row2 = s2.query(MarketErrorLog).filter_by(component="truncation_test").first()
        s2.close()
        if row2 and len(row2.error_message) <= 2000:
            runner.ok("log_market_error_truncation", f"Error message truncated to {len(row2.error_message)} chars")
        elif row2:
            runner.fail(
                "log_market_error_truncation",
                f"Error message NOT truncated: {len(row2.error_message)} chars. "
                f"Runaway AI output can cause MemoryError or max_row_size DB errors."
            )
        else:
            runner.fail("log_market_error_truncation", "Truncation test row not found")

        # ---- Test log_earnings_error()
        from database import log_earnings_error
        log_earnings_error(
            module="test_module",
            error_trace="Test earnings error traceback",
            failed_ticker="HDFC"
        )
        s3 = SessionFactory()
        row3 = s3.query(EarningsErrorLog).filter_by(module="test_module").first()
        s3.close()
        if row3:
            runner.ok("log_earnings_error_inserts", f"Row inserted: module={row3.module}, ticker={row3.failed_ticker}")
        else:
            runner.fail("log_earnings_error_inserts", "log_earnings_error() did not insert a row")

        # ---- Test log_notification_error()
        from database import log_notification_error
        log_notification_error(
            failure_point="test_dispatch",
            error_trace="Test notification error",
            target_device="device_token_abc"
        )
        s4 = SessionFactory()
        row4 = s4.query(NotificationErrorLog).filter_by(failure_point="test_dispatch").first()
        s4.close()
        if row4:
            runner.ok("log_notification_error_inserts", f"Row inserted: failure_point={row4.failure_point}")
        else:
            runner.fail("log_notification_error_inserts", "log_notification_error() did not insert a row")

        # ---- Test log_ideas_error()
        from database import log_ideas_error
        log_ideas_error(
            module="ideas_test_module",
            error_trace="Test ideas error traceback",
            context_ticker="INFY"
        )
        s5 = SessionFactory()
        row5 = s5.query(IdeasErrorLog).filter_by(module="ideas_test_module").first()
        s5.close()
        if row5:
            runner.ok("log_ideas_error_inserts", f"Row inserted: module={row5.module}")
        else:
            runner.fail("log_ideas_error_inserts", "log_ideas_error() did not insert a row")

        # ---- Test that log helpers swallow their own errors (non-fatal)
        # Temporarily break the test engine by destroying the table
        engine.execute = None  # This makes the engine non-functional
        try:
            # This should NOT raise even though the DB is broken
            # (the helper wraps everything in try/except: pass)
            # Re-patch with a broken get_session
            def broken_get_session():
                raise RuntimeError("Simulated DB outage")
            db_module.get_session = broken_get_session

            log_market_error(component="outage_test", error_message="Should not raise")
            runner.ok("log_market_error_swallows_own_errors",
                      "log_market_error() correctly swallowed its own exception during DB outage")
        except Exception as e:
            runner.fail(
                "log_market_error_swallows_own_errors",
                f"log_market_error() propagated an exception during DB outage: {e}. "
                f"Telemetry must NEVER cause cascading failures. "
                f"Add 'except Exception: pass' inside log_market_error().",
                e
            )

    finally:
        # Restore original get_session
        db_module.get_session = original_get_session

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
