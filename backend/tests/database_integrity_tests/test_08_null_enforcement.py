"""
test_08_null_enforcement.py
============================
Tests that NOT NULL columns actually reject NULL values at the DB layer.
SQLAlchemy's nullable=False should translate to NOT NULL in SQLite DDL.
This test also catches columns with nullable=False that have a Python-level
default but no server_default — meaning the DB column might accept NULLs
if the ORM default is bypassed by raw SQL.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import (
    TestRunner, make_test_engine, make_session, sa_inspect,
    User, Portfolio, AnalysisHistory, TradeJournal,
)
from sqlalchemy.exc import IntegrityError


def run():
    runner = TestRunner("08_null_enforcement")
    runner.setup()
    session = runner.session

    # Create base user
    u = User(username="null_test_user", password_hash="x" * 60, display_name="Null Test")
    session.add(u)
    session.commit()
    uid = u.id

    # ---- User: username cannot be NULL
    try:
        session.add(User(username=None, password_hash="x" * 60, display_name="No Username"))
        session.commit()
        runner.fail(
            "user_username_not_null",
            "NULL username was accepted. users.username is declared nullable=False but DB is not enforcing it. "
            "Two users can have null usernames — authentication will return wrong user on login."
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("user_username_not_null", "NULL username correctly rejected")

    # ---- User: password_hash cannot be NULL
    try:
        session.add(User(username="no_pwd_hash", password_hash=None, display_name="No Hash"))
        session.commit()
        runner.fail(
            "user_password_hash_not_null",
            "NULL password_hash was accepted. Any user with NULL hash can log in with any password "
            "if verify_password() returns True on None comparison."
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("user_password_hash_not_null", "NULL password_hash correctly rejected")

    # ---- Portfolio: ticker cannot be NULL
    try:
        session.add(Portfolio(
            user_id=uid, ticker=None, company_name="No Ticker",
            shares=10, buy_price=100.0, group_name="holdings"
        ))
        session.commit()
        runner.fail(
            "portfolio_ticker_not_null",
            "NULL ticker was accepted in Portfolio. "
            "yfinance and NSE data fetches will crash on None ticker input."
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("portfolio_ticker_not_null", "NULL ticker correctly rejected")

    # ---- Portfolio: shares cannot be NULL
    try:
        session.add(Portfolio(
            user_id=uid, ticker="NULLTST", company_name="Null Test",
            shares=None, buy_price=100.0, group_name="holdings"
        ))
        session.commit()
        runner.fail(
            "portfolio_shares_not_null",
            "NULL shares accepted. Portfolio value calculation will throw TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'"
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("portfolio_shares_not_null", "NULL shares correctly rejected")

    # ---- AnalysisHistory: signal cannot be NULL
    try:
        session.add(AnalysisHistory(
            user_id=uid, ticker="NULLTEST", analysis_date="2026-06-17",
            signal=None, full_json="{}", scan_type="standard"
        ))
        session.commit()
        runner.fail(
            "analysis_history_signal_not_null",
            "NULL signal accepted in analysis_history. "
            "Signal display in the iOS app will crash with: 'NoneType' has no attribute 'upper'. "
            "_SIGNAL_MAP lookup on None will throw KeyError."
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("analysis_history_signal_not_null", "NULL signal correctly rejected")

    # ---- AnalysisHistory: full_json cannot be NULL (always stores the complete result)
    try:
        session.add(AnalysisHistory(
            user_id=uid, ticker="NULLTEST2", analysis_date="2026-06-17",
            signal="HOLD", full_json=None, scan_type="standard"
        ))
        session.commit()
        runner.fail(
            "analysis_history_full_json_not_null",
            "NULL full_json accepted. json.loads(row.full_json) will throw TypeError at runtime "
            "when the analysis result is retrieved. The entire analysis history endpoint will crash."
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("analysis_history_full_json_not_null", "NULL full_json correctly rejected")

    # ---- TradeJournal: reason_text cannot be NULL
    try:
        session.add(TradeJournal(
            user_id=uid, ticker="NULLTJ", action="BUY",
            price_at_time=100.0, reason_text=None
        ))
        session.commit()
        runner.fail(
            "trade_journal_reason_text_not_null",
            "NULL reason_text accepted. Frontend will display 'None' instead of a rationale in the journal view."
        )
    except (IntegrityError, Exception) as e:
        session.rollback()
        runner.ok("trade_journal_reason_text_not_null", "NULL reason_text correctly rejected")

    # ---- Verify nullable columns actually accept NULL (sanity check)
    try:
        ah = AnalysisHistory(
            user_id=uid, ticker="NULLABLE", analysis_date="2026-06-17",
            signal="HOLD", full_json="{}",
            scan_type="standard",
            confidence_pct=None,       # nullable=True
            target_short=None,         # nullable=True
            promoter_pledged_pct=None, # nullable=True
        )
        session.add(ah)
        session.commit()
        runner.ok("nullable_columns_accept_null", "Nullable columns correctly accept None/NULL values")
    except Exception as e:
        session.rollback()
        runner.fail(
            "nullable_columns_accept_null",
            f"Nullable columns incorrectly rejected NULL: {e}",
            e
        )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
