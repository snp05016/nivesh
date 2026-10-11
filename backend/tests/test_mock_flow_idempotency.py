"""DB-27: account-deletion requests and device binds survive check-then-insert races.

Each test simulates the race deterministically: the service's existence check
sees no row, a "concurrent" request commits one in a separate session, and the
service's insert then hits the database uniqueness backstop. The service must
answer idempotently (the existing row) instead of raising or duplicating.
Completed loan disbursements are covered by tests/test_loan_disbursement.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import Base, DataDeletionRequest, DeviceBinding  # pyright: ignore[reportMissingImports]

USER_ID = 4242


class _NoRows:
    """Stands in for a query whose existence check ran before the competing insert."""

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return None


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _racing_get_session(engine, model, nth_query: int, competitor):
    """get_session whose nth query on `model` returns no rows after `competitor` commits."""
    seen = {"n": 0}

    class _RacingSession(Session):
        def query(self, *entities, **kwargs):  # type: ignore[override]
            if entities and entities[0] is model:
                seen["n"] += 1
                if seen["n"] == nth_query:
                    with Session(bind=engine) as other:
                        other.add(competitor())
                        other.commit()
                    return _NoRows()
            return super().query(*entities, **kwargs)

    factory = sessionmaker(bind=engine, class_=_RacingSession)

    @contextmanager
    def _get_session():
        s = factory()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    return _get_session


def _count(engine, model, **filters) -> int:
    with Session(bind=engine) as s:
        return s.query(model).filter_by(**filters).count()


def test_second_active_deletion_request_violates_unique_index(engine):
    with Session(bind=engine) as s:
        s.add(DataDeletionRequest(user_id=USER_ID, status="pending"))
        s.commit()
        s.add(DataDeletionRequest(user_id=USER_ID, status="processing"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        # Finished requests do not count as active.
        s.add_all([
            DataDeletionRequest(user_id=USER_ID, status="cancelled"),
            DataDeletionRequest(user_id=USER_ID, status="completed"),
        ])
        s.commit()


def test_existing_pending_request_is_returned(engine, monkeypatch):
    from services import compliance_service

    monkeypatch.setattr(compliance_service, "get_session", _racing_get_session(engine, None, 0, None))
    first = compliance_service.request_account_deletion(USER_ID, reason="first")
    second = compliance_service.request_account_deletion(USER_ID, reason="second")

    assert first["created"] is True
    assert second["created"] is False
    assert second["id"] == first["id"]
    assert _count(engine, DataDeletionRequest, user_id=USER_ID) == 1


def test_concurrent_deletion_request_returns_existing(engine, monkeypatch):
    from services import compliance_service

    monkeypatch.setattr(
        compliance_service,
        "get_session",
        _racing_get_session(
            engine, DataDeletionRequest, 1,
            lambda: DataDeletionRequest(user_id=USER_ID, status="pending", reason="winner"),
        ),
    )
    out = compliance_service.request_account_deletion(USER_ID, reason="loser")

    assert out["created"] is False
    assert _count(engine, DataDeletionRequest, user_id=USER_ID) == 1
    with Session(bind=engine) as s:
        winner: Any = s.query(DataDeletionRequest).one()
        assert winner.reason == "winner"


def test_concurrent_device_bind_returns_existing_binding(engine, monkeypatch):
    from services import kyc_consent_service

    # bind_device queries DeviceBinding for the cross-user check first, then for
    # this user's existing binding: race on the second lookup.
    monkeypatch.setattr(
        kyc_consent_service,
        "get_session",
        _racing_get_session(
            engine, DeviceBinding, 2,
            lambda: DeviceBinding(user_id=USER_ID, device_id="dev-1", is_primary=True),
        ),
    )
    out = kyc_consent_service.bind_device(USER_ID, "dev-1")

    assert out["user_id"] == USER_ID
    assert out["device_id"] == "dev-1"
    assert _count(engine, DeviceBinding, user_id=USER_ID, device_id="dev-1") == 1


def test_migration_cancels_duplicate_active_requests(tmp_path):
    from sqlalchemy import inspect

    backend_dir = Path(__file__).resolve().parents[1]
    db = tmp_path / "deletion.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}"}

    def _alembic(target):
        res = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", target],
            cwd=str(backend_dir), capture_output=True, text=True, env=env,
        )
        assert res.returncode == 0, res.stderr

    _alembic("814a5ca5bc07")  # revision before 2ea37dafbdbc
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'u1', 'x', 'U1')"))
        for status in ("pending", "processing", "completed"):
            c.execute(text("INSERT INTO data_deletion_requests (user_id, status) VALUES (1, :s)"), {"s": status})
    eng.dispose()

    _alembic("head")
    eng = create_engine(f"sqlite:///{db}")
    with eng.connect() as c:
        statuses = [r[0] for r in c.execute(text("SELECT status FROM data_deletion_requests ORDER BY id"))]
    names = {ix["name"] for ix in inspect(eng).get_indexes("data_deletion_requests")}
    eng.dispose()
    assert statuses == ["pending", "cancelled", "completed"]
    assert "uq_data_deletion_active" in names
