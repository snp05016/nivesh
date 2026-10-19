"""I04 focus cut: the forum and the IPO hub sit behind server flags, default off.

Every route of routers/forum.py ('forum') and routers/ipo.py ('ipo_hub') answers
404 FEATURE_DISABLED while its flag is off, on both the /api/v1 mount and the
legacy /api alias. Flags resolve from env here; the cache is reset around each case.
"""
import pytest

from services import feature_flags

_FORUM = {"code": "FEATURE_DISABLED", "feature": "forum"}
_IPO = {"code": "FEATURE_DISABLED", "feature": "ipo_hub"}


@pytest.fixture(autouse=True)
def _default_flags(monkeypatch):
    monkeypatch.delenv("NIVESH_FLAG_FORUM", raising=False)
    monkeypatch.delenv("NIVESH_FLAG_IPO_HUB", raising=False)
    feature_flags._reset_cache()
    yield
    feature_flags._reset_cache()


def _disabled(resp, detail) -> bool:
    return resp.status_code == 404 and resp.json().get("detail") == detail


def test_forum_off_by_default(client):
    assert _disabled(client.get("/api/forum/boards"), _FORUM)
    assert _disabled(client.get("/api/v1/forum/boards"), _FORUM)


def test_ipo_hub_off_by_default(client):
    assert _disabled(client.get("/api/ipo"), _IPO)
    assert _disabled(client.get("/api/v1/ipo"), _IPO)


def test_forum_post_blocked_while_off(client, auth_headers):
    # The flag dependency runs before auth and body validation, so even a signed-in
    # caller with an empty body gets the flag 404, never a 401 or 422.
    assert _disabled(client.post("/api/forum/threads", json={}, headers=auth_headers), _FORUM)


def test_forum_on_via_env(client, monkeypatch):
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    feature_flags._reset_cache()
    resp = client.get("/api/forum/boards")
    assert not _disabled(resp, _FORUM)
    assert resp.status_code == 200


def test_ipo_hub_on_via_env(client, monkeypatch):
    monkeypatch.setenv("NIVESH_FLAG_IPO_HUB", "true")
    feature_flags._reset_cache()
    resp = client.get("/api/ipo")
    assert not _disabled(resp, _IPO)
    assert resp.status_code == 200


def test_flags_are_independent(client, monkeypatch):
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    feature_flags._reset_cache()
    assert _disabled(client.get("/api/ipo"), _IPO)
