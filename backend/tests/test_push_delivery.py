"""SILENT-07 / REL-09: push paths report what actually happened.

send_apns returns an explicit PushResult (never "success" when nothing was sent),
reuses one HTTP/2 client per push and one provider JWT per 50 minutes, and the
user_service push helpers report delivered=false instead of a fake success.
"""
import asyncio
from contextlib import contextmanager

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import Base, DeviceToken, User
from services import alerts_service, user_service
from services.alerts_service import PushResult

_APNS_ENV = ("APNS_AUTH_KEY_PATH", "APNS_KEY_ID", "APNS_TEAM_ID")
_TOKEN_OK = "a" * 64
_TOKEN_DEAD = "b" * 64


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

    monkeypatch.setattr(alerts_service, "get_session", _get_session)
    monkeypatch.setattr(alerts_service, "_provider_tokens", {})
    with _get_session() as s:
        s.add(User(id=1, username="push_user", password_hash="x", display_name="Push"))
        s.commit()
    yield _get_session
    engine.dispose()


def _add_tokens(db, *tokens):
    with db() as s:
        for t in tokens:
            s.add(DeviceToken(user_id=1, device_token=t, platform="ios"))
        s.commit()


def _send():
    return asyncio.run(alerts_service.send_apns(1, "TCS Alert", "TCS crossed", {"type": "price_alert"}))


def test_no_tokens_is_not_success(db, monkeypatch):
    for k in _APNS_ENV:
        monkeypatch.setenv(k, "x")
    assert _send() is PushResult.NO_TOKENS


def test_unconfigured_apns_is_not_success(db, monkeypatch):
    _add_tokens(db, _TOKEN_OK)
    for k in _APNS_ENV:
        monkeypatch.delenv(k, raising=False)
    assert _send() is PushResult.NOT_CONFIGURED


def test_one_client_per_push_and_cached_provider_token(db, monkeypatch, tmp_path):
    _add_tokens(db, _TOKEN_OK, _TOKEN_DEAD)
    key = tmp_path / "AuthKey.p8"
    key.write_bytes(ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(key))
    monkeypatch.setenv("APNS_KEY_ID", "KEYID")
    monkeypatch.setenv("APNS_TEAM_ID", "TEAMID")

    real_encode = alerts_service.pyjwt.encode
    mints = []

    def _encode(*a, **k):
        mints.append(1)
        return real_encode(*a, **k)

    monkeypatch.setattr(alerts_service.pyjwt, "encode", _encode)

    requests = []

    def _handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith(_TOKEN_DEAD):
            return httpx.Response(410, json={"reason": "Unregistered"})
        return httpx.Response(200)

    real_client = httpx.AsyncClient
    clients = []

    def _client(*_a, **_k):
        clients.append(1)
        return real_client(transport=httpx.MockTransport(_handler))

    monkeypatch.setattr(alerts_service.httpx, "AsyncClient", _client)

    assert _send() is PushResult.SENT
    assert sorted(r.url.path for r in requests) == [f"/3/device/{_TOKEN_OK}", f"/3/device/{_TOKEN_DEAD}"]
    assert all(r.headers["authorization"].startswith("bearer ") for r in requests)
    assert len(clients) == 1  # one client for both devices
    with db() as s:
        assert [t for (t,) in s.query(DeviceToken.device_token).all()] == [_TOKEN_OK]  # 410 pruned

    assert _send() is PushResult.SENT
    assert len(mints) == 1  # provider JWT reused, not minted per push


def test_user_service_push_reports_not_delivered(db, monkeypatch):
    # The user-facing push routes (morning summary) report what actually happened.
    for k in _APNS_ENV:
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(user_service, "push_allowed", lambda _uid: True)
    payload = {"title": "Daily Market Brief", "body": "b", "data": {"type": "morning_summary"}}

    out = user_service._with_delivery(payload, user_service._deliver_apns(1, payload))

    assert out["delivered"] is False
    assert out["delivery_status"] == "no_tokens"
    assert out["title"] == "Daily Market Brief"  # iOS decodes title/body at the root
