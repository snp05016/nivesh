"""IOSCORE-23: the stored alerts_enabled preference gates every APNs push path.

The price-alert poller path is covered by
test_notifications_inbox_producer.test_alerts_disabled_skips_push.
"""
import pytest

from services import preferences, user_service
from services.alerts_service import PushResult


@pytest.mark.parametrize(
    "prefs, expected",
    [
        (None, True),                       # no row: default on
        ({"alerts_enabled": True}, True),
        ({"alerts_enabled": None}, True),
        ({"alerts_enabled": False}, False),  # only an explicit off suppresses
    ],
)
def test_push_allowed(monkeypatch, prefs, expected):
    monkeypatch.setattr(preferences, "get_preferences", lambda _uid: prefs)
    assert preferences.push_allowed(1) is expected


def test_deliver_apns_disabled_skips_send(monkeypatch):
    called = []

    async def _send(*args):
        called.append(args)
        return PushResult.SENT

    monkeypatch.setattr(user_service, "push_allowed", lambda _uid: False)
    monkeypatch.setattr(user_service, "send_apns", _send)

    assert user_service._deliver_apns(1, {"title": "TCS", "body": "b"}) is PushResult.DISABLED
    assert not called


def test_deliver_apns_uses_real_sender_when_allowed(monkeypatch):
    """SILENT-07: no more log-only stub; the result is the real sender's."""
    called = []

    async def _send(*args):
        called.append(args)
        return PushResult.NOT_CONFIGURED

    monkeypatch.setattr(user_service, "push_allowed", lambda _uid: True)
    monkeypatch.setattr(user_service, "send_apns", _send)

    result = user_service._deliver_apns(1, {"title": "TCS", "body": "b", "data": {"ticker": "TCS"}})

    assert result is PushResult.NOT_CONFIGURED
    assert called == [(1, "TCS", "b", {"ticker": "TCS"})]
