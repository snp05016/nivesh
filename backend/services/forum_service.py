"""Community Forum service — business logic + repository access for message
boards, threads, posts, and polls.

Controller-Service-Repository: routers/forum.py must only validate HTTP
input and call functions here. All session.query() calls for the forum
ORM models live in this module.
"""
from typing import Optional

from sqlalchemy import case, distinct, func
from sqlalchemy.exc import IntegrityError

from database import get_session
from models.db_models import (
    ForumBoard,
    ForumPoll,
    ForumPollOption,
    ForumPost,
    ForumReport,
    ForumThread,
    ForumVote,
    User,
    UserBlock,
)
from services.forum_moderation_service import moderate_post

VOTE_DIRECTIONS = {"up", "down"}

# User reports (App Store 1.2 UGC controls).
REPORT_REASONS = {"spam", "abuse", "misleading", "pump_and_dump", "other"}
# Distinct open reports from different users that hide a post for everyone
# until a moderator resolves it.
REPORT_AUTO_HIDE_THRESHOLD = 3
REPORT_RESOLVE_ACTIONS = {"hide", "dismiss"}
HIDDEN = "hidden"


# ---------------------------------------------------------------------------
# Seed boards — structural categories so the Forum Hub has somewhere to post.
# Seeded at startup (main._seed_catalogs). No seed threads or posts: content
# must never be attributed to a real user who did not write it.
# ---------------------------------------------------------------------------
_MOCK_BOARDS = [
    {
        "slug": "general-market",
        "name": "General Market",
        "description": "Broad market moves, macro news, and off-topic trading chatter.",
        "board_type": "general",
        "ticker": None,
    },
    {
        "slug": "ipo-buzz",
        "name": "IPO Buzz",
        "description": "GMP talk, subscription numbers, and listing-day discussion.",
        "board_type": "general",
        "ticker": None,
    },
    {
        "slug": "stock-reliance",
        "name": "Reliance Industries",
        "description": "All things RELIANCE — earnings, targets, and technicals.",
        "board_type": "stock",
        "ticker": "RELIANCE",
    },
]


def seed_mock_boards_if_empty() -> int:
    """Populate forum_boards when the table is empty. Returns boards inserted."""
    with get_session() as session:
        existing = session.query(ForumBoard).count()
        if existing > 0:
            return 0

        boards = []
        for row in _MOCK_BOARDS:
            board = ForumBoard(
                slug=row["slug"],
                name=row["name"],
                description=row["description"],
                board_type=row["board_type"],
                ticker=row["ticker"],
            )
            session.add(board)
            boards.append(board)
        session.commit()
        return len(boards)


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------

def list_boards() -> list[ForumBoard]:
    with get_session() as session:
        return session.query(ForumBoard).order_by(ForumBoard.id.asc()).all()


def get_board_by_id(board_id: int) -> Optional[ForumBoard]:
    with get_session() as session:
        return session.query(ForumBoard).filter(ForumBoard.id == board_id).first()


def thread_count_for_board(board_id: int) -> int:
    with get_session() as session:
        return session.query(ForumThread).filter(ForumThread.board_id == board_id).count()


# ---------------------------------------------------------------------------
# Viewer filtering (blocks, own reports, moderator/auto hides)
# ---------------------------------------------------------------------------

def _viewer_filters(session, viewer_id: Optional[int]) -> tuple[set[int], set[int]]:
    """(user ids the viewer blocked, post ids the viewer reported)."""
    if viewer_id is None:
        return set(), set()
    blocked = {
        row[0]
        for row in session.query(UserBlock.blocked_user_id)
        .filter(UserBlock.blocker_user_id == viewer_id)
        .all()
    }
    reported = {
        row[0]
        for row in session.query(ForumReport.post_id)
        .filter(ForumReport.reporter_user_id == viewer_id)
        .all()
    }
    return blocked, reported


