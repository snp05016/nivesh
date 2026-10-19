"""Shared fixture helper for the data-cluster tests: an in-memory SQLite behind database.get_session."""
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from models.db_models import Base


def patch_get_session(monkeypatch, *modules):
    """Create all tables in a fresh in-memory DB (foreign keys on) and route get_session() (and the given modules' own binding) to it; returns a factory."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)

    @contextmanager
    def fake_get_session():
        s = factory()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(database, "get_session", fake_get_session)
    for module in modules:  # modules that did `from database import get_session` at import time
        monkeypatch.setattr(module, "get_session", fake_get_session)
    return factory
