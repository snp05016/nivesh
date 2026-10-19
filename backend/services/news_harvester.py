"""
Nivesh News Harvester
Scrapes Moneycontrol + ET for financial news articles.
Run nightly. Never called from request handlers.
"""
import feedparser
import requests
from newspaper import Article
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import SessionLocal, NewsArticle
from services.sentiment_engine import score_article

logger = logging.getLogger(__name__)

# ── RSS Feed Targets ──────────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "source": "moneycontrol",
        "url": "https://www.moneycontrol.com/rss/business.xml",
        "category": "market",
    },
    {
        "source": "moneycontrol",
        "url": "https://www.moneycontrol.com/rss/marketreports.xml",
        "category": "market",
    },
    {
        "source": "economic_times",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "category": "market",
    },
    {
        "source": "economic_times",
        "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "category": "stocks",
    },
    {
        "source": "business_standard",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
        "category": "market",
    },
    {
        "source": "livemint",
        "url": "https://www.livemint.com/rss/markets",
        "category": "market",
    },
    {
        "source": "ndtv_profit",
        "url": "https://feeds.feedburner.com/ndtvprofit-latest",
        "category": "market",
    },
]

# Keywords that mark an article as a red flag
RED_FLAG_KEYWORDS = [
    "auditor resign", "auditor quit", "cfo resign", "cfo quit", "md resign",
    "sebi investigation", "sebi probe", "sebi notice", "promoter pledge",
    "stock suspended", "trading halt", "forensic audit", "fraud", "embezzlement",
    "governance concern", "qualified opinion"
]

def is_red_flag(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in RED_FLAG_KEYWORDS)


# ── Market Relevance Filter ──────────────────────────────────────────────────
# Articles must contain at least one of these keywords to be stored.
# Prevents non-financial content (politics, sports, entertainment) from
# polluting the news feed even if it appears in a market-category RSS feed.
MARKET_KEYWORDS = [
    "stock", "share", "nifty", "sensex", "nse", "bse", "market",
    "investor", "investment", "trading", "trade", "broker", "broking",
    "mutual fund", "etf", "index", "indices", "dividend", "bonus",
    "ipo", "listing", "stake", "acquisition", "merger", "takeover",
    "buyback", "demerger", "rights issue", "bonus issue",
    "revenue", "profit", "ebitda", "earnings", "net profit", "pat",
    "quarterly result", "annual result", "q1", "q2", "q3", "q4",
    "fy24", "fy25", "fy26", "financial year", "quarter",
    "market cap", "market capitalisation", "valuation", "pe ratio",
    "promoter", "holding", "pledged", "fii", "dii", "institutional",
    "rbi", "sebi", "monetary policy", "repo rate", "interest rate",
    "inflation", "gdp", "fiscal deficit", "budget",
    "bull", "bear", "rally", "crash", "correction", "volatility",
    "commodity", "crude oil", "gold price", "silver price",
    "rupee", "forex", "currency", "dollar", "bond yield",
    "sector", "banking", "pharma", "it sector", "auto sector",
    "power sector", "metal", "fmcg", "telecom", "real estate",
    "nifty 50", "bank nifty", "midcap", "smallcap",
    "cagr", "roce", "roe", "debt", "leverage", "cash flow",
    "cfo", "ceo", "md", "chairman", "board", "agm",
    "credit rating", "upgrade", "downgrade", "outlook",
    "brokerage", "target price", "nomura", "morgan stanley",
    "jp morgan", "goldman", "clsa", "jefferies", "macquarie",
    "motilal oswal", "hdfc sec", "icici direct", "kotak",
]

