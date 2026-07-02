"""Forum Moderation service — lightweight spam filtering + sentiment tagging.

Layered on top of the Community Forum feature (owned separately by the
Fullstack Forum Agent). This module intentionally does NOT touch
models/db_models.py, routers/forum.py, or services/forum_service.py — it is
a standalone, importable set of pure/near-pure functions that the forum
stack can call from its own post-creation flow.

Persistence contract (documented, not implemented here):
    The Fullstack Forum Agent's ForumPost model is expected to persist the
    verdict returned by `moderate_post()` in a column named
    `moderation_action` (values: "allow" | "flag" | "block"), and optionally
    `spam_score` (0-100) and `sentiment` ("bullish" | "bearish" | "neutral")
    columns alongside it. This service has no DB tables of its own.

Spam detection:
    `is_spam()` / `spam_score()` use a simple, fully explainable rule-based
    scorer (0-100) — no external API calls or model downloads, since no ML
    training infra exists in this repo for spam classification. Signals:
    excessive links, repeated characters, all-caps ratio, known spam
    phrases, and excessive punctuation. A real ML classifier (e.g. a small
    fine-tuned transformer) could later replace `spam_score()` without
    changing the public signature of `is_spam()` / `moderate_post()`.

Sentiment tagging:
    `tag_sentiment()` reuses the existing FinBERT-first / lexicon-fallback
    engine at `services/math_engines/finbert_sentiment.py`
    (`analyze_news_sentiment`) rather than reimplementing sentiment scoring.
    That engine was built for financial news headlines, not short informal
    forum chatter, so `tag_sentiment()` adds a small Indian-market-slang
    pre-pass (e.g. "to the moon", "multibagger", "bhaag gaya", "dabba
    trading") on top of the reused engine's lexicon signal before falling
    back to the engine's own verdict. This keeps us reusing the existing
    helper (per repo convention) while covering forum-specific slang the
    news-tuned lexicon wasn't built for.
"""
from __future__ import annotations

import re
from typing import Dict

# ---------------------------------------------------------------------------
# Spam detection (pure, rule-based, explainable — no external calls)
# ---------------------------------------------------------------------------

# Threshold above which a post is considered spam. Kept as a module-level
# constant so callers/tests can tune it without editing scoring internals.
SPAM_SCORE_THRESHOLD = 60

# Score above which a (non-spam) post should still be routed to human review
# rather than auto-allowed.
FLAG_SCORE_THRESHOLD = 35

_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{4,}")  # same char 5+ times in a row
_REPEATED_PUNCT_RE = re.compile(r"[!?$]{3,}")

_SPAM_PHRASES = [
    "click here", "buy now", "limited time offer", "guaranteed returns",
    "guaranteed profit", "100% profit", "double your money", "risk free",
    "join telegram", "join my telegram", "dm me for tips", "whatsapp me",
    "call now", "free tips", "sure shot tip", "sureshot", "act now",
    "investment opportunity", "earn from home", "work from home",
    "no loss guarantee", "assured returns", "hurry up", "limited slots",
]


def _link_score(text: str) -> int:
    links = _URL_RE.findall(text)
    if not links:
        return 0
    if len(links) == 1:
        return 15
    return min(40, 15 + (len(links) - 1) * 15)


def _repeated_char_score(text: str) -> int:
    hits = len(_REPEATED_CHAR_RE.findall(text))
    if hits == 0:
        return 0
    return min(20, 10 * hits)


def _all_caps_score(text: str) -> int:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
        return 0
    caps = sum(1 for c in letters if c.isupper())
    ratio = caps / len(letters)
    if ratio < 0.6:
        return 0
    if ratio < 0.8:
        return 10
    return 20


def _spam_phrase_score(text_lower: str) -> int:
    hits = sum(1 for phrase in _SPAM_PHRASES if phrase in text_lower)
    if hits == 0:
        return 0
    return min(35, hits * 15)


def _punctuation_score(text: str) -> int:
    hits = len(_REPEATED_PUNCT_RE.findall(text))
    if hits == 0:
        return 0
    return min(15, hits * 8)


