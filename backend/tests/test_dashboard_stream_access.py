"""REL-11: dashboard stream and AI-engine monitor are admin-only operator views."""

import asyncio
from typing import cast

import pytest
from fastapi import Request


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dashboard/ai-engine",
        "/api/v1/dashboard/ai-engine/some-job-id",
        "/api/v1/dashboard/stream",
    ],
)
def test_non_admin_user_gets_403_and_anonymous_gets_401(client, auth_headers, path):
    # auth_headers belongs to test_nivesh_9999, which is never promoted to admin.
    assert client.get(path, headers=auth_headers).status_code == 403
    assert client.get(path).status_code == 401


def test_ai_engine_limit_is_bounded(client, monkeypatch):
    monkeypatch.setattr("routers.dashboard.require_admin", lambda authorization: 1)

    response = client.get(
        "/api/v1/dashboard/ai-engine?limit=100000",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 422


def test_stream_generator_terminates_after_max_duration(monkeypatch):
    from routers import dashboard

    monkeypatch.setattr(dashboard, "_STREAM_MAX_SEC", 0)
    monkeypatch.setattr(dashboard, "get_dashboard_snapshot", lambda: {"type": "dashboard_snapshot"})

    class _ConnectedRequest:
        async def is_disconnected(self):
            return False

    async def _collect():
        return [chunk async for chunk in dashboard.event_generator(cast(Request, _ConnectedRequest()))]

    chunks = asyncio.run(asyncio.wait_for(_collect(), timeout=5))

    assert chunks == ['data: {"type": "dashboard_snapshot"}\n\n']
