"""TEST-10: route contracts for forum, IPO, mutual funds, the notification inbox
and preferences.

Moderation, vote-counter internals and MF provenance have their own files
(test_forum_moderation_api.py, test_forum_vote_counters.py,
test_mutual_fund_provenance.py); this file checks the happy paths, the Swift
DTO keys and per-user isolation. The IPO and MF catalogs are the local mock
seeds; nothing here touches the network.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

IOS_MODELS = Path(__file__).resolve().parents[2] / "ios" / "StockApp" / "stockme" / "stockme" / "Models"


def _swift_keys(file_name: str, struct: str) -> set[str]:
    """JSON keys of a Swift DTO: the raw values of its CodingKeys enum."""
    path = IOS_MODELS / file_name
    if not path.is_file():  # backend-only checkout (the server) has no iOS tree
        pytest.skip("iOS sources not present")
    body = path.read_text(encoding="utf-8").split(f"struct {struct}:", 1)[1]
    enum = body.split("enum CodingKeys", 1)[1].split("}", 1)[0]
    keys = set()
    for line in enum.splitlines():
        line = line.strip()
        if line.startswith("case "):
            for item in line[len("case "):].split(","):
                name, _, raw = item.partition("=")
                keys.add(raw.strip().strip('"') if raw else name.strip())
    return keys


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"cc_{uuid4().hex[:12]}", password_hash="x", display_name="Community Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.fixture(scope="module")
def catalogs():
    """GET handlers never seed (FAKE-06); seed the mock IPO and MF catalogs explicitly."""
    from services.ipo_service import seed_mock_ipos_if_empty
    from services.mutual_fund_service import seed_mock_funds_if_empty

    seed_mock_ipos_if_empty()
    seed_mock_funds_if_empty()


# ---------------------------------------------------------------------------
# Forum
# ---------------------------------------------------------------------------

def test_forum_thread_contract_and_vote_once_per_user(client):
    boards = client.get("/api/forum/boards")
    assert boards.status_code == 200, boards.text
    assert boards.json(), "forum boards are seeded at startup"

    _, author = _new_user()
    created = client.post(
        "/api/forum/threads",
        json={"board_id": boards.json()[0]["id"], "title": f"Thread {uuid4().hex[:6]}", "body": "Opening post body"},
        headers=author,
    )
    assert created.status_code == 200, created.text
    thread = created.json()
    assert _swift_keys("ForumModels.swift", "ForumThreadDetail") <= set(thread)
    op_id = next(p["id"] for p in thread["posts"] if p["is_op"])

    _, voter_a = _new_user()
    _, voter_b = _new_user()
    url = f"/api/forum/posts/{op_id}/vote"
    assert client.post(url, json={"direction": "up"}, headers=voter_a).json()["upvotes"] == 1
    assert client.post(url, json={"direction": "up"}, headers=voter_b).json()["upvotes"] == 2
    # Re-voting the same direction toggles the vote off; it never counts a user twice.
    again = client.post(url, json={"direction": "up"}, headers=voter_a).json()
    assert again["upvotes"] == 1 and again["user_vote"] == 0


# ---------------------------------------------------------------------------
# IPO and mutual funds (mock catalogs)
# ---------------------------------------------------------------------------

def test_ipo_list_detail_and_unknown(client, catalogs):
    resp = client.get("/api/ipo")
    assert resp.status_code == 200, resp.text
    ipos = resp.json()
    assert ipos
    assert client.get(f"/api/ipo/{ipos[0]['id']}").status_code == 200
    assert client.get("/api/ipo/999999").status_code == 404
    assert client.get("/api/ipo", params={"status": "bogus"}).status_code == 400


def test_mutual_fund_list_and_detail(client, catalogs):
    resp = client.get("/api/mutual-funds/")
    assert resp.status_code == 200, resp.text
    funds = resp.json()
    assert funds
    fund = next(f for f in funds if f["scheme_code"])
    detail = client.get(f"/api/mutual-funds/{fund['scheme_code']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == fund["id"]


# ---------------------------------------------------------------------------
# Notification inbox
# ---------------------------------------------------------------------------

def test_notifications_are_owner_only(client):
    from services.notifications_inbox import create_notification

    owner_id, owner = _new_user()
    _, stranger = _new_user()
    notif_id = create_notification(owner_id, "test", "Hello", "Body")

    listed = client.get("/api/v1/notifications", headers=owner)
    assert listed.status_code == 200, listed.text
    item = next(n for n in listed.json() if n["id"] == notif_id)
    assert _swift_keys("NotificationDTO.swift", "NotificationDTO") <= set(item)
    assert item["is_read"] is False

    assert notif_id not in {n["id"] for n in client.get("/api/v1/notifications", headers=stranger).json()}
    assert client.put(f"/api/v1/notifications/{notif_id}/read", headers=stranger).status_code in (403, 404)
    still_unread = next(n for n in client.get("/api/v1/notifications", headers=owner).json() if n["id"] == notif_id)
    assert still_unread["is_read"] is False

    assert client.put(f"/api/v1/notifications/{notif_id}/read", headers=owner).status_code == 200
    read = next(n for n in client.get("/api/v1/notifications", headers=owner).json() if n["id"] == notif_id)
    assert read["is_read"] is True


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def test_preferences_round_trip(client):
    user_id, headers = _new_user()
    first = client.get("/api/v1/preferences", headers=headers)
    assert first.status_code == 200, first.text
    assert set(first.json()) == _swift_keys("NotificationDTO.swift", "PreferenceDTO")
    assert first.json()["user_id"] == user_id

    flipped = not first.json()["alerts_enabled"]
    put = client.put("/api/v1/preferences", json={"alerts_enabled": flipped}, headers=headers)
    assert put.status_code == 200, put.text
    assert put.json()["alerts_enabled"] is flipped

    after = client.get("/api/v1/preferences", headers=headers).json()
    assert after["alerts_enabled"] is flipped
    assert after["theme"] == first.json()["theme"]
