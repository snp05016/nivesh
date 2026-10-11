"""DB-34: forum vote counters must stay equal to COUNT(forum_votes) — updated
with atomic SQL, never lost to a stale ORM read, and a double-submitted vote
must be idempotent instead of surfacing the unique-constraint IntegrityError.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# conftest.py patches heavy modules before any app import — rely on that here.
from models.db_models import (
    Base,
    ForumBoard,
    ForumPoll,
    ForumPollOption,
    ForumPost,
    ForumThread,
    ForumVote,
    User,
)
from services import forum_service


class _NoVoteQuery:
    """Stands in for the existing-vote lookup and reports "no vote yet"."""

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


@pytest.fixture()
def forum(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    hooks = {}

    class HookedSession(Session):
        """Runs hooks["vote_lookup"] once, on the first ForumVote query (the
        existing-vote lookup), to simulate a concurrent request at that point."""

        def query(self, *entities, **kwargs):
            if entities and entities[0] is ForumVote:
                hook = hooks.pop("vote_lookup", None)
                if hook is not None:
                    replacement = hook(self)
                    if replacement is not None:
                        return replacement
            return super().query(*entities, **kwargs)

    TestSession = sessionmaker(bind=engine, class_=HookedSession, autoflush=False)

    @contextmanager
    def fake_get_session():
        session = TestSession()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(forum_service, "get_session", fake_get_session)

    with TestSession() as s:
        users = [User(username=f"u{i}", password_hash="x", display_name=f"U{i}") for i in range(3)]
        s.add_all(users)
        s.flush()
        board = ForumBoard(slug="general", name="General")
        s.add(board)
        s.flush()
        thread = ForumThread(board_id=board.id, user_id=users[0].id, title="T")
        s.add(thread)
        s.flush()
        post = ForumPost(thread_id=thread.id, user_id=users[0].id, body="hello", is_op=True)
        poll = ForumPoll(thread_id=thread.id, question="Q?")
        s.add_all([post, poll])
        s.flush()
        opts = [ForumPollOption(poll_id=poll.id, option_text=t) for t in ("A", "B")]
        s.add_all(opts)
        s.commit()
        ids = {
            "users": [u.id for u in users],
            "post": post.id,
            "poll": poll.id,
            "opts": [o.id for o in opts],
        }

    yield TestSession, hooks, ids
    engine.dispose()


def _post_counts(TestSession, post_id):
    with TestSession() as s:
        post = s.get(ForumPost, post_id)
        ups = s.query(ForumVote).filter(ForumVote.post_id == post_id, ForumVote.vote_value == 1).count()
        downs = s.query(ForumVote).filter(ForumVote.post_id == post_id, ForumVote.vote_value == -1).count()
        return post.upvotes, post.downvotes, ups, downs


def _option_counts(TestSession, option_ids):
    with TestSession() as s:
        return [
            (
                s.get(ForumPollOption, oid).vote_count,
                s.query(ForumVote).filter(ForumVote.poll_option_id == oid).count(),
            )
            for oid in option_ids
        ]


def test_post_counters_match_vote_rows_through_toggle_and_switch(forum):
    TestSession, _, ids = forum
    u1, u2, u3 = ids["users"]
    post_id = ids["post"]

    steps = [
        (u1, "up", 1),
        (u2, "up", 1),
        (u3, "down", -1),
        (u1, "up", 0),     # toggle off
        (u2, "down", -1),  # switch
    ]
    for user_id, direction, expected_user_vote in steps:
        result = forum_service.vote_post(user_id, post_id, direction)
        assert result is not None
        assert result["user_vote"] == expected_user_vote
        upvotes, downvotes, ups, downs = _post_counts(TestSession, post_id)
        assert (upvotes, downvotes) == (ups, downs)
        assert (result["upvotes"], result["downvotes"]) == (upvotes, downvotes)

    assert _post_counts(TestSession, post_id) == (0, 2, 0, 2)


def test_poll_counters_match_vote_rows_when_moving_vote(forum):
    TestSession, _, ids = forum
    u1 = ids["users"][0]
    opt_a, opt_b = ids["opts"]

    forum_service.vote_poll(u1, ids["poll"], opt_a)
    assert _option_counts(TestSession, [opt_a, opt_b]) == [(1, 1), (0, 0)]

    result = forum_service.vote_poll(u1, ids["poll"], opt_b)
    assert _option_counts(TestSession, [opt_a, opt_b]) == [(0, 0), (1, 1)]
    assert result is not None
    assert result["total_votes"] == 1
    assert [o["vote_count"] for o in result["options"]] == [0, 1]


def test_vote_increments_in_sql_instead_of_overwriting_stale_value(forum):
    """Another request bumps upvotes after this request loaded the post; the
    old `post.upvotes += 1` wrote back the stale value (0 + 1) and lost it."""
    TestSession, hooks, ids = forum
    post_id = ids["post"]

    def concurrent_bump(session):
        session.execute(
            text("UPDATE forum_posts SET upvotes = upvotes + 5 WHERE id = :id"), {"id": post_id}
        )

    hooks["vote_lookup"] = concurrent_bump
    result = forum_service.vote_post(ids["users"][0], post_id, "up")

    assert result is not None
    assert result["upvotes"] == 6
    assert _post_counts(TestSession, post_id)[0] == 6


def test_duplicate_post_vote_is_idempotent_not_integrity_error(forum):
    TestSession, hooks, ids = forum
    u1 = ids["users"][0]
    post_id = ids["post"]
    forum_service.vote_post(u1, post_id, "up")

    # The duplicate tap misses the existing row in its lookup (lost race).
    hooks["vote_lookup"] = lambda session: _NoVoteQuery()
    result = forum_service.vote_post(u1, post_id, "up")

    assert result == {"post_id": post_id, "upvotes": 1, "downvotes": 0, "user_vote": 1}
    assert _post_counts(TestSession, post_id) == (1, 0, 1, 0)


def test_duplicate_poll_vote_is_idempotent_not_integrity_error(forum):
    TestSession, hooks, ids = forum
    u1 = ids["users"][0]
    opt_a, opt_b = ids["opts"]
    forum_service.vote_poll(u1, ids["poll"], opt_a)

    hooks["vote_lookup"] = lambda session: _NoVoteQuery()
    result = forum_service.vote_poll(u1, ids["poll"], opt_a)

    assert result is not None
    assert result["total_votes"] == 1
    assert _option_counts(TestSession, [opt_a, opt_b]) == [(1, 1), (0, 0)]
