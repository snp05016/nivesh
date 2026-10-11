"""Summary provider abstraction — DeepSeek, Mock, and Extractive fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Finance-aware summarization prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a senior Indian equity analyst reviewing a YouTube video transcript from an Indian \
market commentary video. Your task is to extract structured, factual insights for Indian \
retail investors.

Rules:
- Use Indian number formatting: Lakhs (L) and Crores (Cr). Never write "Million" or "Billion".
- Express prices in INR (₹) where relevant.
- Identify NSE/BSE ticker symbols explicitly mentioned (e.g., RELIANCE, TATAMOTORS, HDFCBANK).
- Sentiment must be one of: bullish | bearish | neutral | mixed.
- Be concise and factual — do not invent claims the presenter did not make.
- Do not convert the presenter's views into recommendations.
- Output ONLY valid JSON matching the schema below. No markdown fences, no preamble.

Output schema:
{
  "tldr": "<one-sentence synopsis>",
  "key_points": ["<point>", ...],
  "finance_insights": ["<insight>", ...],
  "tickers_mentioned": ["<NSE_TICKER>", ...],
  "risks_or_red_flags": ["<risk>", ...],
  "sentiment": "bullish|bearish|neutral|mixed",
  "confidence": <0.0-1.0>
}
"""

_USER_TEMPLATE = """\
Transcript chunk ({chunk_index} of {total_chunks}):

{text}

Summarize this chunk following the schema above.
"""

_MERGE_SYSTEM_PROMPT = """\
You are merging partial JSON summaries of consecutive chunks from the same YouTube video \
into one final consolidated summary. Deduplicate tickers and points. \
Output ONLY valid JSON matching the original schema.
"""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SummaryProvider(ABC):
    """Contract that all summary providers must satisfy."""

    @abstractmethod
    async def summarize_chunks(self, chunks: List[str]) -> dict:
        """Summarize a list of transcript chunks and return a merged dict."""


# ---------------------------------------------------------------------------
# DeepSeek provider
# ---------------------------------------------------------------------------

class DeepSeekProvider(SummaryProvider):
    """Calls DeepSeek via the project's canonical llm_utils.deepseek_chat."""

    _MAX_CHUNK_TOKENS: int = 500  # output tokens per chunk
    _MAX_CHUNKS: int = 20

    async def summarize_chunks(self, chunks: List[str]) -> dict:
        """Summarize up to _MAX_CHUNKS chunks and merge results."""
        from services.llm_utils import deepseek_chat  # local import avoids circular deps

        chunks = chunks[: self._MAX_CHUNKS]
        total = len(chunks)
        partials: List[dict] = []

        for idx, chunk in enumerate(chunks, start=1):
            prompt = _USER_TEMPLATE.format(
                chunk_index=idx, total_chunks=total, text=chunk
            )
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            try:
                # Sync LLM client: run in a worker thread so the loop stays free.
                raw = await asyncio.to_thread(
                    deepseek_chat,
                    messages,
                    max_tokens=self._MAX_CHUNK_TOKENS,
                    temperature=0.2,
                    log_endpoint="youtube_summary",
                )
                partials.append(_safe_json(raw))
            except Exception as exc:
                logger.warning("DeepSeekProvider chunk %d failed: %s", idx, exc)

        if not partials:
            # Raise so the summarizer returns 502 and never caches an empty summary.
            raise RuntimeError("all DeepSeek chunk calls failed")

        if len(partials) == 1:
            return _sanitize(partials[0])

        return await asyncio.to_thread(_merge_partials, partials, deepseek_chat)


# ---------------------------------------------------------------------------
# Mock provider (YOUTUBE_SUMMARY_FORCE_MOCK=true)
# ---------------------------------------------------------------------------

class MockProvider(SummaryProvider):
    """Returns a fake structured summary — for local testing."""

    async def summarize_chunks(self, chunks: List[str]) -> dict:
        """Return a deterministic fake summary regardless of input."""
        snippet = chunks[0][:120].replace("\n", " ") if chunks else "N/A"
        return {
            "tldr": f"[MOCK] This video discusses Indian equity markets. Snippet: {snippet}",
            "key_points": ["[MOCK] Key point 1", "[MOCK] Key point 2"],
            "finance_insights": ["[MOCK] Nifty 50 outlook remains range-bound near 24,500 levels"],
            "tickers_mentioned": ["RELIANCE", "HDFCBANK"],
            "risks_or_red_flags": ["[MOCK] Global macro headwinds from Fed rate trajectory"],
            "action_items": [],
            "sentiment": "neutral",
            "confidence": 0.5,
        }


# ---------------------------------------------------------------------------
# Extractive fallback (no API cost)
# ---------------------------------------------------------------------------

_TICKER_RE = re.compile(r"\b([A-Z]{2,10}(?:\.NS|\.BO)?)\b")
_FINANCE_KEYWORDS = {
    "bullish", "bearish", "buy", "sell", "hold", "target", "nifty", "sensex",
    "ipo", "fii", "dii", "rbi", "sebi", "eps", "pe ratio", "market cap",
    "crore", "lakh", "quarter", "results", "dividend", "bonus", "split",
    "revenue", "profit", "loss", "debt", "equity", "portfolio", "allocation",
}


