"""DB-12: price-alert poller claims alerts atomically and prunes dead APNs tokens."""
import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import Base, DeviceToken, InAppNotification, PriceTarget, User
from services import alerts_service, notifications_inbox, preferences


@pytest.fixture()
def db(monkeypatch):
    """One in-memory DB, a fresh session per get_session() call (like production)."""
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

    for mod in (alerts_service, notifications_inbox, preferences):
        monkeypatch.setattr(mod, "get_session", _get_session)
    with _get_session() as s:
        s.add(User(id=1, username="poller_user", password_hash="x", display_name="Poller"))
        s.add(PriceTarget(user_id=1, ticker="TCS", target_price=100.0,
                          direction="above", triggered=False))
        s.commit()
    yield _get_session
    engine.dispose()


def _poll(monkeypatch, price, pollers=1, push_result=True):
    monkeypatch.setattr(alerts_service, "_yf_price", lambda _t: (price, price - 10))
    push = AsyncMock(return_value=push_result)
    monkeypatch.setattr(alerts_service, "_send_apns_push", push)

    async def _run():
        await asyncio.gather(*(alerts_service._poll_once() for _ in range(pollers)))

    asyncio.run(_run())
    return push


def test_concurrent_pollers_single_push(db, monkeypatch):
    push = _poll(monkeypatch, 120.0, pollers=2)

    push.assert_awaited_once()
    with db() as s:
        assert s.query(PriceTarget).one().triggered is True
        assert s.query(InAppNotification).filter_by(user_id=1).count() == 1


def test_untriggered_when_price_not_crossed(db, monkeypatch):
    push = _poll(monkeypatch, 90.0)

    push.assert_not_awaited()
    with db() as s:
        assert s.query(PriceTarget).one().triggered is False
        assert s.query(InAppNotification).count() == 0


def test_failed_push_does_not_repeat_delivery(db, monkeypatch):
    """The inbox row is the durable delivery: a failed push neither re-triggers
    nor leaves a dirty flag for a later commit."""
    first = _poll(monkeypatch, 120.0, push_result=False)
    second = _poll(monkeypatch, 120.0)

    first.assert_awaited_once()
    second.assert_not_awaited()
    with db() as s:
        assert s.query(InAppNotification).filter_by(user_id=1).count() == 1


class _Resp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = ""

    def json(self):
        return self._body


@pytest.mark.parametrize("status_code,body,pruned", [
    (410, {"reason": "Unregistered"}, True),
    (400, {"reason": "BadDeviceToken"}, True),
    (400, {"reason": "BadTopic"}, False),
    (500, {}, False),
])
def test_dead_token_pruned(db, monkeypatch, tmp_path, status_code, body, pruned):
    with db() as s:
        s.add(DeviceToken(user_id=1, device_token="deadbeef", platform="ios"))
        s.commit()
    key = tmp_path / "AuthKey.p8"
    key.write_text("not-a-real-key")
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(key))
    monkeypatch.setenv("APNS_KEY_ID", "KEYID")
    monkeypatch.setenv("APNS_TEAM_ID", "TEAMID")
    monkeypatch.setattr(alerts_service.pyjwt, "encode", lambda *_a, **_k: "token")

    class _Client:
        def __init__(self, *_a, **_k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def post(self, *_a, **_k):
            return _Resp(status_code, body)

    monkeypatch.setattr(alerts_service.httpx, "AsyncClient", _Client)

    result = asyncio.run(alerts_service._send_apns_push(
        user_id=1, ticker="TCS", target_price=100.0, current_price=120.0, direction="above"))

    PR = alerts_service.PushResult
    assert result == (PR.NO_TOKENS if pruned else PR.FAILED)
    with db() as s:
        remaining = s.query(DeviceToken).filter_by(user_id=1).count()
    assert remaining == (0 if pruned else 1)
