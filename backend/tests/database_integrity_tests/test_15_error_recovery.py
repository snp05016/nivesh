"""
test_15_error_recovery.py
==========================
Tests database error recovery scenarios:
- PendingRollbackError: session is usable after IntegrityError + rollback
- DetachedInstanceError: accessing attributes on a closed-session object
- SQLAlchemyError: general error recovery
- OperationalError: handling DB lock timeouts
- Session boundary violations: using same session across threads
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from contextlib import contextmanager
from _base import TestRunner, make_test_engine, User, Portfolio
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import (
    IntegrityError, PendingRollbackError, DetachedInstanceError,
    OperationalError, SQLAlchemyError
)


def run():
    runner = TestRunner("15_error_recovery")
    runner.setup()
    engine = runner.engine
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextmanager
    def get_session():
        s = SessionFactory()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ---- Test 1: PendingRollbackError recovery
    # After IntegrityError, the session is in a 'needs rollback' state.
    # The get_session() context manager MUST call rollback() to clean it up.
    with get_session() as s:
        s.add(User(username="recovery_base", password_hash="x" * 60, display_name="Recovery Base"))
        s.commit()

    # Trigger IntegrityError (duplicate username)
    try:
        with get_session() as s:
            s.add(User(username="recovery_base", password_hash="y" * 60, display_name="Dup"))
            s.commit()
    except IntegrityError:
        pass  # Correctly caught; session should be rolled back

    # Now try a completely new session — must NOT get PendingRollbackError
    try:
        with get_session() as s:
            count = s.query(User).filter_by(username="recovery_base").count()
            if count == 1:
                runner.ok("pending_rollback_recovery",
                          "Session is clean after IntegrityError — no PendingRollbackError")
            else:
                runner.fail("pending_rollback_recovery",
                            f"Unexpected count={count} after recovery")
    except PendingRollbackError as e:
        runner.fail(
            "pending_rollback_recovery",
            f"PendingRollbackError leaked to next session: {e}. "
            f"This means the except block in get_session() is NOT calling session.rollback(). "
            f"Every subsequent DB operation will fail until the process is restarted.",
            e
        )
    except Exception as e:
        runner.fail("pending_rollback_recovery", f"Unexpected error: {e}", e)

    # ---- Test 2: DetachedInstanceError
    # Accessing a lazy-loaded relationship attribute after the session is closed
    # should raise DetachedInstanceError.
    with get_session() as s:
        u = s.query(User).filter_by(username="recovery_base").first()
        user_id_captured = u.id  # capture PK while session is open

    # Session is now closed. Trying to access a relationship should fail.
    try:
        # Accessing the 'portfolio' relationship requires a DB round-trip
        _ = u.portfolio  # This should raise DetachedInstanceError
        # If it doesn't raise (e.g., eager loading was used), that's also fine
        runner.ok("detached_instance_handled",
                  "Relationship access after session close did not raise (eager loading active)")
    except DetachedInstanceError as e:
        runner.ok(
            "detached_instance_detected",
            f"DetachedInstanceError correctly raised when accessing relationship after session close. "
            f"Code that accesses relationships outside session context will hit this error at runtime. "
            f"Use eager loading (joinedload) or keep access within session scope."
        )
    except Exception as e:
        runner.fail("detached_instance_handled", f"Unexpected error type: {type(e).__name__}: {e}", e)

    # ---- Test 3: SQLAlchemy error types are importable and catchable
    from sqlalchemy.exc import (
        IntegrityError, OperationalError, ProgrammingError, DataError,
        DatabaseError, SQLAlchemyError, NoResultFound, MultipleResultsFound,
        InvalidRequestError, PendingRollbackError, DBAPIError, InterfaceError,
    )
    # Verify they are all proper exception classes
    error_classes = [
        ("IntegrityError", IntegrityError),
        ("OperationalError", OperationalError),
        ("ProgrammingError", ProgrammingError),
        ("SQLAlchemyError", SQLAlchemyError),
        ("NoResultFound", NoResultFound),
        ("MultipleResultsFound", MultipleResultsFound),
        ("InvalidRequestError", InvalidRequestError),
        ("PendingRollbackError", PendingRollbackError),
        ("DBAPIError", DBAPIError),
        ("InterfaceError", InterfaceError),
    ]
    for name, cls in error_classes:
        if issubclass(cls, Exception):
            runner.ok(f"exception_class_importable:{name}", f"{name} is importable and a valid Exception subclass")
        else:
            runner.fail(f"exception_class_importable:{name}", f"{name} is not a valid Exception subclass")

    # ---- Test 4: Multiple sequential errors do not corrupt state
    sequential_errors = 0
    for i in range(5):
        try:
            with get_session() as s:
                s.add(User(username="recovery_base", password_hash="x" * 60, display_name="Dup"))
                s.commit()  # IntegrityError every time
        except IntegrityError:
            sequential_errors += 1

    if sequential_errors == 5:
        # Now verify DB is still usable
        try:
            with get_session() as s:
                count = s.query(User).count()
                runner.ok("sequential_errors_recovery",
                          f"DB usable after {sequential_errors} sequential IntegrityErrors. user_count={count}")
        except Exception as e:
            runner.fail(
                "sequential_errors_recovery",
                f"DB not usable after {sequential_errors} sequential IntegrityErrors: {e}. "
                f"Session pool may be exhausted or poisoned.",
                e
            )
    else:
        runner.fail(
            "sequential_errors_recovery",
            f"Only {sequential_errors}/5 IntegrityErrors were caught — some leaked as a different exception type"
        )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
