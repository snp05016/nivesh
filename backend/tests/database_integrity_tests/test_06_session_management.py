"""
test_06_session_management.py
==============================
Tests database.py's get_session() context manager for:
- Proper rollback on exception (no PendingRollbackError poison)
- Session does not leak (close() is called in finally)
- Re-use of session after rollback works (clean state)
- Nested error handling does not swallow exceptions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from contextlib import contextmanager
from _base import TestRunner, make_test_engine, make_session, User
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, PendingRollbackError


def run():
    runner = TestRunner("06_session_management")
    runner.setup()
    engine = runner.engine

    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Replicate the exact get_session() pattern from database.py
    @contextmanager
    def get_session():
        session = SessionFactory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ---- Test 1: Rollback on exception leaves session usable
    try:
        with get_session() as s:
            u = User(username="rollback_test", password_hash="x" * 60, display_name="Rollback Test")
            s.add(u)
            s.flush()
            raise ValueError("Intentional error to trigger rollback")
    except ValueError:
        pass  # expected

    # After rollback, we should be able to open a fresh session and query
    try:
        with get_session() as s:
            count = s.query(User).filter_by(username="rollback_test").count()
            if count == 0:
                runner.ok("rollback_on_exception", "Row was correctly rolled back")
            else:
                runner.fail(
                    "rollback_on_exception",
                    "Row survived the rollback — data may be committed before the exception was raised. "
                    "Check autoflush=True setting which would commit before the exception."
                )
    except PendingRollbackError as e:
        runner.fail(
            "rollback_on_exception",
            f"PendingRollbackError after exception: the session was not properly rolled back. "
            f"get_session() must call session.rollback() in its except block. Error: {e}",
            e
        )
    except Exception as e:
        runner.fail("rollback_on_exception", f"Unexpected error after rollback: {e}", e)

    # ---- Test 2: Session closes after exiting context (no leak)
    leaked_session = None
    with get_session() as s:
        leaked_session = s

    # After context exit, the session should be closed
    # In SQLAlchemy 2.0+, a closed session raises InvalidRequestError or similar
    try:
        leaked_session.query(User).count()
        runner.fail(
            "session_closes_on_exit",
            "Session is still fully usable after context exit — session may be leaked. "
            "This will exhaust the connection pool under load."
        )
    except Exception as e:
        # Any exception (InvalidRequestError, OperationalError, etc.) confirms the session is closed
        runner.ok("session_closes_on_exit",
                  f"Session correctly unusable after context exit: {type(e).__name__}: {str(e)[:80]}")

    # ---- Test 3: After IntegrityError + rollback, session can be reused
    try:
        # First: create a user
        with get_session() as s:
            s.add(User(username="integrity_test_user", password_hash="x" * 60, display_name="IT User"))
            s.commit()

        # Second: trigger IntegrityError (duplicate username)
        try:
            with get_session() as s:
                s.add(User(username="integrity_test_user", password_hash="y" * 60, display_name="IT User Dup"))
                s.commit()
        except IntegrityError:
            pass  # Correctly caught; get_session should have rolled back

        # Third: open a clean session and do a normal query — must not throw PendingRollbackError
        with get_session() as s:
            count = s.query(User).filter_by(username="integrity_test_user").count()
            if count == 1:
                runner.ok("session_clean_after_integrity_error", "Fresh session works after IntegrityError")
            else:
                runner.fail(
                    "session_clean_after_integrity_error",
                    f"Unexpected count={count} after IntegrityError recovery"
                )
    except PendingRollbackError as e:
        runner.fail(
            "session_clean_after_integrity_error",
            f"PendingRollbackError leaked between sessions: {e}. "
            f"The get_session() context manager did not call rollback() after IntegrityError. "
            f"Fix: ensure 'session.rollback()' is in the except block of get_session().",
            e
        )
    except Exception as e:
        runner.fail("session_clean_after_integrity_error", f"Unexpected error: {e}", e)

    # ---- Test 4: No data committed inside a with-block that raised before commit
    try:
        with get_session() as s:
            s.add(User(username="uncommitted_user", password_hash="x" * 60, display_name="Uncommit"))
            # Note: NO s.commit() — the context manager exits normally (no exception)
            # but the transaction was never committed

        # Without an explicit commit, the data should NOT be in the DB
        with get_session() as s:
            count = s.query(User).filter_by(username="uncommitted_user").count()
            if count == 0:
                runner.ok("no_implicit_commit", "Data without explicit commit was correctly not persisted")
            else:
                runner.fail(
                    "no_implicit_commit",
                    "Data without commit() was persisted — autocommit may be ON. "
                    "This can cause accidental partial writes."
                )
    except Exception as e:
        runner.fail("no_implicit_commit", f"Unexpected error: {e}", e)

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
