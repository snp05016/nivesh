"""
Nivesh Sentiment Engine
Runs FinBERT sentiment scoring on news article headlines and summaries.
Loads the model once at module import time and reuses it (singleton pattern).
"""
from datetime import timezone
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_classifier = None
_classifier_lock = threading.Lock()
_load_failed_at: float | None = None
_RETRY_AFTER_SEC = 600  # one load attempt per 10 min after a failure, not one per article


def get_classifier():
    """Load FinBERT once and cache it. Thread-safe; a failed load is retried at most every _RETRY_AFTER_SEC."""
    global _classifier, _load_failed_at
    if _classifier is not None:
        return _classifier
    with _classifier_lock:
        if _classifier is not None:
            return _classifier
        if _load_failed_at is not None and time.monotonic() - _load_failed_at < _RETRY_AFTER_SEC:
            return None
        try:
            from transformers import pipeline
            # yiyanghkust/finbert-tone incompatible with transformers 5.x
            # ProsusAI/finbert is PyTorch-native and actively maintained
            logger.info("Loading FinBERT model (ProsusAI/finbert)...")
            _classifier = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                device=-1,
                truncation=True,
                max_length=512,
                token=os.getenv("HF_TOKEN"),
            )
            _load_failed_at = None
            logger.info("FinBERT loaded successfully (ProsusAI/finbert).")
        except Exception as e:
            logger.warning(f"FinBERT load failed: {e}")
            _classifier = None
            _load_failed_at = time.monotonic()
    return _classifier


def score_article(headline: str, summary: Optional[str] = None) -> tuple:
    """
    Score a news article using FinBERT.
    Returns (label, score) where label is Positive/Negative/Neutral
    and score is -1.0 to +1.0.
    """
    clf = get_classifier()
    if clf is None:
        return ("Neutral", 0.0)

    text = headline.strip()
    if summary:
        text = f"{text}. {summary.strip()}"
    text = text[:1200]

    try:
        result = clf(text)[0]
        label = result["label"]
        confidence = result["score"]

        if label == "Positive":
            signed_score = round(confidence, 4)
        elif label == "Negative":
            signed_score = round(-confidence, 4)
        else:
            signed_score = 0.0

        # Fix 2.7: detect financial sarcasm and adjust score.
        # Phrases like "Another stellar performance: debt is up 400%"
        # confuse FinBERT into positive scoring on negative content.
        text_lower = text.lower()
        _sarcasm_markers = [
            "another stellar", "yet another brilliant", "once again amazing",
            "debt is up", "losses widened", "revenue collapsed",
            "stock crashed", "fraud revealed", "bankruptcy",
        ]
        _sarcasm_hits = sum(1 for m in _sarcasm_markers if m in text_lower)
        if _sarcasm_hits >= 2:
            signed_score = -signed_score
            label = "Negative" if signed_score < 0 else "Positive"

        return (label, signed_score)
    except Exception as e:
        logger.warning(f"FinBERT inference error: {e}")
        return ("Neutral", 0.0)


def score_articles_batch(articles: list) -> list:
    """
    Score multiple articles efficiently using FinBERT batch inference.
    Each article dict must have 'headline' and optionally 'summary'.
    """
    clf = get_classifier()
    if clf is None:
        return [("Neutral", 0.0)] * len(articles)

    texts = []
    for a in articles:
        text = a.get("headline", "").strip()
        if a.get("summary"):
            text = f"{text}. {a['summary'].strip()}"
        texts.append(text[:1200])

    try:
        results = clf(texts)
        output = []
        for r in results:
            label = r["label"]
            conf = r["score"]
            if label == "Positive":
                output.append((label, round(conf, 4)))
            elif label == "Negative":
                output.append((label, round(-conf, 4)))
            else:
                output.append(("Neutral", 0.0))
        return output
    except Exception as e:
        logger.warning(f"FinBERT batch error: {e}")
        return [("Neutral", 0.0)] * len(articles)


async def backfill_existing_articles():
    """
    Backfill sentiment scores for existing news articles in the database.

    Iteratively fetches articles missing sentiment scores and processes them
    in batches using the FinBERT model.

    Returns:
        int: The total number of articles updated.
    """
    from database import NewsArticle
    from database import get_session
    updated = 0

    with get_session() as db:
        offset = 0
        while True:
            batch = db.query(NewsArticle).filter(
                NewsArticle.sentiment_score == None
            ).limit(50).offset(offset).all()

            if not batch:
                break

            article_dicts = [
                {"headline": a.headline, "summary": a.summary}
                for a in batch
            ]
            scores = score_articles_batch(article_dicts)

            for article, (label, score) in zip(batch, scores):
                article.sentiment_label = label
                article.sentiment_score = score

            db.commit()
            updated += len(batch)
            logger.info(f"Backfill progress: {updated} articles scored")
            offset += len(batch)

    logger.info(f"Backfill complete. {updated} articles scored.")
    return updated

def get_sentiment_trend(ticker: str, days: int = 30):
    """
    Retrieve the historical sentiment trend for a specific ticker.

    Args:
        ticker (str): The stock ticker symbol.
        days (int): The number of days to look back. Defaults to 30.

    Returns:
        list[dict]: A list of daily sentiment aggregations, each containing the date,
        average sentiment score, article count, and a descriptive label.
    """
    from database import get_session, NewsArticle
    from datetime import datetime, timedelta
    from sqlalchemy import and_, or_, func, cast, Date

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    with get_session() as db:
        # date() works on both dialects (SQLite: 'YYYY-MM-DD' text, Postgres: date);
        # substr() on a timestamp does not exist on Postgres (DB-15).
        date_expr = func.date(NewsArticle.published_at)
        
        results = db.query(
            date_expr.label('date_str'),
            func.avg(NewsArticle.sentiment_score).label('avg_score'),
            func.count(NewsArticle.id).label('article_count')
        ).filter(
            NewsArticle.published_at >= cutoff.replace(tzinfo=None),
            or_(
                NewsArticle.ticker == ticker,
                NewsArticle.headline.like(f"%{ticker}%")
            )
        ).group_by(
            date_expr
        ).order_by(
            date_expr
        ).all()
        
        trend = []
        for r in results:
            avg_score = float(r.avg_score) if r.avg_score else 0.0
            label = 'Neutral'
            if avg_score > 0.1:
                label = 'Positive'
            elif avg_score < -0.1:
                label = 'Negative'
                
            trend.append({
                "date": str(r.date_str)[:10],
                "avg_score": round(avg_score, 4),
                "article_count": r.article_count,
                "label": label
            })
            
        return trend
