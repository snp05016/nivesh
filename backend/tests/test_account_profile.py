"""GH-692: PATCH /api/v1/me/profile persists the display name server-side.

The iOS Profile screen used to show 'PROFILE SAVED' without saving anything.
"""
from __future__ import annotations

from tests.conftest import TEST_DISPLAY, TEST_PASSWORD, TEST_USERNAME

URL = "/api/v1/me/profile"


def test_patch_profile_updates_display_name(client, auth_headers):
    try:
        resp = client.patch(URL, json={"display_name": "  New Name  "}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["display_name"] == "New Name"
        assert resp.json()["username"] == TEST_USERNAME

        login = client.post("/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
        assert login.status_code == 200
        assert login.json()["display_name"] == "New Name"
    finally:
        # The test user is session-scoped; leave its name as other tests expect.
        client.patch(URL, json={"display_name": TEST_DISPLAY}, headers=auth_headers)


def test_patch_profile_rejects_blank(client, auth_headers):
    assert client.patch(URL, json={"display_name": "   "}, headers=auth_headers).status_code == 422


def test_patch_profile_rejects_too_long(client, auth_headers):
    assert client.patch(URL, json={"display_name": "x" * 101}, headers=auth_headers).status_code == 422


def test_patch_profile_requires_auth(client):
    assert client.patch(URL, json={"display_name": "Someone"}).status_code == 401
