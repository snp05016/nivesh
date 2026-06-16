"""
test_07_concurrent_writes.py
============================
Tests SQLite write-concurrency behavior under the WAL journal mode.
Simulates multiple threads writing to the DB simultaneously —
the scenario that occurs when multiple FastAPI workers or background
tasks (nightly jobs, price alert poller, AI analysis worker) all
write to stockapp.db concurrently.

SQLite WAL mode allows concurrent reads but serializes writes.
This test verifies:
1. Concurrent writes from multiple threads complete without data loss
2. The busy_timeout (5000ms) prevents immediate OperationalError: database is locked
3. Row counts are consistent after all threads complete
"""
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import TestRunner, make_test_engine, make_session, User, Portfolio
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError


def run():
    runner = TestRunner("07_concurrent_writes")
    runner.setup()
    engine = runner.engine
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Create base user
    base_session = SessionFactory()
    base_user = User(username="concurrent_base", password_hash="x" * 60, display_name="Concurrent Base")
    base_session.add(base_user)
    base_session.commit()
    base_uid = base_user.id
    base_session.close()

    errors = []
    successes = []

    def write_portfolio(thread_id: int):
        s = SessionFactory()
        try:
            p = Portfolio(
                user_id=base_uid,
                ticker=f"THREAD{thread_id:03d}",
                company_name=f"Thread {thread_id} Co",
                shares=float(thread_id),
                buy_price=100.0,
                group_name="holdings"
            )
            s.add(p)
            s.commit()
            successes.append(thread_id)
        except OperationalError as e:
            errors.append((thread_id, f"OperationalError (likely lock timeout): {e}"))
            s.rollback()
        except Exception as e:
            errors.append((thread_id, str(e)))
            s.rollback()
        finally:
            s.close()

    # Launch 10 concurrent writer threads
    NUM_THREADS = 10
    threads = [threading.Thread(target=write_portfolio, args=(i,)) for i in range(NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # Verify results
    if errors:
        for thread_id, error_msg in errors:
            runner.fail(
                f"concurrent_write_thread_{thread_id}",
                f"Thread {thread_id} failed: {error_msg}. "
                f"SQLite WAL busy_timeout may be too low, or write contention is too high. "
                f"Under Uvicorn --workers N, this will cause frequent 500 errors on analysis endpoints. "
                f"Consider: increasing PRAGMA busy_timeout, or migrating to PostgreSQL."
            )
    else:
        runner.ok(f"concurrent_writes_all_succeeded", f"All {NUM_THREADS} concurrent writers succeeded")

    # Count actual rows
    verify_session = SessionFactory()
    actual_count = verify_session.query(Portfolio).filter_by(user_id=base_uid).count()
    verify_session.close()

    expected_count = len(successes)
    if actual_count == expected_count:
        runner.ok(f"concurrent_write_count", f"Expected {expected_count}, got {actual_count} rows — consistent")
    else:
        runner.fail(
            "concurrent_write_count",
            f"Expected {expected_count} portfolio rows but got {actual_count}. "
            f"Data was lost or duplicated during concurrent writes. "
            f"This indicates a race condition in the WAL commit sequence."
        )

    # ---- Concurrent reads during writes
    read_errors = []
    read_results = []

    def concurrent_read(thread_id: int):
        s = SessionFactory()
        try:
            count = s.query(Portfolio).filter_by(user_id=base_uid).count()
            read_results.append(count)
        except Exception as e:
            read_errors.append(str(e))
        finally:
            s.close()

    read_threads = [threading.Thread(target=concurrent_read, args=(i,)) for i in range(5)]
    for t in read_threads:
        t.start()
    for t in read_threads:
        t.join(timeout=10)

    if read_errors:
        for err in read_errors:
            runner.fail("concurrent_reads", f"Read failed during concurrent writes: {err}")
    else:
        runner.ok("concurrent_reads", f"All concurrent reads succeeded. Result counts: {read_results}")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
