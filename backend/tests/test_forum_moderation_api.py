"""Forum report / block / moderation-queue API (App Store 1.2 UGC controls, UX-23).

Endpoints under test (prefix /api/forum):
  POST   /posts/{post_id}/report
  POST   /posts/{post_id}/block-author
  GET    /blocks
  DELETE /blocks/{block_id}
  GET    /admin/reports
  POST   /admin/reports/{report_id}/resolve
plus the viewer filtering of GET /boards/{id}/threads and GET /threads/{id}.

Uses the conftest session `client` against the temporary sqlite test DB.
FinBERT moderation is stubbed so nothing heavy loads.
"""
import uuid

import pytest

from core.security import require_admin
from database import get_session
from main import app
from models.db_models import ForumPost, ForumReport
from services import feature_flags
from tests.conftest import REGISTER_CONSENT

_ALLOW = {"action": "allow", "spam_score": 0, "sentiment": "neutral"}


@pytest.fixture(autouse=True)
def _focus_flags_on(monkeypatch):
    """I04: the forum and IPO hub are off by default; these tests exercise them."""
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    monkeypatch.setenv("NIVESH_FLAG_IPO_HUB", "true")
    feature_flags._reset_cache()
    yield
    feature_flags._reset_cache()


@pytest.fixture(autouse=True)
def _allow_all_posts(monkeypatch):
    monkeypatch.setattr("services.forum_service.moderate_post", lambda _body: dict(_ALLOW))
    # These tests register many throwaway users from one client IP.
    monkeypatch.setattr("routers.auth._check_rate_limit", lambda *_args, **_kwargs: True)


@pytest.fixture()
def as_admin():
    app.dependency_overrides[require_admin] = lambda: 1
    yield
    app.dependency_overrides.pop(require_admin, None)


