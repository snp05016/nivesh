"""
Nivesh Advisor Intelligence — Nightly Harvest Engine
Called exclusively by the CRON scheduler. Never imported by request-handling code.
"""

import json
import logging
import logging.handlers
import os
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from services.llm_utils import deepseek_chat as _deepseek_chat, DEEPSEEK_MODEL as _DEEPSEEK_MODEL
from services.sebi_registry import REGISTERED_CHANNELS

# ---------------------------------------------------------------------------
# Logging — handlers configured by the caller (CRON)
# ---------------------------------------------------------------------------

logger = logging.getLogger("advisor_harvester")

# ---------------------------------------------------------------------------
# Ensure logs/ directory exists
# ---------------------------------------------------------------------------

_LOGS_DIR = Path(__file__).parent.parent / "logs"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).parent.parent / ".env"

def _load_env() -> None:
    """Loads KEY=VALUE pairs from .env into os.environ (if not already set)."""
    if not _ENV_PATH.exists():
        return
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "").strip()

# ---------------------------------------------------------------------------
# Advisor registry
# ---------------------------------------------------------------------------

# Only SEBI-registered channels with a known channel_id (services/sebi_registry.py).
ADVISOR_REGISTRY = [c for c in REGISTERED_CHANNELS if c.get("channel_id")]

# ---------------------------------------------------------------------------
# DeepSeek V4 Flash stance extraction (Tier 1)
# Client + chat imported from services.llm_utils (single source)

HAIKU_SYSTEM = """You are a financial transcript analyst. Extract structured investment stance data from Indian financial advisor commentary. Output ONLY valid JSON. No preamble. No explanation."""

HAIKU_USER_TEMPLATE = """
Transcript snippet from {advisor_name} discussing {ticker}:
---
{snippet}
---
Extract and return this exact JSON structure:
{{
  "stance": "BULLISH" | "NEUTRAL" | "BEARISH",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "catalyst_summary": "<single bullet, max 120 chars, MUST include at least one number>"
}}
Rules:
- stance must be exactly: BULLISH, NEUTRAL, or BEARISH
- If hedging/undecided: NEUTRAL
- catalyst_summary must have a numeric anchor (₹ amounts in Lakhs/Crores, percentages, multiples)
"""

# ---------------------------------------------------------------------------
# Duration helpers
# ---------------------------------------------------------------------------

def _parse_iso8601_duration(duration_str: str) -> int:
    """Parses an ISO 8601 duration string into seconds.

    Args:
        duration_str (str): The ISO 8601 duration string (e.g. PT4M30S).

    Returns:
        int: The parsed duration in seconds, or 0 if unparseable.
    """
    if not duration_str:
        return 0
    # Try isodate if available
    try:
        import isodate  # type: ignore
        td = isodate.parse_duration(duration_str)
        return int(td.total_seconds())
    except ImportError:
        pass
    # Manual regex fallback
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    m = re.match(pattern, duration_str)
    if not m:
        return 0
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


# ---------------------------------------------------------------------------
# YouTube video list fetchers
# ---------------------------------------------------------------------------

