"""user_events storage: schema, erasure registration, retention and the consent backstop."""
import importlib
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from database import ENGINE, get_session
from models.db_models import Base, KYCConsent, User, UserEvent
from services import job_runs, retention


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.create_all(ENGINE)


def _user() -> int:
    with get_session() as s:
        u = User(username=f"ev_{uuid4().hex[:12]}", password_hash="x", display_name="E")
        s.add(u)
        s.commit()
        return int(u.id)


def _consent(uid, granted=True, revoked=False):
    now = job_runs._now()
    with get_session() as s:
        s.add(KYCConsent(user_id=uid, consent_type="product_analytics", granted=granted,
                         revoked_at=now if revoked else None))
        s.commit()


def _event(uid, age_days=1.0, name="app_open"):
    with get_session() as s:
        s.add(UserEvent(user_id=uid, event_name=name, props={"launch": "cold"},
                        created_at=job_runs._now() - timedelta(days=age_days)))
        s.commit()


def _count(uid) -> int:
    with get_session() as s:
        return s.query(UserEvent).filter(UserEvent.user_id == uid).count()


@pytest.fixture(autouse=True)
def _quiet_retention(monkeypatch):
    monkeypatch.setattr(retention, "_rotate_token_log", lambda: 0)


def test_table_and_indexes():
    insp = inspect(ENGINE)
    assert "user_events" in insp.get_table_names()
    names = {i["name"] for i in insp.get_indexes("user_events")}
    assert {"ix_user_events_name_created", "ix_user_events_user_created"} <= names


def test_erasure_policy_registered():
    from services.compliance_service import ERASURE_POLICY, user_fk_columns

    assert ERASURE_POLICY["user_events.user_id"] == "delete"
    fks = {f"{t.name}.{c.name}" for t, c in user_fk_columns()}
    assert fks - set(ERASURE_POLICY) == set()


def test_erase_user_removes_events():
    from services.compliance_service import erase_user

    uid, other = _user(), _user()
    _event(uid)
    _event(other)
    erase_user(uid)
    assert _count(uid) == 0 and _count(other) == 1


def test_old_events_deleted_for_consenting_user():
    uid = _user()
    _consent(uid)
    _event(uid, age_days=181)
    _event(uid, age_days=1)
    assert retention.run_retention()["user_events_deleted"] >= 1
    assert _count(uid) == 1


def test_longer_retention_keeps_181_day_event(monkeypatch):
    monkeypatch.setattr(retention, "USER_EVENTS_RETENTION_DAYS", 365)
    uid = _user()
    _consent(uid)
    _event(uid, age_days=181)
    retention.run_retention()
    assert _count(uid) == 1


def test_events_without_active_consent_deleted():
    never, revoked, kept = _user(), _user(), _user()
    _event(never)
    _consent(revoked, granted=True, revoked=True)
    _event(revoked)
    _consent(kept)
    _event(kept)
    retention.run_retention()
    assert (_count(never), _count(revoked), _count(kept)) == (0, 0, 1)


@pytest.mark.parametrize("raw,expected", [(None, 180), ("", 180), ("abc", 180), ("0", 180), ("-5", 180), ("365", 365)])
def test_retention_env_parsing(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("USER_EVENTS_RETENTION_DAYS", raising=False)
    else:
        monkeypatch.setenv("USER_EVENTS_RETENTION_DAYS", raw)
    assert retention._retention_days_from_env() == expected
