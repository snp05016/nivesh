"""GH-664: (user_id, device_id) is unique on device_bindings, not on the
append-only device_binding_attempts audit log, so re-binding the same device
logs a second attempt instead of raising IntegrityError."""
from contextlib import contextmanager
from typing import cast

import pytest
from sqlalchemy import UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# conftest.py patches heavy modules before any app import — rely on that here.
from models.db_models import Base, DeviceBinding, DeviceBindingAttempt, User
from services import kyc_consent_service


def _unique_column_sets(model):
    return [
        sorted(col.name for col in c.columns)
        for c in model.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def test_unique_constraint_on_binding_not_attempts():
    assert ["device_id", "user_id"] in _unique_column_sets(DeviceBinding)
    assert _unique_column_sets(DeviceBindingAttempt) == []


@pytest.fixture()
def temp_db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    @contextmanager
    def fake_get_session():
        session = TestSession()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(kyc_consent_service, "get_session", fake_get_session)
    yield TestSession
    engine.dispose()


def test_rebind_same_device_logs_two_attempts(temp_db):
    with temp_db() as session:
        user = User(username="device_rebind_user", password_hash="x", display_name="Rebind")
        session.add(user)
        session.commit()
        uid = cast(int, user.id)

    first = kyc_consent_service.bind_device(uid, "dev-1")
    second = kyc_consent_service.bind_device(uid, "dev-1")

    assert first["device_id"] == "dev-1"
    assert second["device_id"] == "dev-1"
    assert second["id"] == first["id"]

    with temp_db() as session:
        assert session.query(DeviceBinding).filter_by(user_id=uid).count() == 1
        attempts = session.query(DeviceBindingAttempt).filter_by(user_id=uid).all()
        assert [a.outcome for a in attempts] == ["bound", "bound"]
