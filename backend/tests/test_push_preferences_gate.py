"""IOSCORE-23: the stored alerts_enabled preference gates every APNs push path.

The price-alert poller path is covered by
test_notifications_inbox_producer.test_alerts_disabled_skips_push.
"""
from contextlib import contextmanager

import pytest

from services import preferences, user_service


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


def test_deliver_apns_returns_false_when_disabled(monkeypatch):
    # Record the call: _deliver_apns swallows exceptions from get_session,
    # so a raising sentinel alone would not catch a removed gate.
    called = []

    def _no_db():
        called.append(True)
        raise RuntimeError("token lookup must not run when pushes are off")

    monkeypatch.setattr(user_service, "push_allowed", lambda _uid: False)
    monkeypatch.setattr(user_service, "get_session", _no_db)

    assert user_service._deliver_apns(1, {"title": "TCS"}) is False
    assert not called


def test_deliver_apns_runs_when_allowed(monkeypatch):
    class _Query:
        def filter_by(self, **_kw):
            return self

        def all(self):
            return [type("DT", (), {"platform": "ios", "device_token": "a" * 64})()]

    class _Session:
        def query(self, _model):
            return _Query()

    @contextmanager
    def _get_session():
        yield _Session()

    monkeypatch.setattr(user_service, "push_allowed", lambda _uid: True)
    monkeypatch.setattr(user_service, "get_session", _get_session)

    assert user_service._deliver_apns(1, {"title": "TCS"}) is True
