"""
nivesh.reformatter — Deterministic Reformatting Layer (Task 13.2)
=================================================================

DEPRECATED — This module is NOT called by any active backend code.
The canonical reformatter is services/orchestrator.py:reformat_with_claude()
which includes Sonnet → DeepSeek fallback + _normalize_response().
Keep this module as a reference for the enhanced system prompt only.

Feeds raw Portfolio Manager output into Claude Sonnet 4.6 with:

  • Indian Market Priority Weighting Matrix enforced in the system prompt:
      Management Quality → Institutional Flow → Contrarian Sentiment →
      Core Fundamentals → Policy Tailwinds → Global Macro

  • Dual prompt-cache breakpoints (ephemeral):
      Breakpoint 1 — Static institutional persona (never changes per run)
      Breakpoint 2 — Ticker-specific historical analyses (changes per ticker)

  • temperature=0 for strict deterministic JSON output

  • Pristine JSON schema output — no markdown fences, no trailing text.

  • Retry with exponential backoff (max 3 attempts) for 503 / network errors.

Public API
----------
    reformat_with_sonnet(
        raw_output: str,
        full_ticker: str,
        exchange: str,
        prior_analyses: list[dict] | None = None,
    ) -> dict
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model constant — Claude Sonnet 4.6 (Tier 3, user-facing reformatter)
# ---------------------------------------------------------------------------
_SONNET_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Indian Market Priority Weighting Matrix — injected as static system prompt.
# Cached at Breakpoint 1 (ephemeral) — tokens never re-sent on cache hits.
# ---------------------------------------------------------------------------
_INDIAN_MARKET_SYSTEM_PROMPT = """\
You are the Principal Market Microstructure Analyst for Dalal Street equities. \
Your user is a 10-year veteran retail investor who has survived multiple severe \
Indian market cycles. You write like a hardened risk officer — authoritative, \
skeptical of corporate PR, relentlessly focused on capital preservation.

ANALYSIS PRIORITIES (highest weight first — enforce this exact ordering):
1. Management Quality — governance, capital allocation, promoter pledging
2. Institutional Flow — Promoter/FII/DII stake changes, bulk deals, insider disclosures
3. Contrarian Sentiment — operator activity, retail herd behaviour, Telegram/Twitter \
   chatter signals. HIGH retail excitement = potential cycle-top risk, NOT bullish.
4. Core Fundamentals — revenue growth, margins, ROE, ROCE, debt, cash flow
5. Policy Tailwinds — India-specific risks, PLI schemes, government capex
6. Global Macro — Fed rates, crude oil (India imports 85%), DXY, risk sentiment

NAME & NUMBER CONSTRAINT — NON-NEGOTIABLE:
Every qualitative assertion MUST be paired with a quantitative metric and a \
specific operational catalyst.
- BANNED: "Margins are improving."
  REQUIRED: "EBITDA margins expanded 240bps to 18.5% driven by 12% drop in \
  crude-linked raw material costs."
- BANNED: "Strong rural demand."
  REQUIRED: "Rural volume grew 8% YoY driven by extended monsoon cycle."
- BANNED: "Good debt management."
  REQUIRED: "D/E reduced to 0.4x on ₹1,200cr FCF; working capital cycle 85 days."

FORBIDDEN LANGUAGE — output containing these phrases is a failure:
- "On the one hand / on the other hand" → force base-case probability + invalidation metric
- "Subject to market risks / only time will tell" → replace with structural risk in bps/crore
- "Cautiously optimistic / navigating headwinds / value unlocking / synergies" → use exact figures
- "Strong / robust / significant potential / gaining traction / healthy demand" → use CAGR/margin %
- "Investors should monitor / trading in a range / mixed signals" → use specific price level
- "Impacted by global cues / geopolitical uncertainties" → specify variable + direct operational impact

OUTPUT RULES:
- Return ONLY valid JSON. No markdown fences, no text outside the JSON object.
- Rupee figures in Indian format: lakhs (1,00,000) and crores (1,00,00,000).
- Percentages rounded to one decimal place.
- Dates in DD-MMM-YYYY format.
- signal must be exactly one of: BULLISH, CAUTIOUSLY BULLISH, NEUTRAL, HOLD, \
  CAUTIOUSLY BEARISH, BEARISH
- A promoter_pledged_pct above 30% MUST be treated as a significant bear case point.

