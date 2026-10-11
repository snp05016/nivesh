"""
Nivesh YouTube Harvester — SEBI-Registered Channels Only
=========================================================
Two harvest modes:
  1. channel_harvest  — Fetches latest N videos from each curated SEBI channel nightly
  2. portfolio_harvest — Tags already-harvested registry videos with the held tickers
     they mention. It never searches YouTube: open search returned unregistered
     finfluencer videos (REG-03).

Channel harvest uses YouTube Data API v3 when YOUTUBE_API_KEY is set, falling back
silently to yt-dlp. Never raises. Never blocks the main request pipeline.
Zero Anthropic API calls.
"""

import os
import time
import logging
import requests
import yt_dlp
from datetime import datetime, timezone
from sqlalchemy import or_
from database import get_session, YouTubeVideo, Portfolio
# SEBI-registered channels only; the registry and every INH/INA number live there.
from services.sebi_registry import REGISTERED_CHANNELS as CHANNEL_REGISTRY

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_API_AVAILABLE = bool(YOUTUBE_API_KEY and len(YOUTUBE_API_KEY) > 10)
MIN_SUBSCRIBER_THRESHOLD = 100_000  # only harvest from channels with 100k+ subscribers

# Company name map for better search quality.
TICKER_COMPANY_MAP = {
    "RELIANCE": "Reliance Industries",
    "TCS": "TCS Tata Consultancy",
    "HDFCBANK": "HDFC Bank",
    "INFY": "Infosys",
    "WIPRO": "Wipro",
    "SUZLON": "Suzlon Energy",
    "IRFC": "IRFC Indian Railway Finance",
    "ADANIENT": "Adani Enterprises",
    "ICICIBANK": "ICICI Bank",
    "BAJFINANCE": "Bajaj Finance",
    "TATAMOTORS": "Tata Motors",
    "SBIN": "SBI State Bank India",
    "AXISBANK": "Axis Bank",
    "MARUTI": "Maruti Suzuki",
    "TITAN": "Titan Company",
    "ASIANPAINT": "Asian Paints",
    "NESTLEIND": "Nestle India",
    "HINDUNILVR": "Hindustan Unilever",
    "TATASTEEL": "Tata Steel",
    "ZOMATO": "Zomato",
    "IRCTC": "IRCTC Indian Railway Catering",
    "COALINDIA": "Coal India",
    "ONGC": "ONGC Oil Natural Gas",
    "NTPC": "NTPC Power",
    "POWERGRID": "Power Grid Corporation",
    "BPCL": "BPCL Bharat Petroleum",
    "IOC": "Indian Oil Corporation",
    "GAIL": "GAIL India Gas",
    "HINDALCO": "Hindalco Aluminium",
    "JSWSTEEL": "JSW Steel",
}


def get_company_name(ticker: str) -> str:
    """Returns a human-readable company name for YouTube search quality.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        str: The full company name.
    """
    t = ticker.upper()
    if t in TICKER_COMPANY_MAP:
        return TICKER_COMPANY_MAP[t]
    try:
        import yfinance as yf
        info = yf.Ticker(f"{t}.NS").info
        name = info.get("longName") or info.get("shortName") or t
        for suffix in [" Limited", " Ltd.", " Ltd", " Private Limited", " Pvt. Ltd"]:
            name = name.replace(suffix, "").strip()
        return name
    except Exception as _e:
        return t


def _parse_date(raw: str) -> datetime:
    """Safely parses a date string from either API (ISO) or yt-dlp (YYYYMMDD) format.

    Args:
        raw (str): The raw date string.

    Returns:
        datetime: The parsed datetime object in UTC. Defaults to current UTC time if parsing fails.
    """
    if not raw:
        return datetime.now(timezone.utc)
    try:
        if "T" in str(raw):
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
        if len(str(raw)) == 8:
            return datetime.strptime(str(raw), "%Y%m%d")
    except Exception as _e:
        pass
    return datetime.now(timezone.utc)


