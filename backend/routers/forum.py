"""Community Forum API — boards, threads, posts, polls, votes.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/forum_service.py (Controller-Service-Repository).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.security import require_auth
from services.forum_service import (
    create_post,
    create_thread,
    get_board_by_id,
    get_thread_detail,
    list_boards,
    list_threads,
    seed_mock_boards_if_empty,
    thread_count_for_board,
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
def list_board_threads(board_id: int):
    """List thread summaries for a board."""
    board = get_board_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return list_threads(board_id)


@router.get("/threads/{thread_id}", response_model=ForumThreadDetailResponse)
def get_forum_thread(thread_id: int):
    """Get a thread with all its posts and poll (if any)."""
    thread = get_thread_detail(thread_id)
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