REQUIRED JSON STRUCTURE — return exactly this, no extra keys:
{
  "ticker": "<NSE/BSE ticker with exchange suffix e.g. SUZLON.NS>",
  "company_name": "<full company name>",
  "exchange": "<NSE or BSE>",
  "analysis_date": "<DD-MMM-YYYY>",
  "signal": "<BULLISH | CAUTIOUSLY BULLISH | NEUTRAL | HOLD | CAUTIOUSLY BEARISH | BEARISH>",
  "confidence_pct": <integer 0-100>,
  "confidence_rationale": "<one sentence: 2-3 specific factors most responsible>",
  "current_price_inr": <number>,
  "target_prices": {
    "short_term_3m": <number>,
    "medium_term_12m": <number>,
    "long_term_36m": <number>
  },
  "upside_downside_pct": {
    "short_term": <number>,
    "medium_term": <number>,
    "long_term": <number>
  },
  "bull_case": ["<point 1>", "<point 2>", "<point 3>"],
  "bear_case": ["<point 1>", "<point 2>", "<point 3>"],
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "key_factors": {
    "management_quality": "<2-3 sentences>",
    "geopolitical_context": "<2-3 sentences>",
    "promoter_fii_dii_activity": "<2-3 sentences>",
    "indian_market_sentiment": "<2-3 sentences: buzz level, operator/retail direction, \
contrarian risk if euphoria detected>",
    "turnaround_story": "<2-3 sentences>",
    "fundamentals_summary": "<2-3 sentences>",
    "global_macro_impact": "<2-3 sentences>",
    "news_sentiment": "<1-2 sentences>"
  },
  "fundamentals_snapshot": {
    "revenue_ttm_crores": <number or null>,
    "ebitda_margin_pct": <number or null>,
    "pat_ttm_crores": <number or null>,
    "roe_pct": <number or null>,
    "roce_pct": <number or null>,
    "debt_to_equity": <number or null>,
    "pe_ratio": <number or null>,
    "market_cap_crores": <number or null>,
    "promoter_holding_pct": <number or null>,
    "promoter_pledged_pct": <number or null>,
    "promoter_pledged_trend": <string or null>,
    "fii_holding_pct": <number or null>,
    "dii_holding_pct": <number or null>
  },
  "what_to_watch": ["<trigger 1>", "<trigger 2>", "<trigger 3>"],
  "patterns": ["<pattern if found, else omit>"],
  "disclaimer": "This analysis is generated by an AI system for informational \
purposes only. It does not constitute financial advice. Please consult a \
SEBI-registered investment advisor before making any investment decisions. \
Past performance is not indicative of future results."
}
"""

# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_from_text(text: str) -> str:
    """Strip markdown fences if present; return raw JSON string."""
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Try to find the outermost {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def reformat_with_sonnet(
    raw_output: str,
    full_ticker: str,
    exchange: str,
    prior_analyses: list[dict] | None = None,
    api_key: str | None = None,
) -> dict:
    """Reformat raw trading agent output into pristine JSON via Claude Sonnet 4.6.

    Parameters
    ----------
    raw_output:
        The unstructured text emitted by the Portfolio Manager node.
    full_ticker:
        Ticker with exchange suffix, e.g. ``"SUZLON.NS"``.
    exchange:
        ``"NSE"`` or ``"BSE"``.
    prior_analyses:
        Optional list of previous analysis dicts for this ticker.
        Up to the last 15 are serialized deterministically and cached at
        Breakpoint 2 (ephemeral) to maximise prompt-cache hit ratio.
    api_key:
        Anthropic API key. Defaults to ``ANTHROPIC_API_KEY`` env var.

    Returns
    -------
    dict
        Parsed JSON matching the REQUIRED JSON STRUCTURE above.
    """
    from datetime import date as _date

    resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=resolved_key)

    # ── Breakpoint 2: deterministic ticker-history context ──────────────────
    serialized_history = ""
    if prior_analyses:
        history_points = []
        for p in prior_analyses[-15:]:
            history_points.append(
                {
                    "date": p.get("analysis_date"),
                    "signal": p.get("signal"),
                    "conf": p.get("confidence_pct"),
                    "target_3m": (p.get("target_prices") or {}).get("short_term_3m"),
                }
            )
        serialized_history = json.dumps(history_points, sort_keys=True)

    # ── Prefix-aligned system array with dual ephemeral cache breakpoints ──
    system_array: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _INDIAN_MARKET_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # Breakpoint 1 — static persona
        }
    ]
    if serialized_history:
        system_array.append(
            {
                "type": "text",
                "text": f"PREVIOUS HISTORICAL ANALYSES FOR {full_ticker}:\n{serialized_history}",
                "cache_control": {"type": "ephemeral"},  # Breakpoint 2 — ticker archive
            }
        )

    # ── HumanMessage: volatile ticker data (not cached) ───────────────────
    today_str = _date.today().strftime("%d-%b-%Y")
    user_message = (
        f"Below is the raw trading analysis for {full_ticker} ({exchange}).\n\n"
        f"<raw_analysis>\n{raw_output}\n</raw_analysis>\n\n"
        f"Today's date: {today_str}"
    )

    # ── Retry loop with exponential backoff (max 3 attempts, base 2s) ─────
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=_SONNET_MODEL,
                max_tokens=2000,
                system=system_array,
                messages=[{"role": "user", "content": user_message}],
                temperature=0,  # strict deterministic output
            )
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "[reformatter] Attempt %d/3 failed for %s: %s",
                attempt + 1,
                full_ticker,
                exc,
            )
            if attempt < 2:
                time.sleep(2.0 * (2**attempt))  # 2s, 4s
    else:
        raise RuntimeError(
            f"[reformatter] Reformat failed after 3 retries for {full_ticker}: {last_exc}"
        ) from last_exc

    raw_json = _extract_json_from_text(response.content[0].text)

    try:
        parsed: dict = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.error(
            "[reformatter] JSON parse failed for %s: %s\nRaw: %.200s",
            full_ticker,
            exc,
            raw_json,
        )
        # Return minimal valid fallback structure on parse failure
        return {
            "ticker": full_ticker,
            "exchange": exchange,
            "signal": "HOLD",
            "confidence_pct": 0,
            "confidence_rationale": "Parse error in reformatter output.",
            "target_prices": {
                "short_term_3m": None,
                "medium_term_12m": None,
                "long_term_36m": None,
            },
            "key_factors": {
                "indian_market_sentiment": "Sentiment data unavailable due to parse error."
            },
        }

    # ── Validate indian_market_sentiment field is populated ────────────────
    kf = parsed.get("key_factors", {})
    if not kf.get("indian_market_sentiment", "").strip():
        logger.warning(
            "[reformatter] indian_market_sentiment empty for %s — filling placeholder",
            full_ticker,
        )
        kf["indian_market_sentiment"] = "Sentiment data not available for this stock."
        parsed["key_factors"] = kf

    return parsed
