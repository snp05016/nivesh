"""AUTH-09 / GH-461: the legacy /notifications/* routes require the caller's own bearer.

Before the fix they trusted a body user_id, so anyone could bind their APNs token to
a victim (and receive the victim's price-alert pushes) or probe user ids.
"""
import random
import secrets
from unittest.mock import MagicMock

import pytest

import database
import routers.user as user_router
from database import create_access_token
from models.db_models import DeviceToken, User


def _user() -> tuple[int, dict]:
    uid = random.randint(30_000_000, 39_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"notif_{uid}", password_hash="x", display_name="Notif Test"))
        session.commit()
    return uid, {"Authorization": f"Bearer {create_access_token(uid)}"}


@pytest.fixture
def users():
    return _user(), _user()


def _tokens_for(uid: int, device_token: str) -> int:
    with database.get_session() as session:
        return session.query(DeviceToken).filter_by(user_id=uid, device_token=device_token).count()


def test_register_device_requires_own_token(client, users):
    (a, a_headers), (b, b_headers) = users
    url = "/notifications/register-device"
    device = secrets.token_hex(32)  # 64 hex chars

    assert client.post(url, json={"user_id": a, "device_token": device}).status_code == 401

    hijack = client.post(url, json={"user_id": a, "device_token": device}, headers=b_headers)
    assert hijack.status_code == 403
    assert _tokens_for(a, device) == 0

    own = client.post(url, json={"user_id": b, "device_token": device}, headers=b_headers)
    assert own.status_code == 200
    assert _tokens_for(b, device) == 1

    # DB-26: the same phone, now logged in as A, re-binds the token to A.
    rebound = client.post(url, json={"user_id": a, "device_token": device}, headers=a_headers)
    assert rebound.status_code == 200
    assert _tokens_for(a, device) == 1
    assert _tokens_for(b, device) == 0

    bad = client.post(url, json={"user_id": b, "device_token": "not-hex"}, headers=b_headers)
    assert bad.status_code == 400


def test_notifications_test_requires_own_token(client, users, monkeypatch):
    (a, _), (b, b_headers) = users
    build = MagicMock(return_value={"ok": True})
    monkeypatch.setattr(user_router.user_service, "test_notification", build)
    url = "/notifications/test"

    assert client.post(url, json={"user_id": a, "ticker": "TCS"}).status_code == 401
    assert client.post(url, json={"user_id": a, "ticker": "TCS"}, headers=b_headers).status_code == 403
    build.assert_not_called()

    assert client.post(url, json={"user_id": b, "ticker": "TCS"}, headers=b_headers).status_code == 200
    build.assert_called_once_with(b, "TCS", "NSE")


def test_morning_summary_push_requires_own_token(client, users, monkeypatch):
    (a, _), (_b, b_headers) = users
    push = MagicMock()
    monkeypatch.setattr(user_router.user_service, "push_morning_summary", push)
    url = "/notifications/morning-summary-push"

    assert client.post(url, json={"user_id": a}).status_code == 401
    assert client.post(url, json={"user_id": a}, headers=b_headers).status_code == 403
    push.assert_not_called()