class ExtractiveProvider(SummaryProvider):
    """Zero-cost keyword-extraction fallback when no API key is available."""

    async def summarize_chunks(self, chunks: List[str]) -> dict:
        """Extract tickers and finance keywords from raw transcript text."""
        full_text = " ".join(chunks)
        words = full_text.split()

        # Heuristic ticker detection: uppercase tokens 2-10 chars, not common English words
        _COMMON_ENGLISH = {"I", "A", "AN", "THE", "IS", "IN", "OF", "TO", "AND", "OR", "FOR",
                           "ON", "AT", "BY", "IT", "BE", "AS", "DO", "IF", "SO", "UP", "MY",
                           "WE", "HE", "SHE", "YOU", "THIS", "THAT"}
        tickers = sorted({
            w.rstrip(".,!?;:")
            for w in words
            if _TICKER_RE.match(w.rstrip(".,!?;:"))
            and w.rstrip(".,!?;:") not in _COMMON_ENGLISH
        })[:10]

        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        finance_sentences = [
            s.strip()
            for s in sentences
            if any(kw in s.lower() for kw in _FINANCE_KEYWORDS)
        ][:5]

        tldr = finance_sentences[0] if finance_sentences else full_text[:150]

        sentiment = "neutral"
        lower = full_text.lower()
        bull_count = sum(lower.count(w) for w in ("bullish", "buy", "positive", "upside", "growth"))
        bear_count = sum(lower.count(w) for w in ("bearish", "sell", "negative", "downside", "risk"))
        if bull_count > bear_count * 1.5:
            sentiment = "bullish"
        elif bear_count > bull_count * 1.5:
            sentiment = "bearish"

        return {
            "tldr": tldr[:300],
            "key_points": finance_sentences,
            "finance_insights": [],
            "tickers_mentioned": tickers,
            "risks_or_red_flags": [],
            "action_items": [],
            "sentiment": sentiment,
            "confidence": 0.3,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_provider(name: Optional[str] = None) -> SummaryProvider:
    """Return a SummaryProvider by name; falls back to ExtractiveProvider if key missing."""
    force_mock = os.getenv("YOUTUBE_SUMMARY_FORCE_MOCK", "false").lower() == "true"
    if force_mock:
        return MockProvider()

    resolved = (name or os.getenv("YOUTUBE_SUMMARY_PROVIDER", "deepseek")).lower()

    if resolved == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY not set; falling back to ExtractiveProvider")
            return ExtractiveProvider()
        return DeepSeekProvider()

    if resolved == "mock":
        return MockProvider()

    if resolved == "extractive":
        return ExtractiveProvider()

    logger.warning("Unknown provider %r; using ExtractiveProvider", resolved)
    return ExtractiveProvider()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_json(raw: str) -> dict:
    """Parse JSON from an LLM response, stripping markdown fences."""
    raw = raw.strip()
    # Strip ```json ... ``` fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Last resort: extract first {...} block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return _empty_summary()


def _empty_summary() -> dict:
    """Return an empty summary skeleton matching the schema."""
    return {
        "tldr": "",
        "key_points": [],
        "finance_insights": [],
        "tickers_mentioned": [],
        "risks_or_red_flags": [],
        "action_items": [],
        "sentiment": "neutral",
        "confidence": 0.0,
    }


def _sanitize(d: dict) -> dict:
    """Ensure all required fields exist with correct types."""
    base = _empty_summary()
    base.update(d)
    for list_field in ("key_points", "finance_insights", "tickers_mentioned",
                       "risks_or_red_flags", "action_items"):
        if not isinstance(base[list_field], list):
            base[list_field] = []
    if base["sentiment"] not in ("bullish", "bearish", "neutral", "mixed"):
        base["sentiment"] = "neutral"
    try:
        base["confidence"] = float(base.get("confidence", 0.0))
    except (TypeError, ValueError):
        base["confidence"] = 0.0
    return base


def _merge_partials(partials: List[dict], deepseek_chat) -> dict:
    """Merge multiple chunk summaries into one coherent summary via LLM."""
    merged_json = json.dumps(partials, ensure_ascii=False)
    messages = [
        {"role": "system", "content": _MERGE_SYSTEM_PROMPT},
        {"role": "user", "content": merged_json},
    ]
    try:
        raw = deepseek_chat(messages, max_tokens=600, temperature=0.1, log_endpoint="youtube_summary_merge")
        return _sanitize(_safe_json(raw))
    except Exception as exc:
        logger.warning("Merge call failed (%s); using first partial as fallback", exc)
        # Fallback: naively merge lists from all partials
        merged = _empty_summary()
        for p in partials:
            for field in ("key_points", "finance_insights", "tickers_mentioned",
                          "risks_or_red_flags", "action_items"):
                merged[field] = list(dict.fromkeys(merged[field] + (p.get(field) or [])))
            if not merged["tldr"] and p.get("tldr"):
                merged["tldr"] = p["tldr"]
        # Average confidence
        confs = [float(p.get("confidence", 0.0)) for p in partials]
        merged["confidence"] = round(sum(confs) / len(confs), 2) if confs else 0.0
        # Majority sentiment
        sentiments = [p.get("sentiment", "neutral") for p in partials]
        merged["sentiment"] = max(set(sentiments), key=sentiments.count)
        return merged