def _is_visible(post: ForumPost, viewer_id: Optional[int], blocked: set[int], reported: set[int]) -> bool:
    """Authors always see their own posts; everyone else loses hidden posts,
    posts by users they blocked, and posts they reported."""
    if viewer_id is not None and post.user_id == viewer_id:
        return True
    return (
        post.moderation_action != HIDDEN
        and post.user_id not in blocked
        and post.id not in reported
    )


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def list_threads(board_id: int, viewer_id: Optional[int] = None) -> list[dict]:
    """List thread summaries for a board (title, author, reply/vote counts),
    minus threads the viewer blocked/reported or moderators hid."""
    with get_session() as session:
        blocked, reported = _viewer_filters(session, viewer_id)
        threads = (
            session.query(ForumThread)
            .filter(ForumThread.board_id == board_id)
            .order_by(ForumThread.is_pinned.desc(), ForumThread.created_at.desc())
            .all()
        )
        results = []
        for thread in threads:
            posts = (
                session.query(ForumPost)
                .filter(ForumPost.thread_id == thread.id)
                .order_by(ForumPost.created_at.asc())
                .all()
            )
            op_post = next((p for p in posts if p.is_op), posts[0] if posts else None)
            if thread.user_id in blocked:
                continue
            if op_post is not None and not _is_visible(op_post, viewer_id, blocked, reported):
                continue
            posts = [p for p in posts if _is_visible(p, viewer_id, blocked, reported)]
            author = session.query(User).filter(User.id == thread.user_id).first()
            has_poll = session.query(ForumPoll).filter(ForumPoll.thread_id == thread.id).first() is not None
            results.append({
                "id": thread.id,
                "board_id": thread.board_id,
                "title": thread.title,
                "author_display_name": author.display_name if author else "Unknown",
                "is_pinned": thread.is_pinned,
                "reply_count": max(len(posts) - 1, 0),
                "upvotes": op_post.upvotes if op_post else 0,
                "downvotes": op_post.downvotes if op_post else 0,
                "has_poll": has_poll,
                "created_at": thread.created_at.isoformat() if thread.created_at else None,
                "op_post_id": op_post.id if op_post else None,
                "is_mine": viewer_id is not None and thread.user_id == viewer_id,
            })
        return results


def get_thread_detail(thread_id: int, viewer_id: Optional[int] = None) -> Optional[dict]:
    """Full thread payload: thread meta, visible posts (with author + vote counts), and poll if any.

    Returns None when the thread itself is hidden from this viewer (author
    blocked, opening post reported by the viewer or hidden by moderation).
    """
    with get_session() as session:
        thread = session.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if thread is None:
            return None
        blocked, reported = _viewer_filters(session, viewer_id)
        if thread.user_id in blocked:
            return None

        board = session.query(ForumBoard).filter(ForumBoard.id == thread.board_id).first()
        author = session.query(User).filter(User.id == thread.user_id).first()

        posts = (
            session.query(ForumPost)
            .filter(ForumPost.thread_id == thread_id)
            .order_by(ForumPost.created_at.asc())
            .all()
        )
        op_post = next((p for p in posts if p.is_op), None)
        if op_post is not None and not _is_visible(op_post, viewer_id, blocked, reported):
            return None
        post_payloads = []
        for post in posts:
            if not _is_visible(post, viewer_id, blocked, reported):
                continue
            post_author = session.query(User).filter(User.id == post.user_id).first()
            post_payloads.append({
                "id": post.id,
                "thread_id": post.thread_id,
                "parent_post_id": post.parent_post_id,
                "body": post.body,
                "is_op": post.is_op,
                "author_display_name": post_author.display_name if post_author else "Unknown",
                "upvotes": post.upvotes,
                "downvotes": post.downvotes,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "is_mine": viewer_id is not None and post.user_id == viewer_id,
            })

        poll_payload = None
        poll = session.query(ForumPoll).filter(ForumPoll.thread_id == thread_id).first()
        if poll is not None:
            options = (
                session.query(ForumPollOption)
                .filter(ForumPollOption.poll_id == poll.id)
                .order_by(ForumPollOption.id.asc())
                .all()
            )
            total_votes = sum(o.vote_count for o in options)
            poll_payload = {
                "id": poll.id,
                "thread_id": poll.thread_id,
                "question": poll.question,
                "total_votes": total_votes,
                "options": [
                    {"id": o.id, "option_text": o.option_text, "vote_count": o.vote_count}
                    for o in options
                ],
            }

        return {
            "id": thread.id,
            "board_id": thread.board_id,
            "board_name": board.name if board else None,
            "title": thread.title,
            "author_display_name": author.display_name if author else "Unknown",
            "is_pinned": thread.is_pinned,
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
            "posts": post_payloads,
            "poll": poll_payload,
        }


