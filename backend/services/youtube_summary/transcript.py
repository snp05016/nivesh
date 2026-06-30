"""Transcript extraction layer — youtube-transcript-api with yt-dlp fallback."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_CHARS: int = int(os.getenv("YOUTUBE_SUMMARY_MAX_CHARS", "50000"))

# Matches a bare 11-char video ID or any YouTube URL variant
_VIDEO_ID_RE = re.compile(
    r"(?:(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})|^([A-Za-z0-9_-]{11})$)"
)


def _parse_video_id(url_or_id: str) -> Optional[str]:
    """Return the 11-character video ID from a URL or bare ID, or None."""
    m = _VIDEO_ID_RE.search(url_or_id.strip())
    if not m:
        return None
    return m.group(1) or m.group(2)


def _sha256(text: str) -> str:
    """Return hex SHA-256 of text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class TranscriptExtractor:
    """Extracts transcript text for a YouTube video using available libraries."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, url_or_id: str) -> Optional[dict]:
        """Return transcript dict or None if unavailable.

        Dict shape:
            {
                "video_id":  str,
                "text":      str,          # full concatenated transcript
                "source":    str,          # "youtube_api" | "yt_dlp"
                "hash":      str,          # sha256 of text
                "segments":  list[dict],   # [{"start": float, "text": str}, ...]
                "char_count": int,
            }
        """
        video_id = _parse_video_id(url_or_id)
        if not video_id:
            logger.warning("TranscriptExtractor: could not parse video ID from %r", url_or_id)
            return None

        result = self._try_youtube_transcript_api(video_id)
        if result:
            return result

        result = self._try_yt_dlp(video_id)
        return result

    # ------------------------------------------------------------------
    # Strategy 1: youtube-transcript-api
    # ------------------------------------------------------------------

    def _try_youtube_transcript_api(self, video_id: str) -> Optional[dict]:
        """Attempt transcript fetch via youtube-transcript-api."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound  # type: ignore

            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Prefer manually created English; fall back to auto-generated
            transcript = None
            for lang in ("en", "en-IN", "en-GB"):
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    break
                except Exception as _e:
                    pass
            if transcript is None:
                try:
                    transcript = transcript_list.find_generated_transcript(["en", "en-IN"])
                except Exception as _e:
                    transcript = transcript_list.find_transcript(
                        [t.language_code for t in transcript_list]
                    )

            segments = transcript.fetch()
            raw_segments = [{"start": s["start"], "text": s["text"]} for s in segments]
            full_text = " ".join(s["text"] for s in segments)
            full_text = full_text[:_MAX_CHARS]

            return {
                "video_id": video_id,
                "text": full_text,
                "source": "youtube_api",
                "hash": _sha256(full_text),
                "segments": raw_segments,
                "char_count": len(full_text),
            }
        except ImportError:
            logger.debug("youtube-transcript-api not installed; skipping")
            return None
        except Exception as exc:
            logger.debug("youtube-transcript-api failed for %s: %s", video_id, exc)
            return None

    # ------------------------------------------------------------------
    # Strategy 2: yt-dlp subtitle / description fallback
    # ------------------------------------------------------------------

    def _try_yt_dlp(self, video_id: str) -> Optional[dict]:
        """Fetch auto-captions or description text via yt-dlp."""
        try:
            import yt_dlp  # type: ignore
        except ImportError:
            logger.debug("yt-dlp not installed; skipping fallback")
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-IN"],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # Try to get subtitle text from info dict directly (no disk write).
            # yt-dlp subtitle entries only carry URLs; fetching them requires a
            # separate network call (disk-based workflow) not implemented here.
            # Fall through to the description fallback below.
            text: Optional[str] = None

            if not text:
                # Fall back to description snippet — lower quality but better than nothing
                desc = (info.get("description") or "").strip()
                if len(desc) > 200:
                    text = desc[:_MAX_CHARS]
                    logger.debug("yt-dlp: using description fallback for %s (%d chars)", video_id, len(text))

            if not text:
                return None

            return {
                "video_id": video_id,
                "text": text,
                "source": "yt_dlp",
                "hash": _sha256(text),
                "segments": [],
                "char_count": len(text),
            }
        except Exception as exc:
            logger.debug("yt-dlp failed for %s: %s", video_id, exc)
            return None
