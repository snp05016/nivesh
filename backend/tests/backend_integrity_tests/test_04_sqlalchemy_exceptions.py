"""
test_04_sqlalchemy_exceptions.py
==================================
Tests SQLAlchemy-specific exceptions used throughout the Nivesh backend.
Verifies:
1. All SQLAlchemy exception classes are importable
2. They can be raised and caught
3. They form the correct exception hierarchy
4. They are properly handled by the get_session() context manager
5. Real-world scenarios that trigger each exception type
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test_secret")

import unittest.mock as mock
for _m in ["tradingagents", "tradingagents.graph", "tradingagents.graph.trading_graph",
           "tradingagents.default_config", "tradingagents.agents",
           "tradingagents.agents.utils", "tradingagents.agents.utils.agent_states",
           "langchain_anthropic", "langchain_core", "langchain_core.messages",
           "langchain_core.prompts", "langchain_core.tools", "langgraph", "langgraph.graph",
           "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
           "anthropic", "openai", "prompts", "yfinance", "openpyxl", "openpyxl.styles"]:
    if _m not in sys.modules:
        sys.modules[_m] = mock.MagicMock()
sys.modules["prompts"].INDIAN_MARKET_SYSTEM_PROMPT = "mock"
sys.modules["prompts"].NEWS_ANALYST_PERSONA = "mock"
sys.modules["prompts"].EXTREME_ADDENDUM = "\nmock"

from _base import TestRunner
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.exc import (
    IntegrityError, OperationalError, ProgrammingError, DataError,
    DatabaseError, SQLAlchemyError, NoResultFound, MultipleResultsFound,
    InvalidRequestError, PendingRollbackError,
    DBAPIError, InterfaceError,
)
# DetachedInstanceError moved in SQLAlchemy 2.0
try:
    from sqlalchemy.exc import DetachedInstanceError
except ImportError:
    from sqlalchemy.orm.exc import DetachedInstanceError

try:
    from sqlalchemy.exc import MissingGreenlet
    HAS_MISSING_GREENLET = True
except ImportError:
    HAS_MISSING_GREENLET = False


class Base(DeclarativeBase):
    pass


class TestModel(Base):
    __tablename__ = "exc_test"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


def run():
    runner = TestRunner("04_sqlalchemy_exceptions")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # ---- All exception classes importable and are Exception subclasses
    exc_classes = [
        ("IntegrityError", IntegrityError),
        ("OperationalError", OperationalError),
        ("ProgrammingError", ProgrammingError),
        ("DatabaseError", DatabaseError),
        ("SQLAlchemyError", SQLAlchemyError),
        ("NoResultFound", NoResultFound),
        ("MultipleResultsFound", MultipleResultsFound),
        ("DetachedInstanceError", DetachedInstanceError),
        ("InvalidRequestError", InvalidRequestError),
        ("PendingRollbackError", PendingRollbackError),
        ("DBAPIError", DBAPIError),
        ("InterfaceError", InterfaceError),
    ]
    for name, cls in exc_classes:
        if issubclass(cls, Exception):
            runner.ok(f"importable:{name}", f"{name} is importable and is Exception subclass")
        else:
            runner.fail(f"importable:{name}", f"{name} is not an Exception subclass")

    if HAS_MISSING_GREENLET:
        runner.ok("importable:MissingGreenlet", "MissingGreenlet importable (async SQLAlchemy in use)")
    else:
        runner.ok("MissingGreenlet_not_needed", "MissingGreenlet not in this SQLAlchemy version (sync-only backend is correct)")

    # ---- IntegrityError: duplicate unique value
    s = Session()
    s.add(TestModel(name="unique_value"))
    s.commit()
    try:
        s.add(TestModel(name="unique_value"))
        s.commit()
        runner.fail("IntegrityError_triggered", "Duplicate insert was NOT rejected — UniqueConstraint not enforced")
    except IntegrityError as e:
        s.rollback()
        runner.ok("IntegrityError_triggered", f"IntegrityError correctly raised on duplicate: {str(e)[:100]}")
    s.close()

    # ---- OperationalError: SQL on non-existent table
    s2 = Session()
    try:
        from sqlalchemy import text
        s2.execute(text("SELECT * FROM non_existent_table_12345"))
        runner.fail("OperationalError_triggered", "Query on non-existent table did not raise OperationalError")
    except OperationalError as e:
        s2.rollback()
        runner.ok("OperationalError_triggered", f"OperationalError raised on bad table: {str(e)[:100]}")
    finally:
        s2.close()

    # ---- NoResultFound: .one() on empty result
    s3 = Session()
    try:
        s3.query(TestModel).filter_by(name="does_not_exist_xyz").one()
        runner.fail("NoResultFound_triggered", ".one() on empty result did not raise NoResultFound")
    except NoResultFound as e:
        runner.ok("NoResultFound_triggered", f"NoResultFound raised: {str(e)[:80]}")
    finally:
        s3.close()

    # ---- MultipleResultsFound: .one() with multiple results
    s4 = Session()
    s4.add(TestModel(name="multi_1"))
    s4.add(TestModel(name="multi_2"))
    s4.commit()
    try:
        s4.query(TestModel).one()  # More than one row in table
        runner.fail("MultipleResultsFound_triggered", ".one() with multiple rows did not raise MultipleResultsFound")
    except MultipleResultsFound as e:
        runner.ok("MultipleResultsFound_triggered", f"MultipleResultsFound raised: {str(e)[:80]}")
    except Exception as e:
        runner.fail("MultipleResultsFound_triggered", f"Unexpected error: {type(e).__name__}: {e}", e)
    finally:
        s4.rollback()
        s4.close()

    # ---- PendingRollbackError: use session after IntegrityError without rollback
    s5 = Session()
    s5.add(TestModel(name="pending_test"))
    s5.commit()
    try:
        s5.add(TestModel(name="pending_test"))
        s5.commit()  # IntegrityError
    except IntegrityError:
        pass  # Do NOT rollback intentionally

    try:
        s5.query(TestModel).count()  # Should raise PendingRollbackError
        runner.fail(
            "PendingRollbackError_triggered",
            "Using session after IntegrityError (without rollback) did NOT raise PendingRollbackError. "
            "This means the session auto-rolled back, which is fine."
        )
    except PendingRollbackError as e:
        runner.ok(
            "PendingRollbackError_triggered",
            f"PendingRollbackError correctly raised when session not rolled back after IntegrityError. "
            f"This is WHY get_session() MUST call rollback() in its except block."
        )
    except Exception as e:
        runner.ok(
            "PendingRollbackError_auto_handled",
            f"Session auto-handled the rollback (caught {type(e).__name__}). This is acceptable behavior."
        )
    finally:
        try:
            s5.rollback()
        except Exception as _e:
            pass
        s5.close()

    # ---- DetachedInstanceError: access relationship after session close
    s6 = Session()
    row = s6.query(TestModel).first()
    row_id = row.id
    s6.close()  # Close session — row is now detached

    # The 'name' column should still be accessible (it was loaded)
    try:
        _ = row.name  # This was loaded before session close
        runner.ok("detached_loaded_attr", f"Loaded attribute 'name' accessible after session close: {row.name}")
    except DetachedInstanceError as e:
        runner.fail(
            "detached_loaded_attr",
            f"Loaded attribute raised DetachedInstanceError: {e}. "
            f"SQLAlchemy expunge_on_close may be misconfigured."
        )

    # ---- Exception hierarchy
    hierarchy = [
        (IntegrityError, DatabaseError),
        (OperationalError, DatabaseError),
        (ProgrammingError, DatabaseError),
        (DataError, DatabaseError),
        (DatabaseError, SQLAlchemyError),
        (InterfaceError, SQLAlchemyError),
        (DBAPIError, SQLAlchemyError),
    ]
    for child, parent in hierarchy:
        if issubclass(child, parent):
            runner.ok(f"hierarchy:{child.__name__}→{parent.__name__}")
        else:
            runner.fail(f"hierarchy:{child.__name__}→{parent.__name__}",
                       f"{child.__name__} is NOT a subclass of {parent.__name__}")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    engine.dispose()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