def create_thread(
    user_id: int,
    board_id: int,
    title: str,
    body: str,
    poll_question: Optional[str] = None,
    poll_options: Optional[list[str]] = None,
) -> Optional[dict]:
    """Create a thread + its OP post (+ optional poll). Returns the thread detail payload."""
    body = body.strip()
    verdict = moderate_post(body)
    if verdict["action"] == "block":
        return {"blocked": True, "reason": "spam_detected"}

    with get_session() as session:
        board = session.query(ForumBoard).filter(ForumBoard.id == board_id).first()
        if board is None:
            return None

        thread = ForumThread(board_id=board_id, user_id=user_id, title=title.strip())
        session.add(thread)
        session.flush()

        op_post = ForumPost(
            thread_id=thread.id,
            user_id=user_id,
            body=body,
            is_op=True,
            moderation_action=verdict["action"],
            spam_score=verdict["spam_score"],
            sentiment=verdict["sentiment"],
        )
        session.add(op_post)

        if poll_question and poll_options:
            cleaned_options = [o.strip() for o in poll_options if o and o.strip()]
            if len(cleaned_options) >= 2:
                poll = ForumPoll(thread_id=thread.id, question=poll_question.strip())
                session.add(poll)
                session.flush()
                for option_text in cleaned_options:
                    session.add(ForumPollOption(poll_id=poll.id, option_text=option_text))

        session.commit()
        thread_id = thread.id

    return get_thread_detail(thread_id, viewer_id=user_id)


# ---------------------------------------------------------------------------
# Posts (replies)
# ---------------------------------------------------------------------------

def create_post(user_id: int, thread_id: int, body: str, parent_post_id: Optional[int] = None) -> Optional[dict]:
    with get_session() as session:
        thread = session.query(ForumThread).filter(ForumThread.id == thread_id).first()
        if thread is None:
            return None
        if parent_post_id is not None:
            parent = session.query(ForumPost).filter(
                ForumPost.id == parent_post_id, ForumPost.thread_id == thread_id
            ).first()
            if parent is None:
                return None

        body = body.strip()
        verdict = moderate_post(body)
        if verdict["action"] == "block":
            return {"blocked": True, "reason": "spam_detected"}

        post = ForumPost(
            thread_id=thread_id,
            user_id=user_id,
            parent_post_id=parent_post_id,
            body=body,
            is_op=False,
            moderation_action=verdict["action"],
            spam_score=verdict["spam_score"],
            sentiment=verdict["sentiment"],
        )
        session.add(post)
        session.commit()

        author = session.query(User).filter(User.id == user_id).first()
        return {
            "id": post.id,
            "thread_id": post.thread_id,
            "parent_post_id": post.parent_post_id,
            "body": post.body,
            "is_op": post.is_op,
            "author_display_name": author.display_name if author else "Unknown",
            "upvotes": post.upvotes,
            "downvotes": post.downvotes,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "is_mine": True,
        }


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

def _bump(session, model, row_id: Optional[int], column, delta: int) -> None:
    """Atomic ``column = MAX(column + delta, 0)`` in SQL, so concurrent votes
    never overwrite each other's counter changes (no ORM read-modify-write).
    """
    session.query(model).filter(model.id == row_id).update(
        {column: case((column + delta < 0, 0), else_=column + delta)},
        synchronize_session=False,
    )


def vote_post(user_id: int, post_id: int, direction: str) -> Optional[dict]:
    """Toggle-aware upvote/downvote on a post. Re-voting the same direction
    removes the vote; voting the opposite direction switches it.

    Counters only move when the matching ForumVote write actually changed a
    row, so a double-submitted tap is idempotent instead of drifting or 500ing.
    """
    if direction not in VOTE_DIRECTIONS:
        raise ValueError(f"Invalid direction '{direction}'. Must be one of {sorted(VOTE_DIRECTIONS)}")

    with get_session() as session:
        post = session.query(ForumPost).filter(ForumPost.id == post_id).first()
        if post is None:
            return None

        new_value = 1 if direction == "up" else -1
        existing_vote = (
            session.query(ForumVote)
            .filter(ForumVote.user_id == user_id, ForumVote.post_id == post_id)
            .first()
        )

        def _col(value: int):
            return ForumPost.upvotes if value == 1 else ForumPost.downvotes

        try:
            if existing_vote is None:
                session.add(ForumVote(user_id=user_id, post_id=post_id, vote_value=new_value))
                session.flush()  # raises IntegrityError on a concurrent duplicate before we count it
                _bump(session, ForumPost, post_id, _col(new_value), 1)
                user_vote = new_value
            elif existing_vote.vote_value == new_value:
                # Same direction again — remove the vote (toggle off).
                removed = (
                    session.query(ForumVote)
                    .filter(ForumVote.id == existing_vote.id)
                    .delete(synchronize_session=False)
                )
                if removed:
                    _bump(session, ForumPost, post_id, _col(new_value), -1)
                user_vote = 0
            else:
                # Switching direction.
                switched = (
                    session.query(ForumVote)
                    .filter(ForumVote.id == existing_vote.id, ForumVote.vote_value == existing_vote.vote_value)
                    .update({ForumVote.vote_value: new_value}, synchronize_session=False)
                )
                if switched:
                    _bump(session, ForumPost, post_id, _col(existing_vote.vote_value), -1)
                    _bump(session, ForumPost, post_id, _col(new_value), 1)
                user_vote = new_value
            session.commit()
        except IntegrityError:
            # A duplicate request already inserted (and counted) this vote.
            session.rollback()
            current = (
                session.query(ForumVote)
                .filter(ForumVote.user_id == user_id, ForumVote.post_id == post_id)
                .first()
            )
            user_vote = current.vote_value if current else 0

        session.refresh(post)  # counters were changed in SQL, not on the instance
        return {
            "post_id": post.id,
            "upvotes": post.upvotes,
            "downvotes": post.downvotes,
            "user_vote": user_vote,
        }