def spam_score(text: str) -> int:
    """Score `text` 0-100 on how spam-like it looks.

    Purely rule-based and explainable (link count, repeated characters,
    ALL-CAPS ratio, known spam phrases, excessive punctuation). Not an ML
    model — see module docstring for why. A real classifier could later
    replace this function's internals while keeping the 0-100 contract.
    """
    if not text or not text.strip():
        return 0

    text_lower = text.lower()
    score = (
        _link_score(text)
        + _repeated_char_score(text)
        + _all_caps_score(text)
        + _spam_phrase_score(text_lower)
        + _punctuation_score(text)
    )
    return max(0, min(100, score))


def is_spam(text: str, threshold: int = SPAM_SCORE_THRESHOLD) -> bool:
    """Return True if `text` scores at or above `threshold` (default 60/100)."""
    return spam_score(text) >= threshold


# ---------------------------------------------------------------------------
# Sentiment tagging — reuses services/math_engines/finbert_sentiment.py
# ---------------------------------------------------------------------------

# Indian-market-slang pre-pass. The reused engine's lexicon (see
# math_engines/finbert_sentiment.py) is tuned for formal news headlines, so
# we widen coverage for short informal forum posts here before deferring to
# the engine's own scoring/fallback logic.
_SLANG_BULLISH = [
    "to the moon", "moon soon", "multibagger", "multi bagger", "rocket",
    "breakout", "loading up", "accumulate", "buy the dip", "strong buy",
    "tenbagger", "10x", "chalo upar", "upar jayega", "tejji", "tezi",
]
_SLANG_BEARISH = [
    "dump", "dumping", "crash hone wala", "bhaag gaya", "bhag gaya",
    "sell sell sell", "exit now", "trap", "bull trap", "operator stock",
    "dabba trading", "dabba", "mandi", "girega", "gir gaya", "rug pull",
]


def _slang_hits(text_lower: str) -> int:
    return sum(1 for phrase in _SLANG_BULLISH if phrase in text_lower) - sum(
        1 for phrase in _SLANG_BEARISH if phrase in text_lower
    )


def tag_sentiment(text: str) -> str:
    """Classify `text` as "bullish" | "bearish" | "neutral".

    Reuses `services.math_engines.finbert_sentiment.analyze_news_sentiment`
    (FinBERT-first, lexicon-fallback) rather than reimplementing sentiment
    scoring, per repo convention of reusing existing helpers. That engine
    was tuned for news headlines, so a small Indian-market-slang pre-pass is
    applied first for short informal forum text (see module docstring).
    """
    if not text or not text.strip():
        return "neutral"

    text_lower = text.lower()
    slang_signal = _slang_hits(text_lower)

    try:
        from services.math_engines.finbert_sentiment import analyze_news_sentiment

        result = analyze_news_sentiment([text])
        aggregate = result.aggregate_score
    except Exception:
        aggregate = 0.0

    # Blend: slang pre-pass gives a strong nudge (+/-0.5) since it's tuned
    # for forum-specific phrasing the underlying engine doesn't know about.
    blended = aggregate + (0.5 * slang_signal)

    if blended > 0.1:
        return "bullish"
    if blended < -0.1:
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# Combined moderation verdict
# ---------------------------------------------------------------------------

def moderate_post(text: str) -> Dict:
    """Combine spam scoring and sentiment tagging into one moderation verdict.

    Returns:
        {
            "is_spam": bool,
            "spam_score": int (0-100),
            "sentiment": "bullish" | "bearish" | "neutral",
            "action": "allow" | "flag" | "block",
        }

    Action policy:
        - spam_score >= SPAM_SCORE_THRESHOLD (60)  -> "block"
        - spam_score >= FLAG_SCORE_THRESHOLD (35)   -> "flag" (human review)
        - otherwise                                  -> "allow"

    Callers (the forum stack) are expected to persist this verdict's
    `action` value on their ForumPost row as `moderation_action`.
    """
    score = spam_score(text)
    spam = score >= SPAM_SCORE_THRESHOLD
    sentiment = tag_sentiment(text)

    if score >= SPAM_SCORE_THRESHOLD:
        action = "block"
    elif score >= FLAG_SCORE_THRESHOLD:
        action = "flag"
    else:
        action = "allow"

    return {
        "is_spam": spam,
        "spam_score": score,
        "sentiment": sentiment,
        "action": action,
    }
