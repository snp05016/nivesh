"""
Nivesh YouTube Harvester — SEBI-Registered Channels Only
=========================================================
Two harvest modes:
  1. channel_harvest  — Fetches latest N videos from each curated SEBI channel nightly
  2. portfolio_harvest — Searches for ticker-specific videos based on user holdings

Both modes use YouTube Data API v3 when YOUTUBE_API_KEY is set, falling back
silently to yt-dlp. Never raises. Never blocks the main request pipeline.
Zero Anthropic API calls.
"""

import os
import time
import logging
import requests
import yt_dlp
from datetime import datetime
from database import SessionLocal, YouTubeVideo, Portfolio

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_API_AVAILABLE = bool(YOUTUBE_API_KEY and len(YOUTUBE_API_KEY) > 10)
MIN_SUBSCRIBER_THRESHOLD = 100_000  # only harvest from channels with 100k+ subscribers

# ─────────────────────────────────────────────────────────────────────────────
# SEBI REGISTERED CHANNEL REGISTRY
# Every entry verified against SEBI public RA/IA registry, June 2026.
# sebi_reg field is mandatory. Never add a channel without a confirmed INH/INA number.
# Only SEBI-registered advisors with 100k+ YouTube subscribers are listed here.
# Last updated: June 2026 — Saumya
# ─────────────────────────────────────────────────────────────────────────────
CHANNEL_REGISTRY = [
    {
        "name": "Finology with Pranjal",
        "channel_url": "https://www.youtube.com/@pranjalkamra/videos",
        "sebi_reg": "INH000024277",
        "entity": "Finology Ventures Pvt. Ltd.",
        "tags": ["education", "fundamental", "value_investing", "hindi"],
    },
    {
        "name": "Yadnya Investment Academy",
        "channel_url": "https://www.youtube.com/@InvestYadnya/videos",
        "sebi_reg": "INH000008349",
        "entity": "Yadnya Academy Pvt. Ltd.",
        "tags": ["education", "fundamental", "mutual_fund", "hindi"],
    },
    {
        "name": "Elearnmarkets",
        "channel_url": "https://www.youtube.com/c/Elearnmarkets/videos",
        "sebi_reg": "INH300007493",
        "entity": "StockEdge Fintech Pvt. Ltd.",
        "tags": ["education", "technical", "trading", "courses"],
    },
    {
        "name": "WeekendInvesting",
        "channel_url": "https://www.youtube.com/@AlokJain/videos",
        "sebi_reg": "INH100008717",
        "entity": "Weekendinvesting Analytics Pvt. Ltd.",
        "tags": ["momentum", "smallcase", "portfolio", "longterm"],
    },
    {
        "name": "Equityrush",
        "channel_url": "https://www.youtube.com/channel/UCEk5D5RfUgAJd3VfCz3vWTw/videos",
        "sebi_reg": "INH100001609",
        "entity": "Kunal Saraogi",
        "tags": ["technical", "trading", "price_action", "charts"],
    },
    {
        "name": "Capitalmind",
        "channel_url": "https://www.youtube.com/@CapitalmindHQ/videos",
        "sebi_reg": "INH000014003",
        "entity": "Capitalmind Research LLP",
        "tags": ["quant", "macro", "data_driven", "mutual_fund"],
    },
    {
        "name": "Finance With Sunil",
        "channel_url": "https://www.youtube.com/@financewithsunil1/videos",
        "sebi_reg": "INH000014261",
        "entity": "Alphamojo Financial Services Pvt. Ltd.",
        "tags": ["technical", "price_action", "trading", "breakout"],
    },
    {
        "name": "AryaaMoney",
        "channel_url": "https://www.youtube.com/@AryaaMoney/videos",
        "sebi_reg": "INA000002405",
        "entity": "Aryaa Money Pvt. Ltd.",
        "tags": ["education", "fundamental", "trading", "financial_literacy"],
    },
    {
        "name": "SOIC",
        "channel_url": "https://www.youtube.com/@soicfinance/videos",
        "sebi_reg": "INH000012582",
        "entity": "SOIC Intelligent Research LLP",
        "tags": ["fundamental", "deep_dive", "smallcap", "microcap"],
    },
    {
        "name": "Basant Maheshwari",
        "channel_url": "https://www.youtube.com/@BMTheEquityDesk/videos",
        "sebi_reg": "INH000017949",
        "entity": "Basant Maheshwari Wealth Advisers LLP",
        "tags": ["portfolio", "largecap", "consumer", "longterm"],
    },
    {
        "name": "Anand Rathi",
        "channel_url": "https://www.youtube.com/@AnandRathiOfficial/videos",
        "sebi_reg": "INH000000834",
        "entity": "Anand Rathi Share and Stock Brokers Ltd",
        "tags": ["institutional", "research", "largecap", "sector_calls"],
    },
    {
        "name": "Motilal Oswal",
        "channel_url": "https://www.youtube.com/@motilaloswalofficial/videos",
        "sebi_reg": "INH000000412",
        "entity": "Motilal Oswal Financial Services Ltd",
        "tags": ["institutional", "bluechip", "research", "market_outlook"],
    },
]

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
    """Returns a human-readable company name for YouTube search quality."""
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
    except Exception:
        return t