def vote_poll(user_id: int, poll_id: int, option_id: int) -> Optional[dict]:
    """Cast (or move) a user's single vote on a poll."""
    with get_session() as session:
        poll = session.query(ForumPoll).filter(ForumPoll.id == poll_id).first()
        if poll is None:
            return None
        option = session.query(ForumPollOption).filter(
            ForumPollOption.id == option_id, ForumPollOption.poll_id == poll_id
        ).first()
        if option is None:
            return None

        existing_vote = (
            session.query(ForumVote)
            .filter(ForumVote.user_id == user_id, ForumVote.poll_id == poll_id)
            .first()
        )

        try:
            if existing_vote is None:
                session.add(ForumVote(user_id=user_id, poll_id=poll_id, poll_option_id=option_id, vote_value=1))
                session.flush()  # raises IntegrityError on a concurrent duplicate before we count it
                _bump(session, ForumPollOption, option_id, ForumPollOption.vote_count, 1)
            elif existing_vote.poll_option_id == option_id:
                # Re-voting the same option — no-op (idempotent).
                pass
            else:
                previous_option_id = existing_vote.poll_option_id
                moved = (
                    session.query(ForumVote)
                    .filter(ForumVote.id == existing_vote.id, ForumVote.poll_option_id == previous_option_id)
                    .update({ForumVote.poll_option_id: option_id}, synchronize_session=False)
                )
                if moved:
                    _bump(session, ForumPollOption, previous_option_id, ForumPollOption.vote_count, -1)
                    _bump(session, ForumPollOption, option_id, ForumPollOption.vote_count, 1)
            session.commit()
        except IntegrityError:
            # A duplicate request already inserted (and counted) this vote.
            session.rollback()

        options = (
            session.query(ForumPollOption)
            .filter(ForumPollOption.poll_id == poll_id)
            .order_by(ForumPollOption.id.asc())
            .all()
        )
        total_votes = sum(o.vote_count for o in options)
        return {
            "id": poll.id,
            "thread_id": poll.thread_id,
            "question": poll.question,
            "total_votes": total_votes,
            "options": [
                {"id": o.id, "option_text": o.option_text, "vote_count": o.vote_count}
                for o in options
            ],
        }


# ---------------------------------------------------------------------------
# Reports + blocks (App Store 1.2 UGC controls)
# ---------------------------------------------------------------------------

def report_post(reporter_id: int, post_id: int, reason: str, details: Optional[str] = None) -> Optional[dict]:
    """Record a report against a post. The reporter stops seeing it at once;
    REPORT_AUTO_HIDE_THRESHOLD distinct open reports hide it for everyone.

    Returns None if the post does not exist. Raises ValueError("own_post")
    when reporting your own post, ValueError("invalid_reason") on a bad reason.
    """
    if reason not in REPORT_REASONS:
        raise ValueError("invalid_reason")
    with get_session() as session:
        post = session.query(ForumPost).filter(ForumPost.id == post_id).first()
        if post is None:
            return None
        if post.user_id == reporter_id:
            raise ValueError("own_post")

        session.add(ForumReport(
            reporter_user_id=reporter_id,
            post_id=post_id,
            reason=reason,
            details=(details or "").strip() or None,
        ))
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            return {"status": "already_reported"}

        open_reporters = (
            session.query(func.count(distinct(ForumReport.reporter_user_id)))
            .filter(ForumReport.post_id == post_id, ForumReport.status == "open")
            .scalar()
        ) or 0
        if open_reporters >= REPORT_AUTO_HIDE_THRESHOLD:
            post.moderation_action = HIDDEN
        session.commit()
        return {"status": "reported"}


