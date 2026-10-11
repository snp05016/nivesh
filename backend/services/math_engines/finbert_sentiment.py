"""
Financial News Sentiment Scoring engine.
Tries FinBERT first; falls back to a financial lexicon to score text.
"""

from __future__ import annotations
import logging
import re
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TextSentiment(BaseModel):
    text: str
    score: float
    label: str

class NewsSentimentResponse(BaseModel):
    scores: List[float]
    per_text: List[TextSentiment]
    aggregate_score: float
    sentiment: str
    method: str
    bullish_count: int
    bearish_count: int
    neutral_count: int
    total_texts: int


# ── Financial lexicon ─────────────────────────────────────────────────────────
# Positive (bullish) financial terms
_BULLISH_TERMS: list[tuple[str, float]] = [
    (r"\b(beat|beats|beat expectations|earnings beat)\b", 0.8),
    (r"\b(strong results|strong growth|strong demand)\b", 0.7),
    (r"\b(upgrade|upgraded|buy rating|outperform)\b", 0.7),
    (r"\b(profit surge|profit jump|profit soars)\b", 0.9),
    (r"\b(revenue growth|revenue beat|revenue surge)\b", 0.7),
    (r"\b(record high|all.time high|52.week high)\b", 0.6),
    (r"\b(expansion|expanding|market share gain)\b", 0.5),
    (r"\b(dividend increase|dividend hike|buyback)\b", 0.6),
    (r"\b(positive outlook|raised guidance|guidance raise)\b", 0.7),
    (r"\b(margin expansion|margin improvement)\b", 0.6),
    (r"\b(acquisition|merger|strategic partnership)\b", 0.4),
    (r"\b(turnaround|recovery|rebound)\b", 0.5),
    (r"\b(bullish|bull run|rally)\b", 0.5),
    (r"\b(lakhs crore|crore profit|net profit up)\b", 0.7),
    (r"\b(nifty high|sensex high|market rally)\b", 0.5),
    (r"\b(fii buying|dii buying|institutional buying)\b", 0.6),
    (r"\b(debt free|zero debt|cash rich)\b", 0.6),
    (r"\b(order win|order book|new order)\b", 0.5),
    (r"\b(capex plan|capacity expansion)\b", 0.4),
    (r"\b(promoter buying|stake increase)\b", 0.5),
]

# Negative (bearish) financial terms
_BEARISH_TERMS: list[tuple[str, float]] = [
    (r"\b(miss|missed|earnings miss|profit miss)\b", -0.8),
    (r"\b(downgrade|downgraded|sell rating|underperform)\b", -0.7),
    (r"\b(profit decline|profit fall|profit drops)\b", -0.9),
    (r"\b(revenue miss|revenue decline|revenue fall)\b", -0.7),
    (r"\b(warning|profit warning|guidance cut|guidance lower)\b", -0.8),
    (r"\b(margin pressure|margin squeeze|margin contraction)\b", -0.6),
    (r"\b(debt surge|debt rises|high debt|debt trap)\b", -0.7),
    (r"\b(fraud|scam|accounting fraud|audit concern)\b", -0.9),
    (r"\b(sebi notice|sebi penalty|regulatory action)\b", -0.8),
    (r"\b(promoter pledge|promoter pledging|high pledging)\b", -0.6),
    (r"\b(bearish|bear run|sell.off|selloff)\b", -0.5),
    (r"\b(bankruptcy|insolvency|nclt|liquidation)\b", -0.9),
    (r"\b(52.week low|all.time low|record low)\b", -0.6),
    (r"\b(fii selling|dii selling|institutional selling)\b", -0.6),
    (r"\b(supply chain|shortage|disruption)\b", -0.4),
    (r"\b(negative outlook|lowered guidance|guidance slash)\b", -0.7),
    (r"\b(loss|net loss|operating loss)\b", -0.7),
    (r"\b(npa|bad loan|write.off|provision)\b", -0.6),
    (r"\b(plant shutdown|factory closure|layoff)\b", -0.5),
    (r"\b(promoter sell|stake sale|block deal)\b", -0.4),
]

# Negation words (flip sentiment)
_NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "without", "lack", "fail", "failed",
    "fails", "despite", "although", "though", "unlikely", "below", "falling short",
}


def _lexicon_score(text: str) -> float:
    """
    Score a single text snippet using the financial lexicon.

    Args:
        text: The text snippet to score.

    Returns:
        float: A sentiment score between -1.0 (bearish) and 1.0 (bullish).
    """
    text_lower = text.lower()

    # Check for negation in a short window
    words = set(text_lower.split())
    has_negation = bool(words & _NEGATION_WORDS)

    score = 0.0
    match_count = 0

    for pattern, weight in _BULLISH_TERMS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            score += weight * (-0.5 if has_negation else 1.0)
            match_count += 1

    for pattern, weight in _BEARISH_TERMS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            score += weight * (-0.5 if has_negation else 1.0)
            match_count += 1

    if match_count == 0:
        return 0.0

    # Normalize to [-1, 1]
    raw = score / match_count
    return max(-1.0, min(1.0, raw))


