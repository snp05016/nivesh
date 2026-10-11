"""Community Forum API — boards, threads, posts, polls, votes.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/forum_service.py (Controller-Service-Repository).
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.security import get_current_user_id, require_admin, require_auth
from services.forum_service import (
    block_post_author,
    create_post,
    create_thread,
    get_board_by_id,
    get_thread_detail,
    list_blocks,
    list_boards,
    list_reports,
    list_threads,
    report_post,
    resolve_report,
    seed_mock_boards_if_empty,
    thread_count_for_board,
    unblock,
    vote_poll,
    vote_post,
)

router = APIRouter(prefix="/api/forum", tags=["Forum"])


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------

class ForumBoardResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    board_type: str
    ticker: Optional[str] = None
    thread_count: int = 0

    class Config:
        from_attributes = True


class ForumThreadSummaryResponse(BaseModel):
    id: int
    board_id: int
    title: str
    author_display_name: str
    is_pinned: bool
    reply_count: int
    upvotes: int
    downvotes: int
    has_poll: bool
    created_at: Optional[str] = None
    op_post_id: Optional[int] = None
    is_mine: bool = False


class ForumPostResponse(BaseModel):
    id: int
    thread_id: int
    parent_post_id: Optional[int] = None
    body: str
    is_op: bool
    author_display_name: str
    upvotes: int
    downvotes: int
    created_at: Optional[str] = None
    is_mine: bool = False


class ForumPollOptionResponse(BaseModel):
    id: int
    option_text: str
    vote_count: int


class ForumPollResponse(BaseModel):
    id: int
    thread_id: int
    question: str
    total_votes: int
    options: List[ForumPollOptionResponse]


class ForumThreadDetailResponse(BaseModel):
    id: int
    board_id: int
    board_name: Optional[str] = None
    title: str
    author_display_name: str
    is_pinned: bool
    created_at: Optional[str] = None
    posts: List[ForumPostResponse]
    poll: Optional[ForumPollResponse] = None


class CreateThreadRequest(BaseModel):
    board_id: int
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=1)
    poll_question: Optional[str] = Field(None, max_length=300)
    poll_options: Optional[List[str]] = None


class CreatePostRequest(BaseModel):
    body: str = Field(..., min_length=1)
    parent_post_id: Optional[int] = None


class VotePostRequest(BaseModel):
    direction: str = Field(..., description="'up' or 'down'")


class VotePostResponse(BaseModel):
    post_id: int
    upvotes: int
    downvotes: int
    user_vote: int


class VotePollRequest(BaseModel):
    option_id: int


class ReportPostRequest(BaseModel):
    reason: Literal["spam", "abuse", "misleading", "pump_and_dump", "other"]
    details: Optional[str] = Field(None, max_length=500)


class ModerationStatusResponse(BaseModel):
    status: str


class ForumBlockResponse(BaseModel):
    block_id: int
    display_name: str


class ForumReportAdminResponse(BaseModel):
    report_id: int
    post_id: int
    thread_id: Optional[int] = None
    post_author_user_id: Optional[int] = None
    post_body: Optional[str] = None
    post_moderation_action: Optional[str] = None
    reporter_user_id: int
    reason: str
    details: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class ResolveReportRequest(BaseModel):
    action: Literal["hide", "dismiss"]


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------

@router.get("/boards", response_model=List[ForumBoardResponse])
def list_forum_boards():
    """List discussion boards (general market boards + per-stock boards)."""
    seed_mock_boards_if_empty()  # mock data bootstrap — no-op once table is populated
    boards = list_boards()
    return [
        ForumBoardResponse(
            id=b.id,
            slug=b.slug,
            name=b.name,
            description=b.description,
            board_type=b.board_type,
            ticker=b.ticker,
            thread_count=thread_count_for_board(b.id),
        )
        for b in boards
    ]


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

@router.get("/boards/{board_id}/threads", response_model=List[ForumThreadSummaryResponse])
def list_board_threads(board_id: int, viewer_id: Optional[int] = Depends(get_current_user_id)):
    """List thread summaries for a board. Public; a signed-in viewer's blocks
    and reports are filtered out."""
    board = get_board_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return list_threads(board_id, viewer_id=viewer_id)


@router.get("/threads/{thread_id}", response_model=ForumThreadDetailResponse)
def get_forum_thread(thread_id: int, viewer_id: Optional[int] = Depends(get_current_user_id)):
    """Get a thread with its visible posts and poll (if any)."""
    thread = get_thread_detail(thread_id, viewer_id=viewer_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.post("/threads", response_model=ForumThreadDetailResponse)
def create_forum_thread(payload: CreateThreadRequest, user_id: int = Depends(require_auth)):
    """Create a new thread (with its opening post, and optional poll) on a board."""
    if payload.poll_question and (not payload.poll_options or len(payload.poll_options) < 2):
        raise HTTPException(status_code=400, detail="A poll needs at least 2 options")
    thread = create_thread(
        user_id=user_id,
        board_id=payload.board_id,
        title=payload.title,
        body=payload.body,
        poll_question=payload.poll_question,
        poll_options=payload.poll_options,
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Board not found")
    if isinstance(thread, dict) and thread.get("blocked"):
        raise HTTPException(status_code=422, detail="Post rejected by spam filter")
    return thread


# ---------------------------------------------------------------------------
# Posts (replies)
# ---------------------------------------------------------------------------

@router.post("/threads/{thread_id}/posts", response_model=ForumPostResponse)
def create_forum_post(thread_id: int, payload: CreatePostRequest, user_id: int = Depends(require_auth)):
    """Reply to a thread, optionally nested under a parent post."""
    post = create_post(
        user_id=user_id,
        thread_id=thread_id,
        body=payload.body,
        parent_post_id=payload.parent_post_id,
    )
    if post is None:
        raise HTTPException(status_code=404, detail="Thread or parent post not found")
    if isinstance(post, dict) and post.get("blocked"):
        raise HTTPException(status_code=422, detail="Post rejected by spam filter")
    return post


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

@router.post("/posts/{post_id}/vote", response_model=VotePostResponse)
def vote_forum_post(post_id: int, payload: VotePostRequest, user_id: int = Depends(require_auth)):
    """Upvote/downvote a post. Re-voting the same direction removes the vote."""
    if payload.direction not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    result = vote_post(user_id=user_id, post_id=post_id, direction=payload.direction)
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return result


@router.post("/polls/{poll_id}/vote", response_model=ForumPollResponse)
def vote_forum_poll(poll_id: int, payload: VotePollRequest, user_id: int = Depends(require_auth)):
    """Cast (or move) a user's single vote on a poll."""
    result = vote_poll(user_id=user_id, poll_id=poll_id, option_id=payload.option_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Poll or option not found")
    return result


# ---------------------------------------------------------------------------
# Reports + blocks (App Store 1.2 user-generated-content controls)
# ---------------------------------------------------------------------------

@router.post("/posts/{post_id}/report", response_model=ModerationStatusResponse)
def report_forum_post(post_id: int, payload: ReportPostRequest, user_id: int = Depends(require_auth)):
    """Report a post. It disappears for the reporter immediately."""
    try:
        result = report_post(reporter_id=user_id, post_id=post_id, reason=payload.reason, details=payload.details)
    except ValueError:
        raise HTTPException(status_code=400, detail="You cannot report your own post")
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return result


@router.post("/posts/{post_id}/block-author", response_model=ModerationStatusResponse)
def block_forum_post_author(post_id: int, user_id: int = Depends(require_auth)):
    """Block the author of a post — their threads and posts are hidden for the caller."""
    try:
        result = block_post_author(blocker_id=user_id, post_id=post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="You cannot block yourself")
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return result


@router.get("/blocks", response_model=List[ForumBlockResponse])
def list_forum_blocks(user_id: int = Depends(require_auth)):
    """Users the caller has blocked."""
    return list_blocks(user_id)


@router.delete("/blocks/{block_id}", response_model=ModerationStatusResponse)
def unblock_forum_user(block_id: int, user_id: int = Depends(require_auth)):
    """Remove one of the caller's blocks."""
    if not unblock(blocker_id=user_id, block_id=block_id):
        raise HTTPException(status_code=404, detail="Block not found")
    return {"status": "unblocked"}


@router.get("/admin/reports", response_model=List[ForumReportAdminResponse])
def list_forum_reports(status: Literal["open", "actioned", "dismissed"] = "open", _admin_id: int = Depends(require_admin)):
    """Moderation queue (admin only)."""
    return list_reports(status)


@router.post("/admin/reports/{report_id}/resolve", response_model=ForumReportAdminResponse)
def resolve_forum_report(report_id: int, payload: ResolveReportRequest, _admin_id: int = Depends(require_admin)):
    """Hide the reported post for everyone, or dismiss the report (admin only)."""
    result = resolve_report(report_id, payload.action)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return result
