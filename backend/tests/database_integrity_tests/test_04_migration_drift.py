"""
test_04_migration_drift.py
==========================
Detects the known Alembic migration drift:
The initial migration used Base.metadata.create_all() which does NOT
apply ALTER TABLE for new columns added to existing tables after the initial schema.

This test PROVES the drift by checking whether specific late-added columns
(mood, company_name, updated_at in TradeJournal; ML fields in AnalysisHistory)
exist in the physical schema when using the real stockapp.db file on disk.

For the in-memory test engine (which runs create_all fresh), these columns WILL
exist — this is the expected healthy state. The test also checks the Alembic
version table to see whether proper migrations have been applied.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import sqlite3
from _base import TestRunner, sa_inspect, make_test_engine

# Known columns added AFTER the initial migration was established via create_all()
LATE_ADDED_TRADE_JOURNAL_COLS = ["company_name", "mood", "updated_at"]
LATE_ADDED_ANALYSIS_HISTORY_COLS = [
    "outcome_delta_pct", "was_correct", "outcome_checked_at",
    "market_regime", "calibrated_confidence", "confidence_math_breakdown",
    "conformal_target_upper_3m", "conformal_target_lower_3m",
    "quantitative_drivers", "tail_risk_flags",
]


def run():
    runner = TestRunner("04_migration_drift")

    # ---- Part A: In-memory (fresh create_all) — should have ALL columns
    runner.setup()
    insp = sa_inspect(runner.engine)

    actual_tj = {c["name"] for c in insp.get_columns("trade_journal")}
    for col in LATE_ADDED_TRADE_JOURNAL_COLS:
        if col in actual_tj:
            runner.ok(f"inmemory_trade_journal.{col}", "Column present in fresh schema")
        else:
            runner.fail(
                f"inmemory_trade_journal.{col}",
                f"Column '{col}' missing even from fresh create_all(). "
                f"This means the column is not in db_models.py — add it and run tests again."
            )

    actual_ah = {c["name"] for c in insp.get_columns("analysis_history")}
    for col in LATE_ADDED_ANALYSIS_HISTORY_COLS:
        if col in actual_ah:
            runner.ok(f"inmemory_analysis_history.{col}", "Column present in fresh schema")
        else:
            runner.fail(
                f"inmemory_analysis_history.{col}",
                f"Column '{col}' missing even from fresh create_all(). "
                f"Add it to db_models.py AnalysisHistory model."
            )

    runner.teardown()

    # ---- Part B: Live stockapp.db on disk — check actual state of the running DB
    db_path = Path(__file__).parent.parent.parent / "stockapp.db"
    if not db_path.exists():
        runner.ok("live_db_exists", f"stockapp.db not found at {db_path} — skipping live drift check (expected in CI)")
    else:
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("PRAGMA table_info(trade_journal)")
            live_tj_cols = {row[1] for row in cursor.fetchall()}
            conn.close()

            for col in LATE_ADDED_TRADE_JOURNAL_COLS:
                if col in live_tj_cols:
                    runner.ok(f"live_db_trade_journal.{col}", "Column present in live DB")
                else:
                    runner.fail(
                        f"live_db_trade_journal.{col}",
                        f"CRITICAL: Column '{col}' exists in db_models.py but is MISSING from live stockapp.db. "
                        f"API calls that try to read/write '{col}' will crash with: "
                        f"OperationalError: table trade_journal has no column named {col}. "
                        f"FIX: Run 'alembic revision --autogenerate -m \"add {col} to trade_journal\" && alembic upgrade head'"
                    )

            conn2 = sqlite3.connect(str(db_path))
            cursor2 = conn2.execute("PRAGMA table_info(analysis_history)")
            live_ah_cols = {row[1] for row in cursor2.fetchall()}
            conn2.close()

            for col in LATE_ADDED_ANALYSIS_HISTORY_COLS:
                if col in live_ah_cols:
                    runner.ok(f"live_db_analysis_history.{col}", "Column present in live DB")
                else:
                    runner.fail(
                        f"live_db_analysis_history.{col}",
                        f"CRITICAL: Column '{col}' exists in db_models.py but is MISSING from live stockapp.db. "
                        f"ML pipeline will throw OperationalError when trying to save analysis output. "
                        f"FIX: 'alembic revision --autogenerate -m \"add ML columns\" && alembic upgrade head'"
                    )

            # Check Alembic version table
            try:
                conn3 = sqlite3.connect(str(db_path))
                cursor3 = conn3.execute("SELECT version_num FROM alembic_version")
                versions = [row[0] for row in cursor3.fetchall()]
                conn3.close()
                if versions:
                    runner.ok("alembic_version_table", f"Alembic version: {versions}")
                else:
                    runner.fail(
                        "alembic_version_table",
                        "alembic_version table exists but is EMPTY. "
                        "Alembic does not know the current DB state. "
                        "Run: alembic stamp head"
                    )
            except Exception as e:
                runner.fail(
                    "alembic_version_table",
                    f"alembic_version table missing or unreadable: {e}. "
                    "This means Alembic has never been run against this database. "
                    "The schema is entirely managed by create_all() with no migration history."
                )

        except Exception as e:
            runner.fail("live_db_check", f"Could not inspect live stockapp.db: {e}", e)

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
