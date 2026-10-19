"""GH-679: forum read paths run a fixed number of queries (no N+1).

Rows are inserted directly through database.get_session (no create_thread, so
FinBERT/moderation never loads). Uses the conftest sqlite test DB and stub
users 990001 / 990002.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

import database
from database import get_session
from models.db_models import ForumBoard, ForumPoll, ForumPost, ForumThread  # pyright: ignore[reportMissingImports]
from services import feature_flags
from services.forum_service import get_thread_detail, list_threads, thread_counts_by_board

_USERS = (990001, 990002)
_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _focus_flags_on(monkeypatch):
    """I04: the forum and IPO hub are off by default; these tests exercise them."""
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    monkeypatch.setenv("NIVESH_FLAG_IPO_HUB", "true")
    feature_flags._reset_cache()
    yield
    feature_flags._reset_cache()


@contextmanager
def _count_selects():
    counter = {"n": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    event.listen(database.ENGINE, "before_cursor_execute", _before)
    try:
        yield counter
    finally:
        event.remove(database.ENGINE, "before_cursor_execute", _before)


def _make_board(n_threads: int, replies: int = 2) -> int:
    """Board with n_threads threads (thread i by _USERS[i % 2]); each has an OP
    plus `replies` replies; even-numbered threads carry a poll."""
    with get_session() as session:
        board = ForumBoard(slug=f"gh679-{uuid.uuid4().hex[:10]}", name="GH-679 board", board_type="general")
        session.add(board)
        session.flush()
        for i in range(n_threads):
            created = _BASE_TIME + timedelta(minutes=i)
            thread = ForumThread(
                board_id=board.id, user_id=_USERS[i % 2], title=f"t{i}", created_at=created
            )
            session.add(thread)
            session.flush()
            session.add(ForumPost(thread_id=thread.id, user_id=thread.user_id, body="op", is_op=True,
                                  created_at=created))
            for r in range(replies):
                session.add(ForumPost(thread_id=thread.id, user_id=_USERS[(i + r + 1) % 2], body="re",
                                      is_op=False, created_at=created + timedelta(seconds=r + 1)))
            if i % 2 == 0:
                session.add(ForumPoll(thread_id=thread.id, question="q?"))
        session.commit()
        return int(board.id)  # type: ignore[arg-type]


def _drop_board(board_id: int) -> None:
    with get_session() as session:
        thread_ids = [t.id for t in session.query(ForumThread.id).filter(ForumThread.board_id == board_id)]
        if thread_ids:
            session.query(ForumPoll).filter(ForumPoll.thread_id.in_(thread_ids)).delete(synchronize_session=False)
            session.query(ForumPost).filter(ForumPost.thread_id.in_(thread_ids)).delete(synchronize_session=False)
            session.query(ForumThread).filter(ForumThread.id.in_(thread_ids)).delete(synchronize_session=False)
        session.query(ForumBoard).filter(ForumBoard.id == board_id).delete(synchronize_session=False)
        session.commit()


@pytest.fixture
def boards():
    created = []

    def _factory(n_threads: int, replies: int = 2) -> int:
        board_id = _make_board(n_threads, replies)
        created.append(board_id)
        return board_id

    yield _factory
    for board_id in created:
        _drop_board(board_id)


def test_list_threads_query_count_constant(boards):
    small, large = boards(3), boards(10)

    with _count_selects() as c_small:
        small_rows = list_threads(small, viewer_id=_USERS[0])
    with _count_selects() as c_large:
        large_rows = list_threads(large, viewer_id=_USERS[0])

    assert len(small_rows) == 3 and len(large_rows) == 10
    assert c_small["n"] == c_large["n"]
    assert c_large["n"] <= 6

    by_title = {r["title"]: r for r in large_rows}
    assert all(r["reply_count"] == 2 for r in large_rows)
    assert by_title["t0"]["has_poll"] is True and by_title["t1"]["has_poll"] is False
    assert by_title["t0"]["author_display_name"] == "Test Stub 990001"
    assert by_title["t1"]["author_display_name"] == "Test Stub 990002"
    assert by_title["t0"]["is_mine"] is True and by_title["t1"]["is_mine"] is False


def test_list_threads_pagination(boards):
    board_id = boards(5)
    page = list_threads(board_id, limit=2, offset=2)
    # Newest first: t4, t3 | t2, t1 | t0
    assert [r["title"] for r in page] == ["t2", "t1"]


def test_thread_detail_single_user_query(boards):
    board_id = boards(1, replies=9)  # 10 posts by 2 users
    with get_session() as session:
        thread_id = session.query(ForumThread.id).filter(ForumThread.board_id == board_id).scalar()

    with _count_selects() as counter:
        detail = get_thread_detail(thread_id)

    assert detail is not None
    assert len(detail["posts"]) == 10
    assert {p["author_display_name"] for p in detail["posts"]} == {"Test Stub 990001", "Test Stub 990002"}
    assert counter["n"] <= 6


def test_boards_thread_counts(client, boards):
    a, b = boards(3), boards(1)
    counts = thread_counts_by_board()
    assert counts[a] == 3 and counts[b] == 1

    resp = client.get("/api/forum/boards")
    assert resp.status_code == 200, resp.text
    by_id = {row["id"]: row["thread_count"] for row in resp.json()}
    assert by_id[a] == 3 and by_id[b] == 1
