"""GH-651: the morning-summary push uses the real brief builder and never pushes
canned fallback text as if it were a brief.

Before the fix push_morning_summary imported a symbol that does not exist
(routers.analysis.morning_summary_endpoint), swallowed the ImportError and pushed
"Check your portfolio today." to the user's devices, reporting success.
"""
from unittest.mock import MagicMock

import pytest

import routers.morning_brief as morning_brief
import services.user_service as user_service
from services.alerts_service import PushResult

URL = "/notifications/morning-summary-push"


@pytest.fixture
def deliver(monkeypatch):
    recorder = MagicMock(return_value=PushResult.SENT)
    monkeypatch.setattr(user_service, "_deliver_apns", recorder)
    return recorder


def test_push_requires_auth(client, test_user_id, deliver):
    assert client.post(URL, json={"user_id": test_user_id}).status_code == 401
    deliver.assert_not_called()


def test_push_rejects_other_user(client, auth_headers, test_user_id, deliver):
    resp = client.post(URL, json={"user_id": test_user_id + 1}, headers=auth_headers)
    assert resp.status_code == 403
    deliver.assert_not_called()


def test_push_uses_real_builder(client, auth_headers, test_user_id, deliver, monkeypatch):
    brief = {"summary": "• A", "mood": "positive",
             "priority_items": [{"ticker": "TCS", "action": "watch"}]}
    build = MagicMock(return_value=brief)
    monkeypatch.setattr(morning_brief, "build_morning_summary", build)

    resp = client.post(URL, json={"user_id": test_user_id}, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Flat payload: iOS decodes NotificationPayload(title, body, data) at the root.
    assert {"title", "body", "data"} <= set(body)
    assert "POSITIVE" in body["title"]
    assert "• A" in body["body"]
    build.assert_called_once_with(test_user_id)
    deliver.assert_called_once()


def test_push_failure_does_not_deliver(client, auth_headers, test_user_id, deliver, monkeypatch):
    monkeypatch.setattr(morning_brief, "build_morning_summary",
                        MagicMock(side_effect=ValueError("boom")))

    resp = client.post(URL, json={"user_id": test_user_id}, headers=auth_headers)

    assert resp.status_code == 503
    deliver.assert_not_called()


def test_push_refuses_canned_fallback(client, auth_headers, test_user_id, deliver, monkeypatch):
    fallback = {"summary": morning_brief.FALLBACK_SUMMARY, "movers": [], "mood": "cautious"}
    monkeypatch.setattr(morning_brief, "build_morning_summary", MagicMock(return_value=fallback))

    resp = client.post(URL, json={"user_id": test_user_id}, headers=auth_headers)

    assert resp.status_code == 503
    deliver.assert_not_called()