async def _fetch_videos_youtube_api(channel_id: str, lookback_hours: int) -> list[dict]:
    """Fetches recent videos from a channel using the YouTube Data API v3.

    Args:
        channel_id (str): The YouTube channel ID.
        lookback_hours (int): The number of past hours to search for videos.

    Returns:
        list[dict]: A list of video dictionaries containing metadata.
    """
    import httpx

    published_after = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    search_url = "https://www.googleapis.com/youtube/v3/search"
    search_params = {
        "channelId": channel_id,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after,
        "maxResults": 10,
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(search_url, params=search_params)

    if resp.status_code in (429, 403):
        raise RuntimeError(
            f"YouTube API quota/auth error: HTTP {resp.status_code} — {resp.text[:200]}"
        )
    resp.raise_for_status()

    search_data = resp.json()
    items = search_data.get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
    if not video_ids:
        return []

    # Fetch durations and view counts
    details_url = "https://www.googleapis.com/youtube/v3/videos"
    details_params = {
        "part": "statistics,contentDetails",
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        dresp = await client.get(details_url, params=details_params)

    if dresp.status_code in (429, 403):
        raise RuntimeError(
            f"YouTube API quota/auth error (details): HTTP {dresp.status_code}"
        )
    dresp.raise_for_status()

    details_data = dresp.json()
    details_by_id: dict[str, dict] = {}
    for d in details_data.get("items", []):
        vid = d["id"]
        duration_str = d.get("contentDetails", {}).get("duration", "")
        view_count = int(d.get("statistics", {}).get("viewCount", 0))
        details_by_id[vid] = {
            "duration_seconds": _parse_iso8601_duration(duration_str),
            "view_count": view_count,
        }

    videos = []
    for item in items:
        vid_id = item.get("id", {}).get("videoId")
        if not vid_id:
            continue
        snippet = item.get("snippet", {})
        title = snippet.get("title", "")
        published_str = snippet.get("publishedAt", "")
        try:
            published_at = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            published_at = datetime.now(timezone.utc)

        extra = details_by_id.get(vid_id, {"duration_seconds": 0, "view_count": 0})
        videos.append({
            "video_id": vid_id,
            "title": title,
            "published_at": published_at,
            "duration_seconds": extra["duration_seconds"],
            "view_count": extra["view_count"],
            "url": f"https://www.youtube.com/watch?v={vid_id}",
        })

    return videos


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _video_already_processed(video_id: str) -> bool:
    """Checks if a video has already been processed by querying the database.

    Args:
        video_id (str): The unique YouTube video ID.

    Returns:
        bool: True if the video exists in the advisor_insights table, False otherwise.
    """
    from database import AdvisorInsight, get_session

    with get_session() as session:
        exists = (
            session.query(AdvisorInsight.id)
            .filter(AdvisorInsight.video_id == video_id)
            .first()
        )
        return exists is not None


def _insert_insight(
    *,
    ticker: str,
    advisor_name: str,
    channel_id: str,
    video_id: str,
    video_title: str,
    video_url: str,
    published_at: datetime,
    transcript_source: str,
    stance: str,
    confidence: str,
    catalyst_summary: str,
    raw_snippet: str,
    view_count: int,
) -> bool:
    """Inserts a new insight row into the advisor_insights database table.

    Silently ignores duplicates if a UniqueConstraint is triggered.

    Args:
        ticker (str): The stock ticker symbol.
        advisor_name (str): The name of the advisor.
        channel_id (str): The YouTube channel ID.
        video_id (str): The YouTube video ID.
        video_title (str): The title of the video.
        video_url (str): The URL of the video.
        published_at (datetime): The publication date of the video.
        transcript_source (str): The source of the transcript data.
        stance (str): The extracted stance (e.g., BULLISH).
        confidence (str): The extracted confidence level (e.g., HIGH).
        catalyst_summary (str): The summary of the catalyst.
        raw_snippet (str): The raw transcript snippet used for extraction.
        view_count (int): The video view count.

    Returns:
        bool: True if a new row was successfully inserted, False otherwise.
    """
    from database import AdvisorInsight, get_session
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    with get_session() as session:
        stmt = (
            sqlite_insert(AdvisorInsight)
            .values(
                ticker=ticker,
                advisor_name=advisor_name,
                channel_id=channel_id,
                video_id=video_id,
                video_title=video_title,
                video_url=video_url,
                published_at=published_at,
                transcript_source=transcript_source,
                stance=stance,
                confidence=confidence,
                catalyst_summary=catalyst_summary,
                raw_snippet=raw_snippet,
                view_count=view_count,
                created_at=datetime.now(timezone.utc),
            )
            .prefix_with("OR IGNORE")
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# LLM (DeepSeek) stance extraction
# ---------------------------------------------------------------------------

def _extract_stance_llm(advisor_name: str, ticker: str, snippet: str) -> dict | None:
    """Extracts a structured stance from a transcript snippet using an LLM.

    Args:
        advisor_name (str): The name of the advisor.
        ticker (str): The stock ticker being discussed.
        snippet (str): The transcript snippet containing the discussion.

    Returns:
        dict | None: The parsed stance dictionary with keys 'stance', 'confidence', 
        and 'catalyst_summary', or None if extraction fails.
    """
    user_content = HAIKU_USER_TEMPLATE.format(
        advisor_name=advisor_name,
        ticker=ticker,
        snippet=snippet[:3000],  # guard against oversized snippets
    )

    messages = [
        {"role": "system", "content": HAIKU_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    try:
        raw_text = _deepseek_chat(messages, max_tokens=400, temperature=0.1)
    except Exception as exc:
        logger.warning("DeepSeek stance call failed for %s/%s: %s", advisor_name, ticker, exc)
        return None

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text).strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Malformed stance JSON for %s/%s — %s — raw: %s",
            advisor_name,
            ticker,
            exc,
            raw_text[:200],
        )
        return None

    # Validate required fields
    stance = str(data.get("stance", "")).upper()
    confidence = str(data.get("confidence", "")).upper()
    catalyst_summary = str(data.get("catalyst_summary", ""))

    if stance not in ("BULLISH", "NEUTRAL", "BEARISH"):
        logger.warning(
            "Unexpected stance value '%s' for %s/%s — defaulting to NEUTRAL",
            stance,
            advisor_name,
            ticker,
        )
        stance = "NEUTRAL"

    if confidence not in ("HIGH", "MEDIUM", "LOW"):
        logger.warning(
            "Unexpected confidence value '%s' for %s/%s — defaulting to LOW",
            confidence,
            advisor_name,
            ticker,
        )
        confidence = "LOW"

    return {
        "stance": stance,
        "confidence": confidence,
        "catalyst_summary": catalyst_summary[:120],
    }


# Fix 2.50: sector-balancing normalization weights.
# Prevents Banking/IT sectors from crowding out mid/small-cap visibility.
_SECTOR_WEIGHTS = {
    "BANKING": 0.7, "IT": 0.7, "FINANCIAL_SERVICES": 0.7,
    "PHARMA": 1.0, "AUTO": 1.0, "FMCG": 1.0, "METALS": 1.0,
    "OIL_GAS": 1.0, "POWER": 1.0, "TELECOM": 1.0,
    "REALTY": 1.2, "MEDIA": 1.2, "TEXTILES": 1.2,
    "CHEMICALS": 1.0, "CEMENT": 1.0, "INFRA": 1.0,
}


def _get_sector_weight(sector: str) -> float:
    """Retrieves the normalization weight for a given sector.

    Mid/small-cap sectors get a boost (> 1.0) to prevent large sectors 
    like Banking/IT from crowding out consensus views.

    Args:
        sector (str): The name of the sector.

    Returns:
        float: The sector weight multiplier.
    """
    return _SECTOR_WEIGHTS.get(sector.upper(), 1.0)


# ---------------------------------------------------------------------------
# Core harvest logic
# ---------------------------------------------------------------------------

async def harvest_single_advisor(advisor: dict, lookback_hours: int = 24) -> int:
    """Harvests insights from a single advisor's recent videos.

    Fetches the video list, filters out short or processed videos, fetches 
    transcripts, identifies tickers, extracts stances using an LLM, and 
    inserts the results into the database.

    Args:
        advisor (dict): A dictionary containing the advisor's metadata.
        lookback_hours (int): The number of past hours to search for videos. Defaults to 24.

    Returns:
        int: The number of new insight rows inserted into the database.
    """
    from services.transcript_engine import get_transcript
    from services.ticker_matcher import find_tickers

    advisor_name = advisor["name"]
    channel_id = advisor["channel_id"]
    inserted_total = 0

    logger.info("Harvesting advisor: %s (channel %s)", advisor_name, channel_id)

    # --- Fetch video list ---
    # Official YouTube Data API only; no page scraping (REG-14).
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not set — skipping advisor %s", advisor_name)
        return 0
    try:
        videos: list[dict] = await _fetch_videos_youtube_api(channel_id, lookback_hours)
        logger.info(
            "%s: YouTube API returned %d videos", advisor_name, len(videos)
        )
    except Exception as exc:
        logger.warning("YouTube API fetch failed for %s: %s", advisor_name, exc)
        return 0

    for video in videos:
        vid_id: str = video["video_id"]
        title: str = video["title"]
        duration: int = video["duration_seconds"]
        published_at: datetime = video["published_at"]
        view_count: int = video["view_count"]
        url: str = video["url"]

        # Skip short videos (< 4 minutes = 240 seconds)
        if duration > 0 and duration < 240:
            logger.debug(
                "Skipping %s (%s) — too short: %ds", vid_id, title, duration
            )
            continue

        # Skip already-processed videos
        if _video_already_processed(vid_id):
            logger.debug("Skipping %s — already in DB", vid_id)
            continue

        # Fetch transcript
        try:
            transcript = await get_transcript(vid_id, float(duration))
        except Exception as exc:
            logger.warning(
                "Transcript fetch failed for %s (%s): %s", vid_id, title, exc
            )
            continue

        if not transcript or not transcript.get("full_text"):
            logger.warning("Empty transcript for %s (%s) — skipping", vid_id, title)
            continue

        transcript_source: str = transcript.get("source", "unknown")

        # Find ticker mentions
        try:
            ticker_matches: list[dict] = find_tickers(transcript)
        except Exception as exc:
            logger.warning(
                "Ticker matching failed for %s (%s): %s", vid_id, title, exc
            )
            continue

        if not ticker_matches:
            logger.debug("No tickers found in %s (%s)", vid_id, title)
            continue

        logger.info(
            "%s | %s — found %d ticker(s): %s",
            advisor_name,
            title[:60],
            len(ticker_matches),
            [m.get("ticker") for m in ticker_matches],
        )

        for match in ticker_matches:
            ticker: str = match.get("ticker", "")
            snippet: str = match.get("snippet", transcript["full_text"][:1500])

            if not ticker:
                continue

            # Fix 2.18: Positional token block indexing for multi-stock transcripts.
            # Extract text within ±500 chars of the ticker's first mention to avoid
            # misattributing stances across different stocks in the same video.
            ticker_pos = snippet.lower().find(ticker.lower().replace(".ns", "").replace(".bo", ""))
            if ticker_pos >= 0 and len(ticker_matches) > 1:
                window_start = max(0, ticker_pos - 500)
                window_end = min(len(snippet), ticker_pos + 800)
                snippet = snippet[window_start:window_end]

            # Call the stance-extraction LLM (DeepSeek)
            extracted = _extract_stance_llm(advisor_name, ticker, snippet)
            if extracted is None:
                continue

            inserted = _insert_insight(
                ticker=ticker,
                advisor_name=advisor_name,
                channel_id=channel_id,
                video_id=vid_id,
                video_title=title,
                video_url=url,
                published_at=published_at,
                transcript_source=transcript_source,
                stance=extracted["stance"],
                confidence=extracted["confidence"],
                catalyst_summary=extracted["catalyst_summary"],
                raw_snippet=snippet[:2000],
                view_count=view_count,
            )

            if inserted:
                inserted_total += 1
                logger.info(
                    "Inserted: %s | %s | %s | %s",
                    advisor_name,
                    ticker,
                    extracted["stance"],
                    extracted["confidence"],
                )
            else:
                logger.debug(
                    "Duplicate skipped: %s / %s in %s", ticker, vid_id, advisor_name
                )

    logger.info(
        "Finished %s — inserted %d row(s)", advisor_name, inserted_total
    )
    return inserted_total


def _ensure_file_handler() -> None:
    """Attach one size-capped rotating log file to the harvester logger (OPS-14, #414)."""
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
        return
    fh = logging.handlers.RotatingFileHandler(
        _LOGS_DIR / "advisor_harvester.log", maxBytes=5_000_000, backupCount=5
    )
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
    )
    logger.addHandler(fh)


async def harvest_all_advisors(lookback_hours: int = 24) -> None:
    """Harvests insights from all registered advisors sequentially.

    This function is intended to be called by a CRON scheduler. It wraps 
    the entire process in a try/except block to ensure failures are logged.

    Args:
        lookback_hours (int): The number of past hours to search for videos. Defaults to 24.
    """
    _load_env()
    global YOUTUBE_API_KEY
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
    _ensure_file_handler()

    logger.info(
        "=== harvest_all_advisors START | lookback=%dh | advisors=%d ===",
        lookback_hours,
        len(ADVISOR_REGISTRY),
    )

    total_inserted = 0
    try:
        for advisor in ADVISOR_REGISTRY:
            try:
                count = await harvest_single_advisor(advisor, lookback_hours)
                total_inserted += count
            except Exception as _e:
                logger.error(
                    "Unhandled error harvesting advisor %s:\n%s",
                    advisor.get("name"),
                    traceback.format_exc(),
                )
    except Exception as _e:
        logger.error(
            "Fatal error in harvest_all_advisors:\n%s", traceback.format_exc()
        )

    logger.info(
        "=== harvest_all_advisors END | total_inserted=%d ===", total_inserted
    )


def evaluate_analysis_outcomes(db) -> int:
    """Scores AnalysisHistory signals at a fixed 30-calendar-day horizon (ML-15).

    Entry (close on or before the analysis date) and exit (first close on or after
    analysis date + 30 days) both come from one auto-adjusted series, so the
    horizon is the same for every row and splits/bonuses cancel out. The label is
    services.outcome_labels.direction_hit: HOLD/NEUTRAL abstain (was_correct stays
    None) but outcome_checked_at is set so the row is not reselected. Symbols with
    no usable prices are given up on (checked, no label) once older than
    UNRESOLVABLE_AGE_DAYS. Processes at most 50 rows per run (API rate limits).

    Args:
        db: The SQLAlchemy database session.

    Returns:
        int: The number of analysis outcomes successfully evaluated and updated.
    """
    from database import AnalysisHistory
    import pandas as pd
    from services.outcome_labels import (
        UNRESOLVABLE_AGE_DAYS, direction_hit, fetch_adjusted_history, window_return,
    )

    horizon_days = 30
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=horizon_days)
    pending = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.outcome_checked_at == None)  # noqa: E711
        .filter(AnalysisHistory.created_at < cutoff)
        .order_by(AnalysisHistory.created_at)
        .limit(50)
        .all()
    )

    evaluated = 0
    for analysis in pending:
        try:
            ticker = analysis.ticker
            if not ticker:
                analysis.outcome_checked_at = now  # unscorable: never reselect it (it would starve the batch)
                db.commit()
                continue
            anchor = pd.Timestamp(analysis.created_at.date())
            exit_on = anchor + pd.Timedelta(days=horizon_days)
            hist = fetch_adjusted_history(
                ticker, start=anchor - pd.Timedelta(days=10), end=exit_on + pd.Timedelta(days=15),
            )
            ret = window_return(hist, anchor, exit_on)
            if ret is None:
                if (pd.Timestamp(now.date()) - anchor).days > UNRESOLVABLE_AGE_DAYS:
                    analysis.outcome_checked_at = now  # delisted / no prices: terminal, unlabelled
                    db.commit()
                continue

            analysis.outcome_delta_pct = round(ret * 100, 2)
            analysis.outcome_checked_at = now
            analysis.was_correct = direction_hit(analysis.signal, ret)
            db.commit()
            evaluated += 1
        except Exception as e:
            db.rollback()
            logger.warning(f"[outcome_eval] {getattr(analysis, 'ticker', '?')}: {e}")

    logger.info(f"[outcome_eval] Evaluated {evaluated} analysis outcomes")
    if pending and evaluated == 0:
        logger.warning(f"[outcome_eval] {len(pending)} due rows, 0 labelled: check price data (DB-03)")
    return evaluated
