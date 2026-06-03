"""
Nivesh News Harvester
Scrapes Moneycontrol + ET for financial news articles.
Run nightly. Never called from request handlers.
"""
import feedparser
from newspaper import Article
from datetime import datetime, timedelta
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
        "url": "https://www.moneycontrol.com/rss/latestnews.xml",
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

def extract_tickers_from_text(text: str, db: Session) -> list[str]:
    """
    Use the existing ticker_matcher to find mentioned tickers.
    """
    try:
        from services.ticker_matcher import ALIAS_TO_TICKER
        text_lower = text.lower()
        found_tickers = []
        for alias, ticker in ALIAS_TO_TICKER.items():
            if alias in text_lower and ticker not in found_tickers:
                found_tickers.append(ticker)
        return found_tickers[:5]
    except Exception as e:
        logger.warning(f"Ticker extraction failed: {e}")
        return []

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

async def harvest_news(lookback_hours: int = 26):
    """Main harvest entry point. Called by nightly CRON."""
    from database import get_session
    articles_added = 0

    with get_session() as db:
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        for feed_config in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_config["url"])
                for entry in feed.entries[:20]:  # Max 20 per feed
                    savepoint = db.begin_nested()
                    try:
                        # Skip if already in DB (unique constraint on article_url)
                        url = entry.get("link", "")
                        if not url:
                            continue

                        existing = db.query(NewsArticle).filter(
                            NewsArticle.article_url == url
                        ).first()
                        if existing:
                            continue

                        # Parse publish date
                        try:
                            pub_date = datetime(*entry.published_parsed[:6]) \
                                if hasattr(entry, 'published_parsed') and entry.published_parsed \
                                else datetime.utcnow()
                        except (TypeError, AttributeError, ValueError):
                            pub_date = datetime.utcnow()

                        if pub_date < cutoff:
                            continue

                        headline = entry.get("title", "").strip()
                        summary = entry.get("summary", "").strip()[:500]

                        # Scrape full body + image
                        body, image_url = scrape_article_body(url)

                        full_text = f"{headline} {summary} {body}"

                        article = NewsArticle(
                            source=feed_config["source"],
                            ticker=None,
                            headline=headline,
                            summary=summary,
                            body_text=body,
                            image_url=image_url,
                            article_url=url,
                            published_at=pub_date,
                            sentiment=None,
                            is_red_flag=is_red_flag(full_text),
                        )
                        db.add(article)
                        db.commit()
                        db.refresh(article)

                        # Ticker matching
                        tickers = extract_tickers_from_text(full_text, db)
                        if tickers:
                            article.ticker = tickers[0]

                        # Score with FinBERT
                        try:
                            label, score = score_article(headline, summary)
                            article.sentiment_label = label
                            article.sentiment_score = score
                            article.sentiment = label.upper()
                        except Exception as e:
                            logger.warning(f"Sentiment scoring failed for article: {e}")

                        db.commit()

                        articles_added += 1
                        logger.info(f"Added: {headline[:60]}")

                    except Exception as e:
                        logger.warning(f"Article processing error: {e}")
                        savepoint.rollback()
                        continue
                    else:
                        savepoint.commit()

            except Exception as e:
                logger.error(f"Feed error for {feed_config['url']}: {e}")
                continue

    logger.info(f"News harvest complete. {articles_added} articles added.")
    return articles_added