def _upsert_video(db, video_dict: dict) -> bool:
    """Inserts a video row if video_id does not already exist.

    If it exists, updates matched_ticker if currently null.

    Args:
        db: The SQLAlchemy database session.
        video_dict (dict): A dictionary containing the video data to upsert.

    Returns:
        bool: True if a new row was inserted, False otherwise (including any video
            without a registry sebi_reg, which is never stored).
    """
    vid_id = video_dict.get("video_id", "")
    # REG-03: only videos from SEBI-registered registry channels are ever persisted.
    if not vid_id or not video_dict.get("sebi_reg"):
        return False

    existing = db.query(YouTubeVideo).filter(YouTubeVideo.video_id == vid_id).first()
    if existing:
        if not existing.matched_ticker and video_dict.get("matched_ticker"):
            existing.matched_ticker = video_dict["matched_ticker"]
        # Backfill empty title / thumbnail from fresh harvest data
        new_title = (video_dict.get("title") or "").strip()
        if not existing.title and new_title:
            existing.title = new_title[:500]
        new_thumb = (video_dict.get("thumbnail_url") or "").strip()
        if not existing.thumbnail_url and new_thumb:
            existing.thumbnail_url = new_thumb
        return False

    row = YouTubeVideo(
        video_id=vid_id,
        title=(video_dict.get("title") or "")[:500],
        channel_name=video_dict.get("channel_name", ""),
        channel_url=video_dict.get("channel_url", ""),
        thumbnail_url=video_dict.get("thumbnail_url", ""),
        description_snippet=video_dict.get("description", ""),
        video_url=video_dict.get("video_url", f"https://www.youtube.com/watch?v={vid_id}"),
        published_at=_parse_date(video_dict.get("published_at", "")),
        duration_seconds=int(video_dict.get("duration_seconds") or 0),
        view_count=int(video_dict.get("view_count") or 0),
        matched_ticker=video_dict.get("matched_ticker"),
        source=video_dict.get("source", "channel_harvest"),
        sebi_reg=video_dict.get("sebi_reg"),
        harvested_at=datetime.now(timezone.utc),
    )
    db.add(row)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CHANNEL HARVEST — Latest videos from each SEBI-registered channel
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_channel_via_api(channel: dict, max_videos: int = 10) -> list[dict]:
    """Fetches the latest videos from a channel using the YouTube Data API v3.

    Args:
        channel (dict): The channel dictionary from the registry.
        max_videos (int, optional): The maximum number of videos to fetch. Defaults to 10.

    Returns:
        list[dict]: A list of video dictionaries.
    """
    if not YOUTUBE_API_AVAILABLE:
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "q": channel["name"],
                "type": "channel",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [])
        if not items:
            return []
        channel_id = items[0]["id"]["channelId"]
    except Exception as e:
        logger.warning(f"[API] Channel ID lookup failed for {channel['name']}: {e}")
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "maxResults": max_videos,
                "regionCode": "IN",
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        if resp.status_code == 403:
            logger.warning("[API] Quota exhausted — falling back to yt-dlp")
            return []
        if resp.status_code != 200:
            return []

        videos = []
        for item in resp.json().get("items", []):
            vid_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            if not vid_id:
                continue
            videos.append({
                "video_id": vid_id,
                "title": snippet.get("title", ""),
                "channel_name": channel["name"],
                "channel_url": channel["channel_url"],
                "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "video_url": f"https://www.youtube.com/watch?v={vid_id}",
                "published_at": snippet.get("publishedAt", ""),
                "description": snippet.get("description", ""),
                "description": snippet.get("description", ""),
                "duration_seconds": 0,
                "view_count": 0,
                "source": "channel_harvest",
                "sebi_reg": channel.get("sebi_reg"),
            })
        return videos
    except Exception as e:
        logger.warning(f"[API] Channel video fetch failed for {channel['name']}: {e}")
        return []