def _try_finbert(texts: list[str]) -> list[float] | None:
    """
    Attempt to use FinBERT via the HuggingFace transformers pipeline.

    Args:
        texts: A list of text strings to analyze.

    Returns:
        list[float] | None: A list of sentiment scores if successful, or None if unavailable.
    """
    try:
        # Process-wide ProsusAI/finbert singleton with failure backoff (LLM-23):
        # never build a pipeline per call.
        from services.sentiment_engine import get_classifier

        sentiment_pipe = get_classifier()
        if sentiment_pipe is None:
            return None
        results = sentiment_pipe(texts)
        scores = []
        for r in results:
            label = r["label"].lower()
            confidence = r["score"]
            if label == "positive":
                scores.append(confidence)
            elif label == "negative":
                scores.append(-confidence)
            else:
                scores.append(0.0)
        return scores
    except Exception as _e:
        return None


def analyze_news_sentiment(texts: list[str]) -> NewsSentimentResponse:
    """
    Analyze financial news sentiment for a list of texts.

    Tries FinBERT (HuggingFace) first; falls back to lexicon-based scoring.
    Returns scores from -1.0 (bearish) to +1.0 (bullish).

    Args:
        texts: List of news headlines or article snippets.

    Returns:
        dict: A dictionary with 'scores', 'aggregate_score', 'sentiment',
            'method', 'bullish_count', 'bearish_count', and 'neutral_count'.
    """
    if not texts:
        return NewsSentimentResponse(
            scores=[],
            per_text=[],
            aggregate_score=0.0,
            sentiment="NEUTRAL",
            method="none",
            bullish_count=0,
            bearish_count=0,
            neutral_count=0,
            total_texts=0,
        )

    # Try FinBERT first
    finbert_scores = _try_finbert(texts)
    if finbert_scores is not None:
        scores = finbert_scores
        method = "finbert"
    else:
        scores = [_lexicon_score(t) for t in texts]
        method = "lexicon"

    aggregate = sum(scores) / len(scores) if scores else 0.0
    aggregate = round(aggregate, 4)

    bullish = sum(1 for s in scores if s > 0.1)
    bearish = sum(1 for s in scores if s < -0.1)
    neutral = len(scores) - bullish - bearish

    if aggregate > 0.3:
        sentiment = "BULLISH"
    elif aggregate > 0.1:
        sentiment = "MILD_BULLISH"
    elif aggregate < -0.3:
        sentiment = "BEARISH"
    elif aggregate < -0.1:
        sentiment = "MILD_BEARISH"
    else:
        sentiment = "NEUTRAL"

    per_text = [
        TextSentiment(
            text=t[:120] + "..." if len(t) > 120 else t,
            score=round(s, 4),
            label="BULLISH" if s > 0.1 else ("BEARISH" if s < -0.1 else "NEUTRAL"),
        )
        for t, s in zip(texts, scores)
    ]

    return NewsSentimentResponse(
        scores=[round(s, 4) for s in scores],
        per_text=per_text,
        aggregate_score=aggregate,
        sentiment=sentiment,
        method=method,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        total_texts=len(texts),
    )


if __name__ == "__main__":
    sample_texts = [
        "TCS beats Q3 earnings expectations, profit surges 18% YoY",
        "Infosys cuts annual revenue guidance amid weak demand",
        "Reliance Industries announces record quarterly profit",
        "HDFC Bank faces NPA concerns after regulatory notice",
        "Market rallies on strong FII buying in banking sector",
        "Adani Group company reports net loss in Q2",
        "Wipro upgraded to Buy by Morgan Stanley on strong order book",
    ]

    result = analyze_news_sentiment(sample_texts)
    logging.info(f"Method: {result.method}")
    logging.info(f"Aggregate score: {result.aggregate_score:.3f} — {result.sentiment}")
    logging.info(f"Bullish: {result.bullish_count}, Bearish: {result.bearish_count}, Neutral: {result.neutral_count}")
    for pt in result.per_text:
        logging.info(f"  [{pt.label:12}] {pt.score:+.3f}  {pt.text[:60]}...")

    assert result.method in {"finbert", "lexicon"}
    assert -1.0 <= result.aggregate_score <= 1.0
    assert result.sentiment in {"BULLISH", "MILD_BULLISH", "NEUTRAL", "MILD_BEARISH", "BEARISH"}
    logging.info("All finbert_sentiment tests passed.")