def _new_user(client) -> dict:
    tag = uuid.uuid4().hex[:10]
    resp = client.post("/register", json={
        "username": f"forum_mod_{tag}",
        "password": "ForumPass!1234",
        "display_name": f"Forum Mod {tag}",
        **REGISTER_CONSENT,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"id": data["user_id"], "headers": {"Authorization": f"Bearer {data['access_token']}"}}


def _board_id(client) -> int:
    resp = client.get("/api/forum/boards")
    assert resp.status_code == 200, resp.text
    boards = resp.json()
    assert boards
    return boards[0]["id"]


def _create_thread(client, author: dict) -> dict:
    resp = client.post("/api/forum/threads", json={
        "board_id": _board_id(client),
        "title": f"Thread {uuid.uuid4().hex[:6]}",
        "body": "Opening post body",
    }, headers=author["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _op_id(thread: dict) -> int:
    return next(p["id"] for p in thread["posts"] if p["is_op"])


def _report(client, reporter: dict, post_id: int, reason: str = "spam"):
    return client.post(f"/api/forum/posts/{post_id}/report", json={"reason": reason}, headers=reporter["headers"])


def _thread_ids(client, board_id: int, headers=None) -> set[int]:
    resp = client.get(f"/api/forum/boards/{board_id}/threads", headers=headers or {})
    assert resp.status_code == 200, resp.text
    return {t["id"] for t in resp.json()}


def test_report_hides_post_for_reporter_only(client):
    author, reporter = _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)

    resp = _report(client, reporter, op_id)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "reported"}

    assert client.get(f"/api/forum/threads/{thread['id']}", headers=reporter["headers"]).status_code == 404
    assert thread["id"] not in _thread_ids(client, thread["board_id"], reporter["headers"])

    as_author = client.get(f"/api/forum/threads/{thread['id']}", headers=author["headers"])
    assert as_author.status_code == 200
    op = next(p for p in as_author.json()["posts"] if p["id"] == op_id)
    assert op["is_mine"] is True

    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 200

    with get_session() as session:
        assert session.query(ForumReport).filter(ForumReport.post_id == op_id).count() == 1


def test_report_is_idempotent(client):
    author, reporter = _new_user(client), _new_user(client)
    op_id = _op_id(_create_thread(client, author))

    assert _report(client, reporter, op_id).json() == {"status": "reported"}
    second = _report(client, reporter, op_id)
    assert second.status_code == 200
    assert second.json() == {"status": "already_reported"}

    with get_session() as session:
        assert session.query(ForumReport).filter(
            ForumReport.post_id == op_id, ForumReport.reporter_user_id == reporter["id"]
        ).count() == 1


def test_cannot_report_own_post(client):
    author = _new_user(client)
    op_id = _op_id(_create_thread(client, author))
    assert _report(client, author, op_id).status_code == 400


def test_report_unknown_post_is_404(client):
    reporter = _new_user(client)
    assert _report(client, reporter, 987654321).status_code == 404


def test_report_reason_validation(client):
    author, reporter = _new_user(client), _new_user(client)
    op_id = _op_id(_create_thread(client, author))
    assert _report(client, reporter, op_id, reason="i_dont_like_it").status_code == 422


def test_report_requires_auth(client):
    author = _new_user(client)
    op_id = _op_id(_create_thread(client, author))
    assert client.post(f"/api/forum/posts/{op_id}/report", json={"reason": "spam"}).status_code == 401


def test_block_author_filters_threads_and_posts(client):
    author, viewer, other = _new_user(client), _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)

    # A reply by the soon-to-be-blocked author inside someone else's thread.
    other_thread = _create_thread(client, other)
    reply = client.post(
        f"/api/forum/threads/{other_thread['id']}/posts", json={"body": "reply"}, headers=author["headers"]
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["is_mine"] is True

    resp = client.post(f"/api/forum/posts/{op_id}/block-author", headers=viewer["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "blocked"}

    assert thread["id"] not in _thread_ids(client, thread["board_id"], viewer["headers"])
    assert thread["id"] in _thread_ids(client, thread["board_id"])  # anonymous still sees it
    assert client.get(f"/api/forum/threads/{thread['id']}", headers=viewer["headers"]).status_code == 404

    detail = client.get(f"/api/forum/threads/{other_thread['id']}", headers=viewer["headers"]).json()
    assert reply.json()["id"] not in {p["id"] for p in detail["posts"]}

    # Blocking twice is idempotent.
    again = client.post(f"/api/forum/posts/{op_id}/block-author", headers=viewer["headers"])
    assert again.status_code == 200
    blocks = client.get("/api/forum/blocks", headers=viewer["headers"]).json()
    assert len(blocks) == 1


def test_cannot_block_self(client):
    author = _new_user(client)
    op_id = _op_id(_create_thread(client, author))
    resp = client.post(f"/api/forum/posts/{op_id}/block-author", headers=author["headers"])
    assert resp.status_code == 400


def test_unblock_restores(client):
    author, viewer, stranger = _new_user(client), _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    client.post(f"/api/forum/posts/{_op_id(thread)}/block-author", headers=viewer["headers"])

    blocks = client.get("/api/forum/blocks", headers=viewer["headers"]).json()
    assert len(blocks) == 1
    block_id = blocks[0]["block_id"]

    # Someone else cannot remove the viewer's block.
    assert client.delete(f"/api/forum/blocks/{block_id}", headers=stranger["headers"]).status_code == 404

    resp = client.delete(f"/api/forum/blocks/{block_id}", headers=viewer["headers"])
    assert resp.status_code == 200
    assert client.get("/api/forum/blocks", headers=viewer["headers"]).json() == []
    assert thread["id"] in _thread_ids(client, thread["board_id"], viewer["headers"])


def test_auto_hide_after_threshold(client):
    from services.forum_service import REPORT_AUTO_HIDE_THRESHOLD

    author = _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)

    for _ in range(REPORT_AUTO_HIDE_THRESHOLD):
        assert _report(client, _new_user(client), op_id).json() == {"status": "reported"}

    with get_session() as session:
        post = session.query(ForumPost).filter(ForumPost.id == op_id).first()
        assert post is not None
        assert post.moderation_action == "hidden"

    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 404
    assert thread["id"] not in _thread_ids(client, thread["board_id"])


def test_dismissing_reports_lifts_auto_hide(client, as_admin):
    from services.forum_service import REPORT_AUTO_HIDE_THRESHOLD

    author = _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)
    for _ in range(REPORT_AUTO_HIDE_THRESHOLD):
        _report(client, _new_user(client), op_id)
    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 404

    queue = client.get("/api/forum/admin/reports", headers=author["headers"]).json()
    report_ids = [row["report_id"] for row in queue if row["post_id"] == op_id]
    assert len(report_ids) == REPORT_AUTO_HIDE_THRESHOLD
    for report_id in report_ids:
        resp = client.post(
            f"/api/forum/admin/reports/{report_id}/resolve",
            json={"action": "dismiss"}, headers=author["headers"],
        )
        assert resp.status_code == 200, resp.text

    assert resp.json()["post_moderation_action"] == "allow"
    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 200


def test_dismiss_does_not_undo_moderator_hide(client, as_admin):
    author, reporter_a, reporter_b = _new_user(client), _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)
    _report(client, reporter_a, op_id)
    queue = client.get("/api/forum/admin/reports", headers=author["headers"]).json()
    first = next(row["report_id"] for row in queue if row["post_id"] == op_id)
    client.post(f"/api/forum/admin/reports/{first}/resolve", json={"action": "hide"}, headers=author["headers"])

    _report(client, reporter_b, op_id)
    queue = client.get("/api/forum/admin/reports", headers=author["headers"]).json()
    second = next(row["report_id"] for row in queue if row["post_id"] == op_id)
    resp = client.post(f"/api/forum/admin/reports/{second}/resolve", json={"action": "dismiss"}, headers=author["headers"])
    assert resp.json()["post_moderation_action"] == "hidden"
    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 404


