"""
Nivesh Sentiment Engine
Runs FinBERT sentiment scoring on news article headlines and summaries.
Loads the model once at module import time and reuses it (singleton pattern).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_classifier = None


def get_classifier():
    """Load FinBERT once and cache it. Thread-safe for single-process use."""
    global _classifier
    if _classifier is None:
        try:
            from transformers import pipeline
            logger.info("Loading FinBERT model (first load ~3-5s)...")
            _classifier = pipeline(
                "text-classification",
                model="yiyanghkust/finbert-tone",
                device=-1,
                truncation=True,
                max_length=512,
            )
            logger.info("FinBERT loaded successfully.")
        except Exception as e:
            logger.error(f"FinBERT load failed: {e}")
            _classifier = None
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
