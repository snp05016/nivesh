"""
transcript_engine.py — Task 1.2 of Nivesh Advisor Intelligence Pipeline

Two-layer transcript fetching strategy:
  Layer 1: YouTube Transcript API (free, zero compute)
  Layer 2: Local Whisper fallback (faster-whisper large-v3)
"""

import logging
import os
import tempfile
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# Devanagari Unicode block: U+0900 (ऀ) to U+097F (ॿ)
_DEVANAGARI_START = 0x0900
_DEVANAGARI_END = 0x097F


class TranscriptError(Exception):
    """Raised when all transcript layers fail."""
    pass


def _devanagari_ratio(text: str) -> float:
    """Return fraction of characters that are Devanagari Unicode."""
    if not text:
        return 0.0
    devanagari_count = sum(
        1 for ch in text
        if _DEVANAGARI_START <= ord(ch) <= _DEVANAGARI_END
    )
    return devanagari_count / len(text)


def _word_count(text: str) -> int:
    """Return whitespace-split word count."""
    return len(text.split())


def _passes_quality_gate(full_text: str, duration_seconds: float) -> bool:
    """
    Returns True if transcript passes quality requirements:
      - Devanagari ratio <= 15%
      - Word count >= 80 words per minute of video duration
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
    """Fix 2.29: Convert Western number scales to Indian in transcript text.
    Also flags broken Hinglish patterns (fix 2.15)."""
    import re as _re
    text = _re.sub(r'(\d+\.?\d*)\s*million', r'\1 million (≈\1×10 Lakhs)', text, flags=_re.IGNORECASE)
    text = _re.sub(r'(\d+\.?\d*)\s*billion', r'\1 billion (≈\1×100 Crores)', text, flags=_re.IGNORECASE)
    text = _re.sub(r'(\d+\.?\d*)\s*trillion', r'\1 trillion (≈\1×1 Lakh Crores)', text, flags=_re.IGNORECASE)
    return text


def _detect_hinglish_quality(text: str) -> dict:
    """Fix 2.15: Detect broken Hinglish translations from Whisper.
    Returns quality flags — high Hinglish ratio means risk of hallucination."""
    devanagari_ratio = _devanagari_ratio(text)
    hinglish_markers = ["matlab", "ki matlab", "aise hi", "thoda", "bahut", "kyunki"]
    hinglish_count = sum(1 for m in hinglish_markers if m in text.lower())
    return {
        "hinglish_flagged": hinglish_count >= 3 or devanagari_ratio > 0.1,
        "devanagari_ratio": round(devanagari_ratio, 3),
        "hinglish_marker_count": hinglish_count,
    }


def _build_result(source: str, segments: list, duration_seconds: float) -> dict:
    """Assemble the standard output dict."""
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
# Layer 1 — YouTube Transcript API
# ---------------------------------------------------------------------------

def _fetch_youtube_api(video_id: str, duration_seconds: float) -> Optional[dict]:
    """
    Attempt to fetch transcript via youtube_transcript_api.
    Returns result dict on success, None on failure.
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
        # Some versions/forks use static method, others need an instance
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            raw = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["en", "hi"]
            )
        elif hasattr(YouTubeTranscriptApi, "fetch"):
            # Instance-based fetch (seen in some versions like 1.2.x)
            raw = YouTubeTranscriptApi().fetch(
                video_id, languages=["en", "hi"]
            )
        else:
            # Fallback to manual list/find
            raw = YouTubeTranscriptApi().list(video_id).find_transcript(["en", "hi"]).fetch()
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
            "YouTube API transcript for %s failed quality gate; "
            "falling through to Whisper.",
            video_id,
        )
        return None

    return _build_result("youtube_api", segments, duration_seconds)


# ---------------------------------------------------------------------------
# Layer 2 — Local Whisper (faster-whisper)
# ---------------------------------------------------------------------------

def _fetch_whisper(video_id: str, duration_seconds: float) -> dict:
    """
    Download audio with yt-dlp, then transcribe with faster-whisper.
    Returns result dict or raises TranscriptError.
    """
    import yt_dlp
    from faster_whisper import WhisperModel

    # Create a temp file for audio download
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".%(ext)s")
    os.close(tmp_fd)
    # yt-dlp appends the real extension, so remove the placeholder file
    os.unlink(tmp_path)
    # Use the path without extension; yt-dlp will add the correct one
    tmp_base = tmp_path.replace(".%(ext)s", "")
    actual_tmp = tmp_path  # will be updated after download

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": tmp_base + ".%(ext)s",
        "quiet": True,
    }

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    downloaded_file: Optional[str] = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            # Find the actual downloaded file path
            if "requested_downloads" in info:
                downloaded_file = info["requested_downloads"][0].get("filepath")
            if not downloaded_file:
                # Fallback: scan for files matching the base path
                base_dir = os.path.dirname(tmp_base)
                base_name = os.path.basename(tmp_base)
                for fname in os.listdir(base_dir):
                    if fname.startswith(base_name):
                        downloaded_file = os.path.join(base_dir, fname)
                        break

        if not downloaded_file or not os.path.exists(downloaded_file):
            raise TranscriptError(
                f"yt-dlp download produced no file for video {video_id}"
            )

        logger.warning(
            "Layer 1 failed for %s; transcribing with Whisper large-v3.", video_id
        )

        model = WhisperModel("large-v3", device="cpu", compute_type="int8")

        segments_iter, info_obj = model.transcribe(
            downloaded_file,
            language="hi",
            task="transcribe",
            initial_prompt=(
                "Financial analysis of Indian stock market, "
                "NSE BSE companies, crore lakh rupees"
            ),
        )

        segments = []
        for seg in segments_iter:
            segments.append(
                {
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": seg.text.strip(),
                }
            )

        # Use Whisper-reported duration if not provided
        whisper_duration = duration_seconds
        if whisper_duration <= 0:
            if hasattr(info_obj, "duration") and info_obj.duration:
                whisper_duration = float(info_obj.duration)
            elif segments:
                whisper_duration = float(segments[-1]["end"])

        return _build_result("whisper_local", segments, whisper_duration)

    except TranscriptError:
        raise
    except Exception as exc:
        raise TranscriptError(
            f"Whisper transcription failed for video {video_id}: {exc}"
        ) from exc
    finally:
        # Clean up temp audio file
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.unlink(downloaded_file)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_transcript(video_id: str, duration_seconds: float = 0.0) -> dict:
    """
    Fetch transcript for a YouTube video.

    Tries Layer 1 (YouTube Transcript API) first; falls back to
    Layer 2 (local Whisper large-v3) if Layer 1 is unavailable or
    fails quality checks.

    Args:
        video_id: YouTube video ID (e.g. "dQw4w9WgXcQ").
        duration_seconds: Known video duration in seconds (0 = unknown).

    Returns:
        dict with keys: source, segments, full_text, duration_seconds

    Raises:
        TranscriptError: if both layers fail.
    """
    # Layer 1
    result = _fetch_youtube_api(video_id, duration_seconds)
    if result is not None:
        return result

    # Layer 2
    return _fetch_whisper(video_id, duration_seconds)
