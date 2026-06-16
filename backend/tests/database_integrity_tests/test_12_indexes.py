"""
test_12_indexes.py
==================
Verifies that all Index() definitions in db_models.py are actually
created in the database schema. Also measures query performance to
confirm indexes are being used (EXPLAIN QUERY PLAN analysis).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import TestRunner, sa_inspect, make_test_engine
from sqlalchemy import text

# All indexes declared in db_models.py
EXPECTED_INDEXES = {
    "portfolio": [
        "ix_portfolio_user_id",
        "ix_portfolio_user_ticker",
        "ix_portfolio_group",
    ],
    "analysis_history": [
        "ix_analysis_history_user_id",
        "ix_analysis_history_ticker",
        "ix_analysis_history_scan_type",
        "ix_analysis_history_created_at",
        "ix_analysis_history_ticker_user",
    ],
    "analysis_jobs": [
        "ix_analysis_jobs_user_id",
        "ix_analysis_jobs_ticker",
    ],
    "price_targets": [
        "ix_price_targets_user_id",
    ],
    "trade_journal": [
        "ix_trade_journal_user_id",
    ],
    "device_tokens": [
        "ix_device_tokens_user_id",
    ],
    "market_anomalies": [
        "ix_market_anomalies_anomaly_type",
        "ix_market_anomalies_ticker",
        "ix_market_anomalies_timestamp",
    ],
    "earnings_surprise_history": [
        "ix_earnings_surprise_history_ticker",
    ],
    "macro_events": [
        "ix_macro_events_date",
    ],
    "advisor_insights": [
        "ix_advisor_ticker_published",
    ],
}


def run():
    runner = TestRunner("12_indexes")
    runner.setup()
    engine = runner.engine
    insp = sa_inspect(engine)

    for table_name, expected_idx_names in EXPECTED_INDEXES.items():
        if table_name not in insp.get_table_names():
            runner.fail(f"table_exists:{table_name}", f"Table '{table_name}' missing — cannot check indexes")
            continue

        actual_indexes = {idx["name"] for idx in insp.get_indexes(table_name)}

        for idx_name in expected_idx_names:
            if idx_name in actual_indexes:
                runner.ok(f"index:{table_name}/{idx_name}")
            else:
                runner.fail(
                    f"index:{table_name}/{idx_name}",
                    f"Index '{idx_name}' declared in db_models.py but MISSING from table '{table_name}'. "
                    f"Queries filtering by indexed columns will perform full table scans instead. "
                    f"Under load (1000+ users), this will cause query times > 5s on analysis_history. "
                    f"Fix: alembic revision --autogenerate to recreate missing index."
                )

    # ---- Performance: EXPLAIN QUERY PLAN on analysis_history ticker lookup
    from sqlalchemy.orm import sessionmaker
    session = sessionmaker(bind=engine)()
    try:
        result = session.execute(
            text("EXPLAIN QUERY PLAN SELECT * FROM analysis_history WHERE ticker = 'RELIANCE'")
        ).fetchall()
        plan_text = str(result)
        if "USING INDEX" in plan_text or "ix_analysis_history_ticker" in plan_text:
            runner.ok("analysis_history_ticker_uses_index", f"Query plan uses index: {plan_text[:200]}")
        else:
            runner.fail(
                "analysis_history_ticker_uses_index",
                f"Query on analysis_history.ticker is NOT using the index (full table scan). "
                f"Plan: {plan_text[:500]}. "
                f"This means the index either doesn't exist or SQLite chose not to use it."
            )
    except Exception as e:
        runner.fail("analysis_history_ticker_uses_index", f"EXPLAIN QUERY PLAN failed: {e}", e)
    finally:
        session.close()

    # ---- Performance: EXPLAIN QUERY PLAN on portfolio user_id lookup
    session2 = sessionmaker(bind=engine)()
    try:
        result2 = session2.execute(
            text("EXPLAIN QUERY PLAN SELECT * FROM portfolio WHERE user_id = 1")
        ).fetchall()
        plan_text2 = str(result2)
        if "USING INDEX" in plan_text2 or "ix_portfolio_user_id" in plan_text2 or "SEARCH portfolio" in plan_text2:
            runner.ok("portfolio_user_id_uses_index", f"Portfolio user_id query uses index")
        else:
            runner.fail(
                "portfolio_user_id_uses_index",
                f"Portfolio user_id query is a full table scan. "
                f"Plan: {plan_text2[:300]}"
            )
    except Exception as e:
        runner.fail("portfolio_user_id_uses_index", f"EXPLAIN QUERY PLAN failed: {e}", e)
    finally:
        session2.close()

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
