"""
Nivesh Harvester — YouTube Finance Channels harvester.

Fetches the latest videos from a curated registry of reputable Indian finance
YouTube channels via the YouTube Data API v3, optionally enriches them with
captions/transcripts via youtube_transcript_api, and stores the results as
YOUTUBE cards directly to the DB (the scheduler reformats them later).

Fully defensive: one channel failing must not stop others. The top-level
function NEVER raises — on catastrophic failure it records SourceHealth and
returns 0.

Public:
  harvest_youtube_transcripts(limit=20) -> int   (number of NEW cards stored)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from models import get_session, upsert_card, record_source_health
from reformatter import make_external_id, derive_credential

logger = logging.getLogger("harvester.youtube")

# ═════════════════════════════════════════════════════════════════════════════
# Channel registry  (name, credibility 5-8, optional search_query override)
# ═════════════════════════════════════════════════════════════════════════════

CHANNEL_REGISTRY: list[dict[str, Any]] = [
    {"name": "CNBC-TV18",                    "credibility": 8, "search_query": "CNBC-TV18"},
    {"name": "ET Now",                       "credibility": 8, "search_query": "ET Now"},
    {"name": "BQ Prime",                     "credibility": 8, "search_query": "BQ Prime"},
    {"name": "NDTV Profit",                  "credibility": 8, "search_query": "NDTV Profit"},
    {"name": "Zee Business",                 "credibility": 7, "search_query": "Zee Business"},
    {"name": "Moneycontrol",                 "credibility": 7, "search_query": "Moneycontrol"},
    {"name": "CA Rachana Phadke Ranade",     "credibility": 6, "search_query": "CA Rachana Phadke Ranade"},
    {"name": "Asset Yogi",                   "credibility": 6, "search_query": "Asset Yogi"},
    {"name": "FinnovationZ",                 "credibility": 6, "search_query": "FinnovationZ"},
    {"name": "Invest Yadnya",                "credibility": 6, "search_query": "Invest Yadnya"},
    {"name": "SOIC",                         "credibility": 6, "search_query": "SOIC"},
    {"name": "Value Research",               "credibility": 6, "search_query": "Value Research"},
]

# YouTube Data API v3 base URL
_YT_API_BASE = "https://www.googleapis.com/youtube/v3"
_SOURCE_HEALTH_NAME = "YouTube Finance Channels"

# Polite pause between API calls (seconds) to avoid hammering quota
_API_SLEEP = 0.3


# ═════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═════════════════════════════════════════════════════════════════════════════

def _api_key() -> str:
    return os.getenv("YOUTUBE_API_KEY", "")


def _yt_get(endpoint: str, params: dict[str, Any]) -> dict | None:
    """GET a YouTube Data API v3 endpoint. Returns parsed JSON or None on error."""
    params["key"] = _api_key()
    url = f"{_YT_API_BASE}/{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 403:
            logger.warning("YouTube API 403 (quota exhausted or key invalid) for %s", endpoint)
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("YouTube API request failed (%s): %s", endpoint, exc)
        return None


def _resolve_channel_id(search_query: str) -> str | None:
    """Search for a channel by name and return its channel ID, or None."""
    data = _yt_get("search", {
        "part": "snippet",
        "q": search_query,
        "type": "channel",
        "maxResults": 1,
        "regionCode": "IN",
    })
    time.sleep(_API_SLEEP)
    if not data:
        return None
    items = data.get("items", [])
    if not items:
        return None
    return items[0].get("id", {}).get("channelId")


def _list_recent_videos(channel_id: str, max_results: int = 2) -> list[dict]:
    """Return up to max_results recent video items for a channel."""
    data = _yt_get("search", {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "order": "date",
        "maxResults": max_results,
        "regionCode": "IN",
    })
    time.sleep(_API_SLEEP)
    if not data:
        return []
    return data.get("items", [])


def _fetch_transcript(video_id: str) -> str:
    """Best-effort transcript fetch. Returns empty string on any failure."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        segs = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "hi"])
        return " ".join(s["text"] for s in segs if s.get("text"))
    except Exception:
        return ""


def _build_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _safe_published(snippet: dict) -> str | None:
    """Extract publishedAt from snippet; return ISO string or None."""
    raw = (snippet or {}).get("publishedAt")
    return raw if raw else None


# ═════════════════════════════════════════════════════════════════════════════
# Public entry point
# ═════════════════════════════════════════════════════════════════════════════