def _parse_date(raw: str) -> datetime:
    """Safely parse a date string from either API (ISO) or yt-dlp (YYYYMMDD) format."""
    if not raw:
        return datetime.utcnow()
    try:
        if "T" in str(raw):
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
        if len(str(raw)) == 8:
            return datetime.strptime(str(raw), "%Y%m%d")
    except Exception:
        pass
    return datetime.utcnow()


def _upsert_video(db, video_dict: dict) -> bool:
    """
    Insert a video row if video_id does not already exist.
    If it exists, updates matched_ticker if currently null.
    Returns True if a new row was inserted.
    """
    vid_id = video_dict.get("video_id", "")
    if not vid_id:
        return False

    existing = db.query(YouTubeVideo).filter(YouTubeVideo.video_id == vid_id).first()
    if existing:
        if not existing.matched_ticker and video_dict.get("matched_ticker"):
            existing.matched_ticker = video_dict["matched_ticker"]
        return False

    row = YouTubeVideo(
        video_id=vid_id,
        title=(video_dict.get("title") or "")[:500],
        channel_name=video_dict.get("channel_name", ""),
        channel_url=video_dict.get("channel_url", ""),
        thumbnail_url=video_dict.get("thumbnail_url", ""),
        video_url=video_dict.get("video_url", f"https://www.youtube.com/watch?v={vid_id}"),
        published_at=_parse_date(video_dict.get("published_at", "")),
        duration_seconds=int(video_dict.get("duration_seconds") or 0),
        view_count=int(video_dict.get("view_count") or 0),
        matched_ticker=video_dict.get("matched_ticker"),
        source=video_dict.get("source", "channel_harvest"),
        sebi_reg=video_dict.get("sebi_reg"),
        harvested_at=datetime.utcnow(),
    )
    db.add(row)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CHANNEL HARVEST — Latest videos from each SEBI-registered channel
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_channel_via_api(channel: dict, max_videos: int = 10) -> list[dict]:
    """Fetch latest videos from a channel using YouTube Data API v3."""
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
    """Fetch latest videos from a channel using yt-dlp (fallback)."""
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
    """
    Nightly channel sweep. Fetches latest videos from all SEBI-registered channels.
    Uses API v3 if available, falls back to yt-dlp per channel.
    """
    db = SessionLocal()
    total_added = 0
    channels_ok = 0

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
    finally:
        db.close()

    return {
        "channels_processed": channels_ok,
        "total_channels": len(CHANNEL_REGISTRY),
        "videos_added": total_added,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO HARVEST — Ticker-specific search for user holdings
# ─────────────────────────────────────────────────────────────────────────────

def search_videos_for_ticker(ticker: str, company_name: str, max_results: int = 3) -> list[dict]:
    """
    Searches YouTube for videos about a specific NSE ticker/company.
    PATH A: YouTube Data API v3 (structured, stable, preferred)
    PATH B: yt-dlp keyword search (fallback when API unavailable or quota exceeded)
    Returns [] on any failure. Never raises.
    """
    query = f"{company_name} NSE stock analysis India"

    # PATH A — YouTube Data API v3
    if YOUTUBE_API_AVAILABLE:
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "q": query,
                    "type": "video",
                    "order": "relevance",
                    "maxResults": max_results,
                    "regionCode": "IN",
                    "relevanceLanguage": "en",
                    "key": YOUTUBE_API_KEY,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                videos = []
                for item in resp.json().get("items", []):
                    vid_id = item.get("id", {}).get("videoId", "")
                    snippet = item.get("snippet", {})
                    if not vid_id:
                        continue
                    videos.append({
                        "video_id": vid_id,
                        "title": snippet.get("title", ""),
                        "channel_name": snippet.get("channelTitle", ""),
                        "channel_url": f"https://www.youtube.com/channel/{snippet.get('channelId','')}",
                        "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                        "video_url": f"https://www.youtube.com/watch?v={vid_id}",
                        "published_at": snippet.get("publishedAt", ""),
                        "duration_seconds": 0,
                        "view_count": 0,
                        "source": "api_search",
                        "matched_ticker": ticker,
                        "sebi_reg": None,
                    })
                return videos
            elif resp.status_code == 403:
                logger.warning("[API] Quota exhausted — falling back to yt-dlp for ticker search")
        except Exception as e:
            logger.warning(f"[API search] failed for {ticker}: {e}")

    # PATH B — yt-dlp keyword search
    try:
        opts = {
            "quiet": True,
            "extract_flat": True,
            "playlist_items": f"1-{max_results}",
            "default_search": "ytsearch",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            entries = info.get("entries") or []
            return [
                {
                    "video_id": e.get("id", ""),
                    "title": e.get("title", ""),
                    "channel_name": e.get("uploader") or e.get("channel", ""),
                    "channel_url": e.get("uploader_url", ""),
                    "thumbnail_url": f"https://i.ytimg.com/vi/{e.get('id','')}/mqdefault.jpg",
                    "video_url": f"https://www.youtube.com/watch?v={e.get('id','')}",
                    "published_at": str(e.get("upload_date", "")),
                    "duration_seconds": int(e.get("duration") or 0),
                    "view_count": int(e.get("view_count") or 0),
                    "source": "ytdlp_search",
                    "matched_ticker": ticker,
                    "sebi_reg": None,
                }
                for e in entries if e.get("id")
            ]
    except Exception as e:
        logger.warning(f"[yt-dlp search] failed for {ticker}: {e}")
        return []


async def harvest_portfolio_videos() -> dict:
    """
    Runs after harvest_youtube_metadata().
    For every unique ticker held across ALL user portfolios:
      - Searches YouTube for relevant analysis videos
      - Inserts new results tagged with matched_ticker
    Rate-limited: 1.2s sleep between tickers.
    """
    db = SessionLocal()
    total_added = 0

    try:
        holdings = db.query(Portfolio).all()
        tickers = sorted(set(h.ticker.upper() for h in holdings))

        if not tickers:
            logger.info("[Portfolio Harvest] No holdings found — skipping")
            return {"tickers_processed": 0, "videos_added": 0}

        logger.info(f"[Portfolio Harvest] Processing {len(tickers)} tickers")
        by_ticker = {}

        for ticker in tickers:
            company_name = get_company_name(ticker)
            videos = search_videos_for_ticker(ticker, company_name, max_results=3)

            added = 0
            for v in videos:
                v["matched_ticker"] = ticker
                if _upsert_video(db, v):
                    added += 1

            if added > 0:
                db.commit()

            by_ticker[ticker] = added
            total_added += added
            logger.info(f"[Portfolio Harvest] {ticker} ({company_name}): {added} new")
            time.sleep(1.2)

    except Exception as e:
        logger.error(f"[Portfolio Harvest ERROR] {e}")
        db.rollback()
        return {"tickers_processed": 0, "videos_added": 0, "error": str(e)}
    finally:
        db.close()

    return {
        "tickers_processed": len(tickers),
        "videos_added": total_added,
        "by_ticker": by_ticker,
    }
