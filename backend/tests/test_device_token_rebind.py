"""DB-26: a device token follows whoever is logged in on the phone, and logout unregisters it."""
import secrets
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import helpers
from helpers import upsert_device_token
from models.db_models import Base, DeviceToken, User
from services import notifications_service
from services.notifications_service import unregister_user_device

A, B = 1, 2


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def _get_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    for mod in (helpers, notifications_service):
        monkeypatch.setattr(mod, "get_session", _get_session)
    with _get_session() as s:
        s.add(User(id=A, username="rebind_a", password_hash="x", display_name="A"))
        s.add(User(id=B, username="rebind_b", password_hash="x", display_name="B"))
        s.commit()
    yield _get_session
    engine.dispose()


def _rows(get_session, token):
    with get_session() as s:
        return [r.user_id for r in s.query(DeviceToken).filter_by(device_token=token).all()]


def test_rebind_to_second_user(db):
    token = secrets.token_hex(32)
    upsert_device_token(A, token)
    upsert_device_token(B, token)  # previously PermissionError
    assert _rows(db, token) == [B]


def test_unregister_only_own_token(db):
    token = secrets.token_hex(32)
    upsert_device_token(A, token)
    upsert_device_token(B, token)
    assert unregister_user_device(A, token) == {"status": "not_found"}
    assert _rows(db, token) == [B]
    assert unregister_user_device(B, token) == {"status": "unregistered"}
    assert _rows(db, token) == []


def test_unregister_rejects_bad_token(db):
    with pytest.raises(ValueError):
        unregister_user_device(A, "not-hex")


def test_unregister_endpoint(client, auth_headers, test_user_id):
    url = "/api/v1/notifications/unregister"
    token = secrets.token_hex(32)
    assert client.post(url, json={"device_token": token}).status_code == 401

    upsert_device_token(test_user_id, token)
    resp = client.post(url, json={"device_token": token}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"status": "unregistered"}

    again = client.post(url, json={"device_token": token}, headers=auth_headers)
    assert again.json() == {"status": "not_found"}
    assert client.post(url, json={"device_token": "bad"}, headers=auth_headers).status_code == 400
