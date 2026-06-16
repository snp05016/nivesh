"""
test_01_schema_columns.py
=========================
Verifies that every ORM model column that exists in db_models.py
is actually present in the SQLite database after create_all().

This is the ground truth check - if a column exists in Python but
not in the database, any INSERT or SELECT referencing it will crash
at runtime with OperationalError: no such column.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _base import TestRunner, ALL_MODELS, make_test_engine, sa_inspect

EXPECTED_COLUMNS = {
    "users": ["id", "username", "password_hash", "display_name", "created_at"],
    "portfolio": [
        "id", "user_id", "ticker", "company_name", "shares", "buy_price",
        "target_price", "purchase_date", "group_name", "notes", "created_at"
    ],
    "analysis_history": [
        "id", "user_id", "ticker", "analysis_date", "signal", "confidence_pct",
        "target_short", "target_medium", "target_long", "promoter_pledged_pct",
        "promoter_pledged_trend", "raw_output", "full_json", "scan_type",
        "outcome_delta_pct", "was_correct", "outcome_checked_at",
        "market_regime", "calibrated_confidence", "confidence_math_breakdown",
        "conformal_target_upper_3m", "conformal_target_lower_3m",
        "quantitative_drivers", "tail_risk_flags", "created_at"
    ],
    "trade_journal": [
        "id", "user_id", "ticker", "action", "price_at_time", "reason_text",
        "outcome_text", "company_name", "mood", "updated_at", "created_at"
    ],
    "analysis_jobs": [
        "job_id", "user_id", "ticker", "exchange", "scan_type", "status",
        "stage", "progress_pct", "checkpoints", "pid", "heartbeat_at",
        "tokens_used", "error", "result_json", "created_at", "started_at", "finished_at"
    ],
    "net_worth_ledger": [
        "id", "user_id", "snapshot_date", "total_value_inr", "daily_delta_inr",
        "daily_delta_pct", "peak_value_inr", "top_gainer_ticker", "top_gainer_pct",
        "top_loser_ticker", "top_loser_pct", "portfolio_json", "created_at"
    ],
    "portfolio_valuation_history": [
        "id", "user_id", "snapshot_date", "total_value", "total_invested",
        "total_pnl", "pnl_percent", "nifty_close", "created_at"
    ],
}


def run():
    runner = TestRunner("01_schema_columns")
    runner.setup()

    insp = sa_inspect(runner.engine)
    actual_tables = set(insp.get_table_names())

    # ---- Test: all expected tables exist
    for model in ALL_MODELS:
        tname = model.__tablename__
        if tname in actual_tables:
            runner.ok(f"table_exists:{tname}")
        else:
            runner.fail(f"table_exists:{tname}", f"Table '{tname}' missing from DB after create_all()")

    # ---- Test: detailed column presence for critical tables
    for table_name, expected_cols in EXPECTED_COLUMNS.items():
        if table_name not in actual_tables:
            runner.fail(
                f"columns:{table_name}",
                f"Skipped — table '{table_name}' does not exist"
            )
            continue
        actual_cols = {col["name"] for col in insp.get_columns(table_name)}
        for col in expected_cols:
            if col in actual_cols:
                runner.ok(f"column:{table_name}.{col}")
            else:
                runner.fail(
                    f"column:{table_name}.{col}",
                    f"Column '{col}' declared in db_models.py but MISSING from the actual '{table_name}' table. "
                    f"Any INSERT/SELECT using this column will throw OperationalError at runtime. "
                    f"Run: alembic revision --autogenerate -m 'add {col} to {table_name}' && alembic upgrade head"
                )

    # ---- Test: check for extra columns in DB not in model (stale/orphan columns)
    for table_name, expected_cols in EXPECTED_COLUMNS.items():
        if table_name not in actual_tables:
            continue
        actual_cols = {col["name"] for col in insp.get_columns(table_name)}
        expected_set = set(expected_cols)
        orphan = actual_cols - expected_set
        if orphan:
            runner.fail(
                f"orphan_columns:{table_name}",
                f"Columns in DB but NOT in ORM model: {orphan}. "
                f"These columns consume storage but are never populated. Consider migration to remove them."
            )
        else:
            runner.ok(f"no_orphan_columns:{table_name}")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(run())
