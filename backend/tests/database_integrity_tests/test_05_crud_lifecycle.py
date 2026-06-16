"""
test_05_crud_lifecycle.py
=========================
Full CREATE / READ / UPDATE / DELETE lifecycle tests for every
major entity in the database. Verifies that:
- Objects can be inserted (CREATE)
- Objects can be queried by PK and FK (READ)
- Fields can be modified and committed (UPDATE)
- Objects can be deleted without leaving orphans (DELETE)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timezone
from _base import (
    TestRunner, User, Portfolio, AnalysisHistory, TradeJournal,
    PriceTarget, DeviceToken, AnalysisJob, EarningsAlert,
    NetWorthLedger, PortfolioValuationHistory, MarketErrorLog,
    NewsArticle, EarningsSurpriseHistory,
)


def _now():
    return datetime.now(timezone.utc)


def run():
    runner = TestRunner("05_crud_lifecycle")
    runner.setup()
    session = runner.session

    # ===== USER =====
    user = User(username="crud_user", password_hash="x" * 60, display_name="CRUD User")
    session.add(user)
    session.commit()
    uid = user.id
    assert uid is not None

    fetched = session.query(User).filter_by(username="crud_user").first()
    if fetched and fetched.id == uid:
        runner.ok("user_create_read")
    else:
        runner.fail("user_create_read", f"Could not read back user uid={uid}")

    fetched.display_name = "CRUD User Updated"
    session.commit()
    re_fetched = session.query(User).get(uid)
    if re_fetched.display_name == "CRUD User Updated":
        runner.ok("user_update")
    else:
        runner.fail("user_update", "display_name update did not persist")

    # ===== PORTFOLIO =====
    p = Portfolio(
        user_id=uid, ticker="CRUDE", company_name="Crude Test",
        shares=10, buy_price=500.0, group_name="holdings"
    )
    session.add(p)
    session.commit()
    pid = p.id
    p_fetched = session.query(Portfolio).get(pid)
    if p_fetched and p_fetched.ticker == "CRUDE":
        runner.ok("portfolio_create_read")
    else:
        runner.fail("portfolio_create_read", "Portfolio row not readable after insert")

    p_fetched.shares = 20
    session.commit()
    p_re = session.query(Portfolio).get(pid)
    if p_re.shares == 20:
        runner.ok("portfolio_update_shares")
    else:
        runner.fail("portfolio_update_shares", "Portfolio shares update did not persist")

    # ===== ANALYSIS HISTORY =====
    ah = AnalysisHistory(
        user_id=uid, ticker="CRUD", analysis_date="2026-06-17",
        signal="BULLISH", confidence_pct=75,
        full_json='{"signal":"BULLISH","confidence_pct":75}',
        scan_type="standard"
    )
    session.add(ah)
    session.commit()
    ah_id = ah.id
    ah_fetched = session.query(AnalysisHistory).get(ah_id)
    if ah_fetched and ah_fetched.signal == "BULLISH":
        runner.ok("analysis_history_create_read")
    else:
        runner.fail("analysis_history_create_read", "AnalysisHistory not readable after insert")

    # Update signal (epistemic feedback loop update)
    ah_fetched.was_correct = True
    ah_fetched.outcome_delta_pct = 5.3
    ah_fetched.outcome_checked_at = _now()
    try:
        session.commit()
        runner.ok("analysis_history_update_ml_fields", "ML/feedback fields updated successfully")
    except Exception as e:
        session.rollback()
        runner.fail(
            "analysis_history_update_ml_fields",
            f"Updating ML fields failed: {e}. "
            f"This confirms the column drift — these fields exist in Python but not the DB.",
            e
        )

    # ===== TRADE JOURNAL =====
    tj = TradeJournal(
        user_id=uid, ticker="CRUD", action="BUY",
        price_at_time=200.0, reason_text="Test entry"
    )
    session.add(tj)
    session.commit()
    tj_id = tj.id
    tj_fetched = session.query(TradeJournal).get(tj_id)
    if tj_fetched:
        runner.ok("trade_journal_create_read")
    else:
        runner.fail("trade_journal_create_read", "TradeJournal row not readable after insert")

    # Update late-added fields
    tj_fetched.mood = "Confident"
    tj_fetched.company_name = "Crude Test Co"
    try:
        session.commit()
        runner.ok("trade_journal_update_mood_company", "mood and company_name updated successfully")
    except Exception as e:
        session.rollback()
        runner.fail(
            "trade_journal_update_mood_company",
            f"Updating mood/company_name failed: {e}. "
            f"These columns were added after the initial migration. "
            f"Run the Alembic migration to add them to the live DB.",
            e
        )

    # ===== ANALYSIS JOB =====
    job = AnalysisJob(
        job_id="TESTJOB01", user_id=uid, ticker="CRUD",
        exchange="NSE", scan_type="standard", status="QUEUED",
        progress_pct=0, checkpoints="[]"
    )
    session.add(job)
    session.commit()
    job_fetched = session.query(AnalysisJob).get("TESTJOB01")
    if job_fetched and job_fetched.status == "QUEUED":
        runner.ok("analysis_job_create_read")
    else:
        runner.fail("analysis_job_create_read", "AnalysisJob not readable after insert")

    job_fetched.status = "RUNNING"
    job_fetched.progress_pct = 50
    session.commit()
    job_re = session.query(AnalysisJob).get("TESTJOB01")
    if job_re.status == "RUNNING" and job_re.progress_pct == 50:
        runner.ok("analysis_job_update_status")
    else:
        runner.fail("analysis_job_update_status", "AnalysisJob status update did not persist")

    # ===== PRICE TARGET =====
    pt = PriceTarget(user_id=uid, ticker="CRUD", target_price=300.0, direction="BUY")
    session.add(pt)
    session.commit()
    pt_id = pt.id
    pt_fetched = session.query(PriceTarget).get(pt_id)
    if pt_fetched and pt_fetched.target_price == 300.0:
        runner.ok("price_target_create_read")
    else:
        runner.fail("price_target_create_read", "PriceTarget not readable after insert")

    pt_fetched.triggered = True
    session.commit()
    pt_re = session.query(PriceTarget).get(pt_id)
    if pt_re.triggered:
        runner.ok("price_target_update_triggered")
    else:
        runner.fail("price_target_update_triggered", "PriceTarget triggered update did not persist")

    # ===== NET WORTH LEDGER =====
    nwl = NetWorthLedger(
        user_id=uid, snapshot_date="2026-06-17", total_value_inr=1000000.0,
        daily_delta_inr=5000.0, daily_delta_pct=0.5
    )
    session.add(nwl)
    session.commit()
    nwl_id = nwl.id
    nwl_fetched = session.query(NetWorthLedger).get(nwl_id)
    if nwl_fetched and nwl_fetched.total_value_inr == 1000000.0:
        runner.ok("net_worth_ledger_create_read")
    else:
        runner.fail("net_worth_ledger_create_read", "NetWorthLedger not readable after insert")

    # ===== DELETE lifecycle =====
    session.delete(user)
    session.commit()

    deleted_user = session.query(User).get(uid)
    if deleted_user is None:
        runner.ok("user_delete")
    else:
        runner.fail("user_delete", "User row still exists after DELETE")

    orphaned_portfolio = session.query(Portfolio).filter_by(user_id=uid).count()
    if orphaned_portfolio == 0:
        runner.ok("cascade_delete_confirmed")
    else:
        runner.fail(
            "cascade_delete_confirmed",
            f"{orphaned_portfolio} Portfolio rows still exist after User delete. "
            "Cascade relationship not working correctly."
        )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