def _fetch_channel_via_ytdlp(channel: dict, max_videos: int = 10) -> list[dict]:
    """Fetches the latest videos from a channel using yt-dlp as a fallback.

    Args:
        channel (dict): The channel dictionary from the registry.
        max_videos (int, optional): The maximum number of videos to fetch. Defaults to 10.

    Returns:
        list[dict]: A list of video dictionaries.
    """
    opts = {
        "quiet": True,
        "extract_flat": True,
        "playlist_items": f"1-{max_videos}",
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(channel["channel_url"], download=False)
            entries = info.get("entries") or []
            videos = []
            for e in entries:
                vid_id = e.get("id") or ""
                if not vid_id:
                    continue
                videos.append({
                    "video_id": vid_id,
                    "title": e.get("title", ""),
                    "channel_name": channel["name"],
                    "channel_url": channel["channel_url"],
                    "thumbnail_url": f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg",
                    "video_url": f"https://www.youtube.com/watch?v={vid_id}",
                    "published_at": str(e.get("upload_date", "")),
                "description": "",
                    "duration_seconds": int(e.get("duration") or 0),
                    "view_count": int(e.get("view_count") or 0),
                    "source": "channel_harvest",
                    "sebi_reg": channel.get("sebi_reg"),
                })
            return videos
    except Exception as e:
        logger.warning(f"[yt-dlp] Channel fetch failed for {channel['name']}: {e}")
        return []


async def harvest_youtube_metadata() -> dict:
    """Nightly channel sweep that fetches latest videos from all SEBI-registered channels.

    Uses API v3 if available, falls back to yt-dlp per channel.

    Returns:
        dict: Summary of the harvest containing 'channels_processed', 'total_channels',
            and 'videos_added'.
    """
    total_added = 0
    channels_ok = 0

    with get_session() as db:
        try:
            for channel in CHANNEL_REGISTRY:
                videos = _fetch_channel_via_api(channel, max_videos=10)
                if not videos:
                    videos = _fetch_channel_via_ytdlp(channel, max_videos=10)

                if not videos:
                    logger.warning(f"[Harvest] No videos returned for {channel['name']}")
                    continue

                channels_ok += 1
                added = 0
                for v in videos:
                    if _upsert_video(db, v):
                        added += 1

                db.commit()
                logger.info(f"[Harvest] {channel['name']}: {added} new videos added")
                total_added += added
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"[Harvest ERROR] {e}")
            db.rollback()

    return {
        "channels_processed": channels_ok,
        "total_channels": len(CHANNEL_REGISTRY),
        "videos_added": total_added,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO HARVEST — Tag registry videos with the held tickers they mention
# ─────────────────────────────────────────────────────────────────────────────

async def harvest_portfolio_videos() -> dict:
    """Tags already-harvested registry videos with the portfolio tickers they mention.

    Searches nothing (REG-03): for every unique ticker held across all portfolios,
    untagged rows from SEBI-registered channels whose title names the company or the
    ticker as a whole word get matched_ticker set.

    Returns:
        dict: A summary containing 'tickers_processed', 'videos_added' (rows tagged), and a
            'by_ticker' breakdown. May contain 'error' if an exception is caught.
    """
    import re
    total_added = 0

    with get_session() as db:
        try:
            tickers = sorted({t.upper() for (t,) in db.query(Portfolio.ticker).distinct() if t})

            if not tickers:
                logger.info("[Portfolio Harvest] No holdings found — skipping")
                return {"tickers_processed": 0, "videos_added": 0}

            logger.info(f"[Portfolio Harvest] Tagging registry videos for {len(tickers)} tickers")
            by_ticker = {}

            for ticker in tickers:
                company_name = get_company_name(ticker)
                terms = {company_name, ticker}
                pattern = re.compile(
                    "|".join(rf"(?<!\w){re.escape(t)}(?!\w)" for t in terms), re.IGNORECASE
                )
                candidates = (
                    db.query(YouTubeVideo)
                    .filter(
                        YouTubeVideo.sebi_reg.isnot(None),
                        YouTubeVideo.matched_ticker.is_(None),
                        or_(*(YouTubeVideo.title.ilike(f"%{t}%") for t in terms)),
                    )
                    .all()
                )
                added = 0
                for video in candidates:
                    if pattern.search(str(video.title or "")):
                        video.matched_ticker = ticker
                        added += 1
                if added:
                    db.commit()

                by_ticker[ticker] = added
                total_added += added
                logger.info(f"[Portfolio Harvest] {ticker} ({company_name}): {added} tagged")

        except Exception as e:
            logger.error(f"[Portfolio Harvest ERROR] {e}")
            db.rollback()
            return {"tickers_processed": 0, "videos_added": 0, "error": str(e)}

    return {
        "tickers_processed": len(tickers),
        "videos_added": total_added,
        "by_ticker": by_ticker,
    }