def harvest_youtube_transcripts(limit: int = 20) -> int:
    """Fetch latest videos from curated finance channels, store as YOUTUBE cards.

    Returns the number of NEW cards stored. NEVER raises.
    """
    try:
        return _harvest(limit)
    except Exception as exc:
        logger.exception("Catastrophic failure in harvest_youtube_transcripts: %s", exc)
        try:
            with get_session() as s:
                record_source_health(
                    s,
                    _SOURCE_HEALTH_NAME,
                    success=False,
                    error=f"Catastrophic failure: {exc}",
                )
        except Exception:
            pass
        return 0


def _harvest(limit: int) -> int:
    """Inner (non-defensive) implementation called by harvest_youtube_transcripts."""
    api_key = _api_key()
    if not api_key or len(api_key) < 10:
        logger.warning(
            "YOUTUBE_API_KEY absent or too short — YouTube harvester skipped."
        )
        with get_session() as s:
            record_source_health(
                s,
                _SOURCE_HEALTH_NAME,
                success=False,
                error="YOUTUBE_API_KEY not configured",
            )
        return 0

    num_channels = len(CHANNEL_REGISTRY)
    # Distribute limit across channels: at least 1, at most 3 per channel.
    per_channel = max(1, min(3, (limit + num_channels - 1) // num_channels))

    new_count = 0
    errors: list[str] = []

    for channel in CHANNEL_REGISTRY:
        channel_name: str = channel["name"]
        credibility: int = channel["credibility"]
        search_query: str = channel.get("search_query", channel_name)

        try:
            new_count += _harvest_channel(
                channel_name=channel_name,
                search_query=search_query,
                credibility=credibility,
                max_videos=per_channel,
            )
        except Exception as exc:
            msg = f"{channel_name}: {exc}"
            logger.warning("Channel harvest failed — %s", msg)
            errors.append(msg)

        # Stop early if we've reached the overall limit
        if new_count >= limit:
            break

    with get_session() as s:
        if errors and new_count == 0:
            # All channels failed
            record_source_health(
                s,
                _SOURCE_HEALTH_NAME,
                success=False,
                error="; ".join(errors[:3]),
            )
        else:
            record_source_health(
                s,
                _SOURCE_HEALTH_NAME,
                success=True,
                items=new_count,
            )

    logger.info(
        "YouTube harvest complete: %d new cards stored, %d channel errors",
        new_count,
        len(errors),
    )
    return new_count


def _harvest_channel(
    *,
    channel_name: str,
    search_query: str,
    credibility: int,
    max_videos: int,
) -> int:
    """Resolve channel, fetch recent videos, store cards. Returns new card count."""
    channel_id = _resolve_channel_id(search_query)
    if not channel_id:
        logger.debug("Could not resolve channel ID for '%s' — skipping", channel_name)
        return 0

    videos = _list_recent_videos(channel_id, max_results=max_videos)
    if not videos:
        logger.debug("No recent videos found for '%s'", channel_name)
        return 0

    new_count = 0
    credential = derive_credential("YOUTUBE")

    for item in videos:
        try:
            video_id: str = item.get("id", {}).get("videoId", "")
            if not video_id:
                continue

            snippet: dict = item.get("snippet", {})
            title: str = snippet.get("title", "").strip()
            description: str = snippet.get("description", "").strip()
            published_at: str | None = _safe_published(snippet)

            video_url = _build_video_url(video_id)

            # Best-effort transcript (empty string if unavailable)
            transcript_text = _fetch_transcript(video_id)
            time.sleep(_API_SLEEP)

            # Assemble raw_text: title + description + transcript (capped)
            raw_text = "\n".join(filter(None, [
                title,
                description,
                transcript_text[:4000] if transcript_text else "",
            ]))

            if not raw_text.strip():
                continue

            external_id = make_external_id(video_url, raw_text)

            card = {
                "external_id": external_id,
                "source_type": "YOUTUBE",
                "source_name": channel_name,
                "source_url": video_url,
                "original_author": channel_name,
                "published_at": published_at,
                "title": title or f"{channel_name} video",
                "raw_text": raw_text,
                "tickers": [],
                "card_type": "YOUTUBE",
                "credibility_score": credibility,
                "expert_credential": credential,
                "reformatted_summary": None,
            }

            with get_session() as s:
                inserted = upsert_card(s, card)
                if inserted:
                    new_count += 1
                    logger.debug("Stored new card: %s — %s", channel_name, title[:60])

        except Exception as exc:
            logger.warning(
                "Failed to process video '%s' from '%s': %s",
                item.get("id", {}).get("videoId", "?"),
                channel_name,
                exc,
            )
            continue

    return new_count