def block_post_author(blocker_id: int, post_id: int) -> Optional[dict]:
    """Block the author of `post_id`. Idempotent.

    Returns None if the post does not exist. Raises ValueError("self_block")
    when the post is the blocker's own.
    """
    with get_session() as session:
        post = session.query(ForumPost).filter(ForumPost.id == post_id).first()
        if post is None:
            return None
        if post.user_id == blocker_id:
            raise ValueError("self_block")
        session.add(UserBlock(blocker_user_id=blocker_id, blocked_user_id=post.user_id))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()  # already blocked
        return {"status": "blocked"}


def list_blocks(blocker_id: int) -> list[dict]:
    """Users the blocker has blocked, newest first."""
    with get_session() as session:
        rows = (
            session.query(UserBlock, User)
            .join(User, User.id == UserBlock.blocked_user_id)
            .filter(UserBlock.blocker_user_id == blocker_id)
            .order_by(UserBlock.id.desc())
            .all()
        )
        return [{"block_id": block.id, "display_name": user.display_name} for block, user in rows]


def unblock(blocker_id: int, block_id: int) -> bool:
    """Remove one of the blocker's own blocks. False if it does not exist."""
    with get_session() as session:
        deleted = (
            session.query(UserBlock)
            .filter(UserBlock.id == block_id, UserBlock.blocker_user_id == blocker_id)
            .delete()
        )
        session.commit()
        return deleted > 0


def _report_payload(report: ForumReport, post: Optional[ForumPost]) -> dict:
    return {
        "report_id": report.id,
        "post_id": report.post_id,
        "thread_id": post.thread_id if post else None,
        "post_author_user_id": post.user_id if post else None,
        "post_body": post.body if post else None,
        "post_moderation_action": post.moderation_action if post else None,
        "reporter_user_id": report.reporter_user_id,
        "reason": report.reason,
        "details": report.details,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def list_reports(status: str = "open") -> list[dict]:
    """Moderation queue: reports with the given status, oldest first."""
    with get_session() as session:
        rows = (
            session.query(ForumReport, ForumPost)
            .outerjoin(ForumPost, ForumPost.id == ForumReport.post_id)
            .filter(ForumReport.status == status)
            .order_by(ForumReport.created_at.asc(), ForumReport.id.asc())
            .all()
        )
        return [_report_payload(report, post) for report, post in rows]


def resolve_report(report_id: int, action: str) -> Optional[dict]:
    """Moderator decision. "hide" hides the post for everyone and closes every
    open report on it (and this report) as actioned; "dismiss" closes only an
    open report and lifts an auto-hide once open reporters fall below the
    threshold. Actioned reports are never dismissed, so a moderator "hide" is
    never undone.
    Returns None if the report does not exist.
    """
    if action not in REPORT_RESOLVE_ACTIONS:
        raise ValueError("invalid_action")
    with get_session() as session:
        report = session.query(ForumReport).filter(ForumReport.id == report_id).first()
        if report is None:
            return None
        post = session.query(ForumPost).filter(ForumPost.id == report.post_id).first()
        if action == "hide":
            if post is not None:
                post.moderation_action = HIDDEN
            (
                session.query(ForumReport)
                .filter(ForumReport.post_id == report.post_id, ForumReport.status == "open")
                .update({ForumReport.status: "actioned"}, synchronize_session="fetch")
            )
            # Always leave an "actioned" marker, even when re-resolving a
            # dismissed report, so a later dismissal cannot lift this hide.
            report.status = "actioned"
        elif report.status == "open":
            # Only open reports can be dismissed; an "actioned" report records a
            # moderator hide and must not be silently reversed.
            report.status = "dismissed"
            session.flush()
            # Undo an auto-hide once the dismissals drop it below the threshold,
            # unless a moderator chose "hide" for this post at some point.
            if post is not None and post.moderation_action == HIDDEN:
                actioned = (
                    session.query(ForumReport.id)
                    .filter(ForumReport.post_id == post.id, ForumReport.status == "actioned")
                    .first()
                )
                open_reporters = (
                    session.query(func.count(distinct(ForumReport.reporter_user_id)))
                    .filter(ForumReport.post_id == post.id, ForumReport.status == "open")
                    .scalar()
                ) or 0
                if actioned is None and open_reporters < REPORT_AUTO_HIDE_THRESHOLD:
                    # ponytail: restores "allow" even if the filter had said "flag";
                    # keep a pre-hide column if the flag verdict ever matters.
                    post.moderation_action = "allow"
        session.commit()
        session.refresh(report)
        return _report_payload(report, post)