def is_market_relevant(text: str) -> bool:
    """Return True if article text contains financial market keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in MARKET_KEYWORDS)

def extract_tickers_from_text(text: str) -> list[str]:
    """
    Use the existing ticker_matcher to find mentioned tickers.
    Fix 2.8: Enforces exchange-aware suffix filtering — blocks US equities
    sharing identical ticker strings (e.g., IDEA) from polluting Indian feeds.
    """
    try:
        from services.ticker_matcher import ALIAS_TO_TICKER
        from helpers import NSE_TICKERS
        text_lower = text.lower()
        found_tickers = []
        for alias, ticker in ALIAS_TO_TICKER.items():
            if alias in text_lower and ticker not in found_tickers:
                # Only accept tickers known to be NSE/BSE listed
                clean = ticker.replace(".NS", "").replace(".BO", "").upper()
                if clean in NSE_TICKERS or ticker.endswith((".NS", ".BO")):
                    found_tickers.append(ticker)
        return found_tickers[:5]
    except Exception as e:
        logger.warning(f"Ticker extraction failed: {e}")
        return []

def _extract_image_from_entry(entry) -> str | None:
    """Try to pull an image URL from feedparser entry media fields before scraping."""
    # media:content (e.g. Moneycontrol, ET)
    for mc in entry.get("media_content", []):
        url = mc.get("url", "")
        if url and any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
            return url
    # media:thumbnail
    for mt in entry.get("media_thumbnail", []):
        url = mt.get("url", "")
        if url:
            return url
    # enclosures (podcast-style feeds sometimes use these for images)
    for enc in entry.get("enclosures", []):
        if "image" in enc.get("type", ""):
            return enc.get("href") or enc.get("url")
    return None


def scrape_article_body(url: str) -> tuple[str, str | None]:
    """
    Returns (body_text, image_url) for a given article URL.
    Uses newspaper3k. Times out at 10 seconds.
    """
    try:
        article = Article(url, request_timeout=10)
        article.download()
        article.parse()
        image = article.top_image if article.top_image else None
        return article.text[:8000], image  # Cap at 8k chars
    except Exception as e:
        logger.warning(f"Body scrape failed for {url}: {e}")
        return "", None

_FEED_TIMEOUT_SEC = 15


async def harvest_news(lookback_hours: int = 26):
    """Main harvest entry point. Called by nightly CRON.

    No DB session is open while feeds download, bodies scrape or FinBERT scores
    (DB-22): one short read per feed drops known URLs, then each fully built
    article is inserted in its own short write session.
    """
    from database import get_session
    from sqlalchemy.exc import IntegrityError
    articles_added = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    for feed_config in RSS_FEEDS:
        try:
            # feedparser.parse(url) has no timeout: a hung feed server stalled the job forever.
            resp = requests.get(feed_config["url"], timeout=_FEED_TIMEOUT_SEC,
                                headers={"User-Agent": "Mozilla/5.0 (Nivesh RSS)"})
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            entries = [e for e in feed.entries[:20] if e.get("link", "")]  # Max 20 per feed
            if not entries:
                # SILENT-18: a dead or malformed feed must be visible, not a silent zero.
                logger.warning("[news] feed %s (%s) yielded no entries: bozo=%s %s",
                               feed_config["source"], feed_config["url"],
                               getattr(feed, "bozo", 0), getattr(feed, "bozo_exception", ""))
                continue

            # Skip URLs already in DB (unique constraint on article_url)
            with get_session() as db:
                known = {
                    u for (u,) in db.query(NewsArticle.article_url).filter(
                        NewsArticle.article_url.in_([e.get("link") for e in entries])
                    )
                }

            for entry in entries:
                try:
                    url = str(entry.get("link", ""))
                    if url in known:
                        continue
                    known.add(url)

                    # Parse publish date
                    try:
                        pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc) \
                            if hasattr(entry, 'published_parsed') and entry.published_parsed \
                            else datetime.now(timezone.utc)
                    except (TypeError, AttributeError, ValueError):
                        pub_date = datetime.now(timezone.utc)

                    if pub_date < cutoff:
                        continue

                    headline = entry.get("title", "").strip()
                    summary = entry.get("summary", "").strip()[:500]

                    # Try feed-level image first (fast, no HTTP request)
                    image_url = _extract_image_from_entry(entry)

                    # Scrape full body + image (newspaper3k fills image if feed had none)
                    body, scraped_image = scrape_article_body(url)
                    if not image_url:
                        image_url = scraped_image

                    full_text = f"{headline} {summary} {body}"

                    # Skip non-market articles (politics, sports, entertainment, etc.)
                    if not is_market_relevant(full_text):
                        logger.debug(f"Skipped non-market article: {headline[:60]}")
                        continue

                    tickers = extract_tickers_from_text(full_text)
                    article = NewsArticle(
                        source=feed_config["source"],
                        ticker=tickers[0] if tickers else None,
                        headline=headline,
                        summary=summary,
                        body_text=body,
                        image_url=image_url,
                        article_url=url,
                        published_at=pub_date,
                        sentiment=None,
                        is_red_flag=is_red_flag(full_text),
                    )

                    # Score with FinBERT
                    try:
                        label, score = score_article(headline, summary)
                        article.sentiment_label = label
                        article.sentiment_score = score
                        article.sentiment = label.upper()
                    except Exception as e:
                        logger.warning(f"Sentiment scoring failed for article: {e}")

                    with get_session() as db:
                        try:
                            db.add(article)
                            db.commit()
                        except IntegrityError:
                            db.rollback()  # inserted by a concurrent run
                            continue
                    articles_added += 1
                    logger.info(f"Added: {headline[:60]}")

                except Exception as e:
                    logger.warning(f"Article processing error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Feed error for {feed_config['url']}: {e}")
            continue

    logger.info(f"News harvest complete. {articles_added} articles added.")
    return articles_added
