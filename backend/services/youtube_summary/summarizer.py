"""Core orchestration: check cache → extract → chunk → summarise → cache → return."""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Optional

from services.youtube_summary.cache import YouTubeSummaryCache
from services.youtube_summary.chunking import TranscriptChunker
from services.youtube_summary.providers import get_provider
from services.youtube_summary.schemas import (
    SourceMetadata,
    SummaryContent,
    YouTubeVideoSummaryResponse,
)
from services.youtube_summary.transcript import TranscriptExtractor, _parse_video_id

logger = logging.getLogger(__name__)

_ENABLED: bool = os.getenv("YOUTUBE_SUMMARY_ENABLED", "true").lower() != "false"
_MAX_CHARS: int = int(os.getenv("YOUTUBE_SUMMARY_MAX_CHARS", "50000"))
_CHUNK_SIZE: int = 8000
_MAX_CHUNKS: int = 20
_PROVIDER_NAME: Optional[str] = os.getenv("YOUTUBE_SUMMARY_PROVIDER", "deepseek")

_VIDEO_URL_TEMPLATE = "https://www.youtube.com/watch?v={}"


class YouTubeSummaryService:
    """Orchestrates transcript extraction, chunking, AI summarisation, and caching."""

    def __init__(self) -> None:
        self._extractor = TranscriptExtractor()
        self._chunker = TranscriptChunker()
        self._cache = YouTubeSummaryCache()

    async def summarize(
        self,
        url_or_id: str,
        force_refresh: bool = False,
    ) -> YouTubeVideoSummaryResponse:
        """Run the full summarisation pipeline and return a structured response.

        Steps:
          1. Parse video ID.
          2. If not force_refresh, check DB cache.
          3. Extract transcript via youtube-transcript-api / yt-dlp.
          4. Chunk transcript.
          5. Call AI provider.
          6. Cache result.
          7. Assemble and return YouTubeVideoSummaryResponse.
        """
        if not _ENABLED:
            return self._disabled_response(url_or_id)

        video_id = _parse_video_id(url_or_id)
        if not video_id:
            return self._error_response(
                url_or_id or "",
                "Could not parse a valid YouTube video ID from the provided input.",
            )

        video_url = _VIDEO_URL_TEMPLATE.format(video_id)

        # ── Step 1: transcript extraction ──────────────────────────────────
        transcript = self._extractor.extract(video_id)
        if not transcript:
            return self._error_response(
                video_id,
                "Transcript unavailable — the video may be private, have no captions, or "
                "lack a YouTube API key / yt-dlp installation.",
                video_url=video_url,
            )

        transcript_hash: str = transcript["hash"]
        transcript_source: str = transcript["source"]
        transcript_chars: int = transcript["char_count"]

        # ── Step 2: cache lookup ───────────────────────────────────────────
        if not force_refresh:
            cached_data = self._cache.get(video_id, transcript_hash)
            if cached_data:
                logger.debug("Cache hit for video_id=%s", video_id)
                return self._build_response(
                    video_id=video_id,
                    video_url=video_url,
                    summary_dict=cached_data,
                    transcript_source=transcript_source,
                    transcript_chars=transcript_chars,
                    from_cache=True,
                    provider_name="cached",
                    chunks_processed=0,
                )

        # ── Step 3: chunking ───────────────────────────────────────────────
        text = transcript["text"][:_MAX_CHARS]
        chunks = self._chunker.chunk(text, max_chars=_CHUNK_SIZE)
        chunks = chunks[:_MAX_CHUNKS]

        if not chunks:
            return self._error_response(
                video_id,
                "Transcript is empty after extraction.",
                video_url=video_url,
            )

        # ── Step 4: AI summarisation ───────────────────────────────────────
        provider = get_provider(_PROVIDER_NAME)
        provider_name = type(provider).__name__.replace("Provider", "").lower()

        try:
            summary_dict = await provider.summarize_chunks(chunks)
        except Exception as exc:
            logger.error("Provider %s failed for %s: %s", provider_name, video_id, exc)
            return self._error_response(
                video_id,
                f"Summary generation failed: {exc}",
                video_url=video_url,
            )

        # ── Step 5: cache write ────────────────────────────────────────────
        self._cache.set(video_id, summary_dict, transcript_hash)

        return self._build_response(
            video_id=video_id,
            video_url=video_url,
            summary_dict=summary_dict,
            transcript_source=transcript_source,
            transcript_chars=transcript_chars,
            from_cache=False,
            provider_name=provider_name,
            chunks_processed=len(chunks),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_response(
        self,
        *,
        video_id: str,
        video_url: str,
        summary_dict: dict,
        transcript_source: str,
        transcript_chars: int,
        from_cache: bool,
        provider_name: str,
        chunks_processed: int,
    ) -> YouTubeVideoSummaryResponse:
        """Construct a YouTubeVideoSummaryResponse from raw summary dict."""
        summary = SummaryContent(
            tldr=summary_dict.get("tldr", ""),
            key_points=summary_dict.get("key_points", []),
            finance_insights=summary_dict.get("finance_insights", []),
            tickers_mentioned=summary_dict.get("tickers_mentioned", []),
            risks_or_red_flags=summary_dict.get("risks_or_red_flags", []),
            action_items=summary_dict.get("action_items", []),
            sentiment=summary_dict.get("sentiment", "neutral"),
            confidence=float(summary_dict.get("confidence", 0.0)),
        )
        source = SourceMetadata(
            transcript_source=transcript_source,
            summary_provider=provider_name,
            cached=from_cache,
            transcript_hash="",  # not exposed to client
            estimated_input_tokens=transcript_chars // 4,
            estimated_output_tokens=chunks_processed * 500,
        )
        return YouTubeVideoSummaryResponse(
            video_id=video_id,
            url=video_url,
            title="",
            channel="",
            duration_seconds=0,
            summary=summary,
            timestamps=[],
            source=source,
        )

    def _error_response(
        self,
        url_or_id: str,
        error: str,
        video_url: str = "",
    ) -> YouTubeVideoSummaryResponse:
        """Return a minimal error response preserving schema shape."""
        vid = _parse_video_id(url_or_id) or url_or_id
        if not video_url and vid:
            video_url = _VIDEO_URL_TEMPLATE.format(vid)
        logger.warning("YouTubeSummaryService error [%s]: %s", vid, error)
        return YouTubeVideoSummaryResponse(
            video_id=vid,
            url=video_url,
            title="",
            channel="",
            duration_seconds=0,
            summary=SummaryContent(),
            timestamps=[],
            source=SourceMetadata(
                transcript_source="none",
                summary_provider="none",
                cached=False,
                transcript_hash="",
                estimated_input_tokens=0,
                estimated_output_tokens=0,
            ),
        )

    def get_cached(self, video_id: str) -> Optional[YouTubeVideoSummaryResponse]:
        """Return a cached response for video_id without requiring transcript hash.

        Used by the GET endpoint to retrieve any existing summary from the DB.
        Returns None if no summary exists.
        """
        try:
            from models.db_models import YouTubeVideoSummary
        except ImportError:
            return None

        try:
            from database import get_session
            import json as _json
            with get_session() as session:
                row = (
                    session.query(YouTubeVideoSummary)
                    .filter(YouTubeVideoSummary.video_id == video_id)
                    .first()
                )
                if row is None:
                    return None
                summary_dict = _json.loads(row.summary_json)
        except Exception as exc:
            logger.warning("get_cached failed for %s: %s", video_id, exc)
            return None

        video_url = _VIDEO_URL_TEMPLATE.format(video_id)
        return self._build_response(
            video_id=video_id,
            video_url=video_url,
            summary_dict=summary_dict,
            transcript_source=getattr(row, "transcript_source", "cached"),
            transcript_chars=getattr(row, "estimated_input_tokens", 0) * 4,
            from_cache=True,
            provider_name=getattr(row, "summary_provider", "cached"),
            chunks_processed=0,
        )

    def _disabled_response(self, url_or_id: str) -> YouTubeVideoSummaryResponse:
        """Return a stub response when the service is disabled via env var."""
        return self._error_response(
            url_or_id,
            "YouTube summary service is disabled (YOUTUBE_SUMMARY_ENABLED=false).",
        )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

_service_instance: Optional[YouTubeSummaryService] = None
_service_lock = threading.Lock()


def get_youtube_summary_service() -> YouTubeSummaryService:
    """FastAPI Depends-compatible factory returning a shared service instance."""
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            _service_instance = YouTubeSummaryService()
    return _service_instance
