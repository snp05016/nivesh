"""CMON-18: the notification inbox has a producer (price alerts, morning brief)."""
import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, InAppNotification, PriceTarget, User, UserPreference
from services import alerts_service, notifications_inbox, preferences


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        yield session

    for mod in (alerts_service, notifications_inbox, preferences):
        monkeypatch.setattr(mod, "get_session", _get_session)
    session.add(User(id=1, username="inbox_user", password_hash="x", display_name="Inbox"))
    session.commit()
    yield session
    session.close()


def test_create_notification_visible_in_inbox(db_session):
    nid = notifications_inbox.create_notification(
        1, "system", "Hello", "Body text", action_url="nivesh://home"
    )
    rows = notifications_inbox.get_notifications(1)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == nid
    assert (row["type"], row["title"], row["body"]) == ("system", "Hello", "Body text")
    assert row["action_url"] == "nivesh://home"
    assert row["is_read"] is False


def _run_poller_once(monkeypatch, push_result=False):
    db = alerts_service.get_session
    with db() as s:
        s.add(PriceTarget(user_id=1, ticker="TCS", target_price=100.0, direction="above", triggered=False))
        s.commit()
    monkeypatch.setattr(alerts_service, "_yf_price", lambda _t: (150.0, 140.0))
    push = AsyncMock(return_value=push_result)
    monkeypatch.setattr(alerts_service, "_send_apns_push", push)
    asyncio.run(alerts_service._poll_once())
    return push


def test_poller_trigger_creates_inbox_row(db_session, monkeypatch):
    push = _run_poller_once(monkeypatch, push_result=False)

    notif = db_session.query(InAppNotification).filter_by(user_id=1).one()
    assert notif.type == "price_alert"
    assert "TCS" in notif.title
    assert notif.action_url == "nivesh://analyze/TCS"
    # A failed push no longer leaves the alert re-triggering every pass.
    assert db_session.query(PriceTarget).one().triggered is True
    push.assert_awaited_once()


def test_alerts_disabled_skips_push(db_session, monkeypatch):
    db_session.add(UserPreference(user_id=1, alerts_enabled=False))
    db_session.commit()

    push = _run_poller_once(monkeypatch, push_result=True)

    push.assert_not_awaited()
    assert db_session.query(InAppNotification).filter_by(user_id=1).count() == 1
    assert db_session.query(PriceTarget).one().triggered is True


def test_morning_summary_push_requires_own_token(client, auth_headers, test_user_id):
    url = "/notifications/morning-summary-push"
    assert client.post(url, json={"user_id": test_user_id}).status_code == 401
    other = client.post(url, json={"user_id": test_user_id + 1}, headers=auth_headers)
    assert other.status_code == 403
