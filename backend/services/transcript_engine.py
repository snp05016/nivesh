"""
transcript_engine.py — Task 1.2 of Nivesh Advisor Intelligence Pipeline

Public captions only, via the YouTube Transcript API, unauthenticated. There is
no audio download, no cookie session and no local speech-to-text: videos without
public captions are skipped (REG-14).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Devanagari Unicode block: U+0900 (ऀ) to U+097F (ॿ)
_DEVANAGARI_START = 0x0900
_DEVANAGARI_END = 0x097F


class TranscriptError(Exception):
    """Raised when all transcript layers fail."""
    pass


def _devanagari_ratio(text: str) -> float:
    """Calculates the fraction of characters that are Devanagari Unicode.

    Args:
        text (str): The text to analyze.

    Returns:
        float: The ratio of Devanagari characters to total characters.
    """
    if not text:
        return 0.0
    devanagari_count = sum(
        1 for ch in text
        if _DEVANAGARI_START <= ord(ch) <= _DEVANAGARI_END
    )
    return devanagari_count / len(text)


def _word_count(text: str) -> int:
    """Calculates the whitespace-split word count.

    Args:
        text (str): The text to count words for.

    Returns:
        int: The number of words in the text.
    """
    return len(text.split())


def _passes_quality_gate(full_text: str, duration_seconds: float) -> bool:
    """Checks if the transcript passes quality requirements.

    Requirements:
      - Devanagari ratio <= 15%
      - Word count >= 80 words per minute of video duration

    Args:
        full_text (str): The full text of the transcript.
        duration_seconds (float): The duration of the video in seconds.

    Returns:
        bool: True if the transcript passes the quality gate, False otherwise.
    """
    ratio = _devanagari_ratio(full_text)
    if ratio > 0.15:
        logger.warning(
            "Quality gate failed: Devanagari ratio %.1f%% > 15%%", ratio * 100
        )
        return False

    if duration_seconds > 0:
        minutes = duration_seconds / 60.0
        wpm_threshold = 80 * minutes
        wc = _word_count(full_text)
        if wc < wpm_threshold:
            logger.warning(
                "Quality gate failed: word count %d < threshold %.0f "
                "(%.1f min × 80 wpm)",
                wc,
                wpm_threshold,
                minutes,
            )
            return False

    return True


def _normalize_western_scales(text: str) -> str:
    """Converts Western number scales to Indian in transcript text.

    Fix 2.29: Also flags broken Hinglish patterns (fix 2.15).

    Args:
        text (str): The transcript text containing Western scales.

    Returns:
        str: The normalized text with Indian scales.
    """
    import re as _re
    text = _re.sub(r'(\d+\.?\d*)\s*million', r'\1 million (≈\1×10 Lakhs)', text, flags=_re.IGNORECASE)
    text = _re.sub(r'(\d+\.?\d*)\s*billion', r'\1 billion (≈\1×100 Crores)', text, flags=_re.IGNORECASE)
    text = _re.sub(r'(\d+\.?\d*)\s*trillion', r'\1 trillion (≈\1×1 Lakh Crores)', text, flags=_re.IGNORECASE)
    return text


def _detect_hinglish_quality(text: str) -> dict:
    """Detects broken Hinglish in caption text.

    Fix 2.15: Returns quality flags — high Hinglish ratio means risk of hallucination.

    Args:
        text (str): The transcript text to analyze.

    Returns:
        dict: A dictionary containing quality flags:
            - "hinglish_flagged" (bool): Whether the text was flagged for poor quality.
            - "devanagari_ratio" (float): The ratio of Devanagari characters.
            - "hinglish_marker_count" (int): The count of common Hinglish words.
    """
    devanagari_ratio = _devanagari_ratio(text)
    hinglish_markers = ["matlab", "ki matlab", "aise hi", "thoda", "bahut", "kyunki"]
    hinglish_count = sum(1 for m in hinglish_markers if m in text.lower())
    return {
        "hinglish_flagged": hinglish_count >= 3 or devanagari_ratio > 0.1,
        "devanagari_ratio": round(devanagari_ratio, 3),
        "hinglish_marker_count": hinglish_count,
    }


def _build_result(source: str, segments: list, duration_seconds: float) -> dict:
    """Assembles the standard output dictionary for a transcript result.

    Args:
        source (str): The source of the transcript (e.g., 'youtube_api').
        segments (list[dict]): List of transcript segments.
        duration_seconds (float): The duration of the video in seconds.

    Returns:
        dict: The standardized transcript result dictionary containing segments,
            full_text, duration_seconds, and quality_flags.
    """
    full_text = " ".join(seg["text"] for seg in segments)
    full_text = _normalize_western_scales(full_text)
    quality = _detect_hinglish_quality(full_text)

    if duration_seconds <= 0 and segments:
        duration_seconds = float(segments[-1].get("end", 0))

    return {
        "source": source,
        "segments": segments,
        "full_text": full_text,
        "duration_seconds": duration_seconds,
        "quality_flags": quality,
    }


# ---------------------------------------------------------------------------
# YouTube Transcript API (public captions)
# ---------------------------------------------------------------------------

def _fetch_youtube_api(video_id: str, duration_seconds: float) -> Optional[dict]:
    """Attempts to fetch transcript via youtube_transcript_api.

    Args:
        video_id (str): The YouTube video ID.
        duration_seconds (float): The duration of the video in seconds.

    Returns:
        Optional[dict]: A dictionary containing the transcript result on success,
            or None on failure or if the quality gate fails.
    """
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            TranscriptsDisabled,
            NoTranscriptFound,
        )
    except ImportError as exc:
        logger.warning("youtube_transcript_api not available: %s", exc)
        return None

    try:
        ytt_api = YouTubeTranscriptApi()
        raw = ytt_api.fetch(video_id, languages=["en", "hi"])
    except (TranscriptsDisabled, NoTranscriptFound) as exc:
        logger.warning(
            "YouTube Transcript API: no transcript for %s — %s", video_id, exc
        )
        return None
    except Exception as exc:
        logger.warning(
            "YouTube Transcript API unexpected error for %s: %s", video_id, exc
        )
        return None

    # Normalise to standard segment format
    segments = []
    for entry in raw:
        if hasattr(entry, "text"):
            # Dataclass-based entry (seen in some library versions)
            text = getattr(entry, "text", "")
            start = float(getattr(entry, "start", 0))
            duration = float(getattr(entry, "duration", 0))
        else:
            # Dictionary-based entry (standard)
            text = entry.get("text", "")
            start = float(entry.get("start", 0))
            duration = float(entry.get("duration", 0))
            
        segments.append({
            "start": start,
            "end": start + duration,
            "text": text.strip(),
        })

    full_text = " ".join(seg["text"] for seg in segments)

    if not _passes_quality_gate(full_text, duration_seconds):
        logger.warning(
            "YouTube API transcript for %s failed quality gate; skipping.",
            video_id,
        )
        return None

    return _build_result("youtube_api", segments, duration_seconds)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_transcript(video_id: str, duration_seconds: float = 0.0) -> dict:
    """Fetches a transcript for a YouTube video.

    Uses public captions from the YouTube Transcript API only.

    Args:
        video_id (str): YouTube video ID (e.g. "dQw4w9WgXcQ").
        duration_seconds (float, optional): Known video duration in seconds (0 = unknown). Defaults to 0.0.

    Returns:
        dict: Dictionary with keys: 'source', 'segments', 'full_text', 'duration_seconds', 'quality_flags'.

    Raises:
        TranscriptError: If no public captions pass the quality gate.
    """
    result = _fetch_youtube_api(video_id, duration_seconds)
    if result is None:
        raise TranscriptError(f"No public captions available for video {video_id}")
    return result
