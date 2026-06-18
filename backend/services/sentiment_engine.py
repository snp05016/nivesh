"""
Nivesh Sentiment Engine
Runs FinBERT sentiment scoring on news article headlines and summaries.
Loads the model once at module import time and reuses it (singleton pattern).
"""
from datetime import timezone
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
            # yiyanghkust/finbert-tone incompatible with transformers 5.x
            # ProsusAI/finbert is PyTorch-native and actively maintained
            logger.info("Loading FinBERT model (ProsusAI/finbert)...")
            _classifier = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                device=-1,
                truncation=True,
                max_length=512,
            )
            logger.info("FinBERT loaded successfully (ProsusAI/finbert).")
        except Exception as e:
            logger.warning(f"FinBERT load failed: {e}")
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
    from database import get_session, NewsArticle
    from datetime import datetime, timedelta
    from sqlalchemy import and_, or_, func, cast, Date

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    with get_session() as db:
        # SQLite datetime casting workaround: substr(published_at, 1, 10)
        date_expr = func.substr(NewsArticle.published_at, 1, 10)
        
        results = db.query(
            date_expr.label('date_str'),
            func.avg(NewsArticle.sentiment_score).label('avg_score'),
            func.count(NewsArticle.id).label('article_count')
        ).filter(
            NewsArticle.published_at >= cutoff.isoformat(),
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
                "date": r.date_str,
                "avg_score": round(avg_score, 4),
                "article_count": r.article_count,
                "label": label
            })
            
        return trend


def compute_cisi(
    ticker: str,
    indicators: dict = None,
    microstructure: dict = None,
) -> dict:
    """
    Composite Investor Sentiment Index (CISI) via PCA.
    Aggregates 5 sentiment proxies into a single -100 to +100 score.
    """
    try:
        # -- 1. Collect 5 sentiment proxies --
        # 1a. Text sentiment from NewsArticle DB
        from database import get_session, NewsArticle
        topic_scores = []
        with get_session() as db:
            rows = db.query(NewsArticle.sentiment_score).filter(
                NewsArticle.ticker == ticker,
                NewsArticle.sentiment_score != None,
            ).limit(50).all()
            topic_scores = [float(r.sentiment_score) for r in rows if r.sentiment_score is not None]
        text_sentiment_score = 0.0
        if topic_scores:
            text_sentiment_score = max(-1.0, min(1.0, sum(topic_scores) / len(topic_scores)))

        # Normalize text_sentiment from [-1, 1] to [0, 1]
        text_norm = (text_sentiment_score + 1.0) / 2.0

        # 1b. IPO Froth Score (placeholder)
        ipo_froth_score = 0.0  # hardcoded until scraped data available

        # 1c. F&O Retail Skew from microstructure
        fo_retail_skew = 0.0
        if microstructure and isinstance(microstructure, dict):
            fo_retail_skew = float(microstructure.get("fo_retail_skew", 0.0))

        # 1d. PE Expansion Velocity from indicators
        pe_expansion_velocity = 0.0
        if indicators and isinstance(indicators, dict):
            pe_expansion_velocity = float(indicators.get("pe_expansion_velocity", 0.0))

        # 1e. Social Buzz Index (placeholder)
        social_buzz_index = 0.0

        # -- 2. Normalize all inputs to [0, 1] --
        # fo_retail_skew: typically -1..1 → 0..1
        fo_norm = (fo_retail_skew + 1.0) / 2.0
        # pe_expansion_velocity: clip to [-10, 10] then 0..1
        pe_clipped = max(-10.0, min(10.0, pe_expansion_velocity))
        pe_norm = (pe_clipped + 10.0) / 20.0
        # social_buzz: already 0..1
        social_norm = max(0.0, min(1.0, social_buzz_index))

        X = [[text_norm, ipo_froth_score, fo_norm, pe_norm, social_norm]]

        # -- 3. PCA --
        from sklearn.decomposition import PCA
        import numpy as np
        pca = PCA(n_components=1)
        pc1 = pca.fit_transform(np.array(X))[0, 0]

        # Map PC1 to -100..+100 (first component typically captures ~30-60% variance;
        # map via tanh to keep range bounded)
        import math
        raw = math.tanh(pc1) * 100.0
        cisi_score = round(max(-100.0, min(100.0, raw)), 2)

    except Exception:
        logger.warning("CISI computation failed, returning neutral", exc_info=True)
        return {
            "cisi_score": 0.0,
            "cisi_label": "NORMAL",
            "confidence_modifier": 0.0,
            "components": {
                "text_sentiment_score": 0.0,
                "ipo_froth_score": 0.0,
                "fo_retail_skew": 0.0,
                "pe_expansion_velocity": 0.0,
                "social_buzz_index": 0.0,
            },
            "reasoning": "CISI computation failed; defaulted to neutral.",
        }

    # -- 4. Interpretation --
    if cisi_score > 70.0:
        cisi_label = "IRRATIONAL_EXUBERANCE"
        confidence_modifier = -0.10
        reasoning = (
            f"CISI {cisi_score:.1f} signals irrational exuberance. "
            "Confidence penalised by 0.10 to account for frothy sentiment."
        )
    elif cisi_score < -50.0:
        cisi_label = "PANIC"
        confidence_modifier = 0.05
        reasoning = (
            f"CISI {cisi_score:.1f} signals panic/capitulation. "
            "Mean-reversion boost of 0.05 applied."
        )
    else:
        cisi_label = "NORMAL"
        confidence_modifier = 0.0
        reasoning = f"CISI {cisi_score:.1f} within normal range. No modifier applied."

    return {
        "cisi_score": cisi_score,
        "cisi_label": cisi_label,
        "confidence_modifier": confidence_modifier,
        "components": {
            "text_sentiment_score": round(text_sentiment_score, 4),
            "ipo_froth_score": round(ipo_froth_score, 4),
            "fo_retail_skew": round(fo_retail_skew, 4),
            "pe_expansion_velocity": round(pe_expansion_velocity, 4),
            "social_buzz_index": round(social_buzz_index, 4),
        },
        "reasoning": reasoning,
    }
