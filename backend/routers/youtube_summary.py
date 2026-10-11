"""
YouTube summary endpoints.

Endpoints:
  POST /api/v1/youtube/summary        — fetch or generate a summary for a YouTube URL
  GET  /api/v1/youtube/summary/{video_id} — return a cached summary by video ID or 404
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from helpers import require_auth
from services.llm_budget import require_llm_budget
from services.youtube_summary.schemas import YouTubeVideoSummaryResponse

logger = logging.getLogger("youtube_summary.router")

router = APIRouter(prefix="/api/v1/youtube", tags=["YouTube"])

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
from pydantic import BaseModel


class SummaryRequest(BaseModel):
    url: str
    force_refresh: bool = False


# ---------------------------------------------------------------------------
# Dependency — lazy import so missing summarizer.py gives a clear error at
# request time rather than crashing the whole application at import time.
# ---------------------------------------------------------------------------

_NOT_REGISTRY_DETAIL = (
    "Summaries are available only for videos from SEBI-registered channels in Nivesh's registry."
)


def _is_registry_video(video_id: str) -> bool:
    """REG-03: only videos harvested from SEBI-registry channels may be summarised."""
    from services.youtube_summary.summarizer import is_registry_video
    return is_registry_video(video_id)


def _get_service():
    """Return the shared YouTubeSummaryService singleton (imported lazily)."""
    try:
        from services.youtube_summary.summarizer import get_youtube_summary_service
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="YouTube summary service is not available",
        ) from exc
    return get_youtube_summary_service()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_video_id(url: str) -> str:
    """Return the 11-character YouTube video ID from a URL or bare ID, or raise 400.

    Uses the summary service's own parser so the ID checked against the registry is the
    ID that gets summarised (REG-03).
    """
    from services.youtube_summary.transcript import _parse_video_id
    video_id = _parse_video_id(url)
    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="Could not extract a YouTube video ID from the provided URL.",
        )
    return video_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/summary", response_model=YouTubeVideoSummaryResponse)
async def post_summary(
    req: SummaryRequest,
    user_id: int = Depends(require_llm_budget("youtube_summary")),
):
    """
    Generate or return a cached AI summary for a YouTube video URL.

    Fetches the transcript, runs it through the summarisation pipeline, and
    persists the result.  Pass ``force_refresh=true`` to bypass the cache and
    regenerate even if a summary already exists.

    Args:
        req (SummaryRequest): JSON body containing ``url`` and optional
            ``force_refresh`` flag.
        user_id (int): Caller from the Bearer JWT; the daily AI budget applies.

    Returns:
        YouTubeVideoSummaryResponse: Structured summary with timestamps and
            source metadata.

    Raises:
        HTTPException 400: URL does not contain a valid YouTube video ID.
        HTTPException 401: Missing or invalid authorisation header.
        HTTPException 403: The video is not from a SEBI-registry channel.
        HTTPException 429: The caller's daily AI budget is spent.
        HTTPException 503: Summary service is not available, or AI is paused.
        HTTPException 500: Unexpected error during summarisation.
    """
    video_id = _extract_video_id(req.url)
    if not await asyncio.to_thread(_is_registry_video, video_id):
        raise HTTPException(status_code=403, detail=_NOT_REGISTRY_DETAIL)
    service = _get_service()

    try:
        result: YouTubeVideoSummaryResponse = await service.summarize(
            url_or_id=video_id,  # REG-03: summarise exactly the registry-checked ID
            force_refresh=req.force_refresh,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("post_summary failed for video_id=%s: %s", video_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {exc}") from exc


@router.get("/summary/{video_id}", response_model=YouTubeVideoSummaryResponse)
def get_summary(
    video_id: str,
    authorization: str = Header(None),
):
    """
    Return a previously generated summary from the cache.

    Args:
        video_id (str): 11-character YouTube video ID.
        authorization (str): Bearer JWT issued by /auth/login.

    Returns:
        YouTubeVideoSummaryResponse: The cached structured summary.

    Raises:
        HTTPException 401: Missing or invalid authorisation header.
        HTTPException 404: No cached summary exists for this video ID, or the video is
            not from a SEBI-registry channel.
        HTTPException 503: Summary service is not available.
        HTTPException 500: Unexpected error during cache lookup.
    """
    require_auth(authorization)

    if not video_id or len(video_id) != 11:
        raise HTTPException(
            status_code=400,
            detail="video_id must be exactly 11 characters.",
        )

    service = _get_service()

    try:
        # REG-03: a non-registry video has no servable summary (any old cached row included).
        result = service.get_cached(video_id) if _is_registry_video(video_id) else None
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_summary failed for video_id=%s: %s", video_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache lookup failed: {exc}") from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached summary found for video_id={video_id!r}. "
                   "POST /api/v1/youtube/summary to generate one.",
        )

    return result