def test_hide_on_dismissed_report_survives_later_dismissal(client, as_admin):
    author, reporter_a, reporter_b = _new_user(client), _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)
    _report(client, reporter_a, op_id)
    queue = client.get("/api/forum/admin/reports", headers=author["headers"]).json()
    first = next(row["report_id"] for row in queue if row["post_id"] == op_id)
    url = f"/api/forum/admin/reports/{first}/resolve"
    client.post(url, json={"action": "dismiss"}, headers=author["headers"])

    rehide = client.post(url, json={"action": "hide"}, headers=author["headers"])
    assert rehide.json()["status"] == "actioned"
    assert rehide.json()["post_moderation_action"] == "hidden"

    _report(client, reporter_b, op_id)
    queue = client.get("/api/forum/admin/reports", headers=author["headers"]).json()
    second = next(row["report_id"] for row in queue if row["post_id"] == op_id)
    resp = client.post(f"/api/forum/admin/reports/{second}/resolve", json={"action": "dismiss"}, headers=author["headers"])
    assert resp.json()["post_moderation_action"] == "hidden"
    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 404


def test_dismissing_actioned_report_keeps_hide(client, as_admin):
    author, reporter = _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    op_id = _op_id(thread)
    _report(client, reporter, op_id)
    queue = client.get("/api/forum/admin/reports", headers=author["headers"]).json()
    report_id = next(row["report_id"] for row in queue if row["post_id"] == op_id)
    url = f"/api/forum/admin/reports/{report_id}/resolve"
    client.post(url, json={"action": "hide"}, headers=author["headers"])

    resp = client.post(url, json={"action": "dismiss"}, headers=author["headers"])
    assert resp.json()["status"] == "actioned"
    assert resp.json()["post_moderation_action"] == "hidden"
    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 404


def test_below_threshold_stays_visible_to_others(client):
    author, reporter = _new_user(client), _new_user(client)
    thread = _create_thread(client, author)
    _report(client, reporter, _op_id(thread))
    assert client.get(f"/api/forum/threads/{thread['id']}").status_code == 200


def test_admin_routes_require_admin(client):
    user = _new_user(client)
    assert client.get("/api/forum/admin/reports", headers=user["headers"]).status_code == 403


def test_admin_resolve_hide_and_dismiss(client, as_admin):
    author, reporter_a, reporter_b = _new_user(client), _new_user(client), _new_user(client)
    hide_thread = _create_thread(client, author)
    dismiss_thread = _create_thread(client, author)
    hide_op, dismiss_op = _op_id(hide_thread), _op_id(dismiss_thread)

    _report(client, reporter_a, hide_op, reason="pump_and_dump")
    _report(client, reporter_b, hide_op, reason="misleading")
    _report(client, reporter_a, dismiss_op, reason="other")

    queue = client.get("/api/forum/admin/reports", headers=reporter_a["headers"])
    assert queue.status_code == 200, queue.text
    by_post: dict[int, list[dict]] = {}
    for row in queue.json():
        by_post.setdefault(row["post_id"], []).append(row)
    assert len(by_post[hide_op]) == 2
    assert len(by_post[dismiss_op]) == 1

    hide = client.post(
        f"/api/forum/admin/reports/{by_post[hide_op][0]['report_id']}/resolve",
        json={"action": "hide"}, headers=reporter_a["headers"],
    )
    assert hide.status_code == 200, hide.text
    assert hide.json()["status"] == "actioned"
    assert hide.json()["post_moderation_action"] == "hidden"
    assert client.get(f"/api/forum/threads/{hide_thread['id']}").status_code == 404

    dismiss = client.post(
        f"/api/forum/admin/reports/{by_post[dismiss_op][0]['report_id']}/resolve",
        json={"action": "dismiss"}, headers=reporter_a["headers"],
    )
    assert dismiss.status_code == 200, dismiss.text
    assert dismiss.json()["status"] == "dismissed"
    assert client.get(f"/api/forum/threads/{dismiss_thread['id']}").status_code == 200

    open_ids = {row["post_id"] for row in client.get("/api/forum/admin/reports", headers=reporter_a["headers"]).json()}
    assert hide_op not in open_ids
    assert dismiss_op not in open_ids

    missing = client.post("/api/forum/admin/reports/987654321/resolve", json={"action": "hide"}, headers=reporter_a["headers"])
    assert missing.status_code == 404
