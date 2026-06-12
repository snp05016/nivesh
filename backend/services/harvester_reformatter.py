"""
Nivesh Harvester — DeepSeek V4 Flash reformatter.

Turns raw scraped text (a filing, a rating action, an expert column, a
transcript) into a clean, structured, credibility-scored card.

Mirrors the main backend's `services/llm_utils.py` DeepSeek pattern
(OpenAI-compatible client at api.deepseek.com) but is fully self-contained —
the harvester shares NO code with the backend.

Contract used by the scheduler and every harvester:
  make_external_id(url, text)                         -> str   (dedup hash)
  reformat_single(raw_text, source_type,
                  source_name, original_author)       -> dict | None
  derive_card_type / derive_credibility / derive_credential  (defaults)

reformat_single returns None ONLY when the item is rejected
(credibility < 5) or there is no usable text. On LLM/network failure it falls
back to a deterministic passthrough card so a credible regulatory filing is
never silently lost.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time as _time

import openai as _openai_lib

DEEPSEEK_MODEL = "deepseek-chat"
MIN_CREDIBILITY = 5

_THINK_TAG_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)
# Emoji / pictographs (AGENTS.md §5.3 — all AI text must be emoji-stripped).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U00002190-\U000021FF]+",
    flags=re.UNICODE,
)

# ── Source-type → defaults. These are the floor when the LLM is unavailable. ──
DEFAULT_CREDIBILITY: dict[str, int] = {
    "SEBI_FILING": 10,
    "EXCHANGE_FILING": 10,
    "CRISIL_RATING": 10,
    "ICRA_RATING": 10,
    "CARE_RATING": 10,
    "INDIA_RATINGS": 10,
    "AMFI_DATA": 10,
    "SEBI_RIA_NOTE": 9,
    "FUND_MANAGER_INTERVIEW": 8,
    "BROKERAGE_RESEARCH": 7,
    "EXPERT_COLUMN": 7,
    "FINANCIAL_JOURNALIST": 6,
    "YOUTUBE": 6,
    "EARNINGS_TRANSCRIPT": 5,
}

CARD_TYPE_BY_SOURCE: dict[str, str] = {
    "SEBI_FILING": "GOVERNANCE",
    "EXCHANGE_FILING": "GOVERNANCE",
    "CRISIL_RATING": "GOVERNANCE",
    "ICRA_RATING": "GOVERNANCE",
    "CARE_RATING": "GOVERNANCE",
    "INDIA_RATINGS": "GOVERNANCE",
    "SEBI_RIA_NOTE": "GOVERNANCE",
    "AMFI_DATA": "MACRO",
    "FUND_MANAGER_INTERVIEW": "EXPERT",
    "BROKERAGE_RESEARCH": "EXPERT",
    "EXPERT_COLUMN": "EXPERT",
    "FINANCIAL_JOURNALIST": "EXPERT",
    "EARNINGS_TRANSCRIPT": "EXPERT",
    "YOUTUBE": "YOUTUBE",
}

CREDENTIAL_BY_SOURCE: dict[str, str] = {
    "SEBI_FILING": "SEBI / NSE / BSE regulatory filing — legally binding disclosure",
    "EXCHANGE_FILING": "NSE / BSE exchange filing — mandatory corporate disclosure",
    "CRISIL_RATING": "CRISIL — SEBI-regulated credit rating agency",
    "ICRA_RATING": "ICRA — SEBI-regulated credit rating agency",
    "CARE_RATING": "CARE Ratings — SEBI-regulated credit rating agency",
    "INDIA_RATINGS": "India Ratings & Research — SEBI-regulated credit rating agency",
    "SEBI_RIA_NOTE": "SEBI Registered Investment Advisor — fiduciary duty, legally accountable",
    "AMFI_DATA": "AMFI — Association of Mutual Funds in India, industry regulatory body",
    "FUND_MANAGER_INTERVIEW": "Named fund manager / market professional with track record",
    "BROKERAGE_RESEARCH": "Institutional brokerage research — compliance-reviewed",
    "EXPERT_COLUMN": "Named, bylined market columnist — editorial accountability",
    "FINANCIAL_JOURNALIST": "Named financial journalist — professional standards",
    "EARNINGS_TRANSCRIPT": "Company management's own words — primary source",
    "YOUTUBE": "SEBI-registered finance creator / market commentator",
}


def derive_card_type(source_type: str) -> str:
    return CARD_TYPE_BY_SOURCE.get((source_type or "").upper(), "EXPERT")


def derive_credibility(source_type: str) -> int:
    return DEFAULT_CREDIBILITY.get((source_type or "").upper(), 5)


def derive_credential(source_type: str) -> str:
    return CREDENTIAL_BY_SOURCE.get(
        (source_type or "").upper(), "Credentialed market source"
    )


def make_external_id(url: str, text: str) -> str:
    """Deterministic dedup hash of URL + leading content."""
    basis = f"{(url or '').strip()}|{(text or '').strip()[:1000]}"
    return hashlib.sha256(basis.encode("utf-8", "ignore")).hexdigest()


def strip_emoji(text: str) -> str:
    if not text:
        return text
    return _EMOJI_RE.sub("", text).strip()


# ═════════════════════════════════════════════════════════════════════════════
# DeepSeek client
# ═════════════════════════════════════════════════════════════════════════════

def get_deepseek_client() -> "_openai_lib.OpenAI":
    return _openai_lib.OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com/v1",
        timeout=60.0,
    )


def deepseek_chat(messages: list[dict], *, max_tokens: int = 700, temperature: float = 0.2) -> str:
    """Call DeepSeek (OpenAI-compatible). Retries 3x with backoff. May raise."""
    client = get_deepseek_client()
    last_exc: Exception | None = None
    effective_max = max(max_tokens * 4, 700)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                max_tokens=effective_max,
                temperature=temperature,
            )
            choice = resp.choices[0]
            content = choice.message.content or ""
            if not content.strip():
                content = getattr(choice.message, "reasoning_content", None) or ""
            return _THINK_TAG_RE.sub("", content).strip()
        except Exception as exc:  # noqa: BLE001 — retried, then surfaced
            last_exc = exc
            if attempt < 2:
                _time.sleep(2.0 * (2 ** attempt))

    raise RuntimeError(f"DeepSeek call failed after 3 retries: {last_exc}") from last_exc


# ═════════════════════════════════════════════════════════════════════════════
# Reformatting
# ═════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are the Nivesh Harvester reformatter for Indian equity markets.
You turn raw text from CREDENTIALED expert sources (regulatory filings, credit
rating actions, SEBI-registered advisors, named fund managers, bylined columnists,
finance creators) into one clean, structured card.

Return ONLY a single valid JSON object. No prose, no markdown fences, no emoji.

JSON schema (all keys required):
{
  "title": "<=120 char headline, no clickbait",
  "reformatted_summary": "2-4 sentences. Keep exact numbers, dates and named parties. Use Indian numbering (Lakhs/Crores, never Million/Billion/Trillion). Strip legal boilerplate.",
  "key_takeaways": ["3-5 short bullet strings, each one concrete fact or implication"],
  "tickers": ["NSE symbols in CAPS that this item is materially about, e.g. RELIANCE"],
  "sentiment": "BULLISH | BEARISH | NEUTRAL",
  "credibility_score": <integer 1-10>,
  "expert_credential": "one line on WHY this source is credible (who said it, their role/org)"
}

Credibility scoring (be strict):
  10 = regulatory filing / credit rating action (SEBI, RBI, NSE, BSE, CRISIL, ICRA, CARE, India Ratings)
   9 = SEBI Registered Investment Advisor commentary
   8 = named fund manager / professional with title + organisation
   7 = institutional brokerage research OR named bylined columnist
   6 = named financial journalist / credentialed finance creator
   5 = earnings-call transcript (primary but biased)
  <5 = anonymous / unaccountable / promotional — REJECT

If the text is anonymous, promotional, a wire-service repost with no named
author, or otherwise below 5, set credibility_score to a value below 5.

For GOVERNANCE items: surface management changes, auditor/CFO/MD resignations,
promoter pledge actions, regulatory orders, related-party / forensic issues.
For EXPERT items: name the expert and their credential, state their key call
and the evidence behind it."""


def _safe_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = _FENCE_RE.sub("", text).strip()
    # Grab the outermost {...} if there is surrounding noise.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _passthrough(raw_text: str, source_type: str, source_name: str) -> dict:
    """Deterministic card built without the LLM. Used as a robust fallback."""
    summary = strip_emoji(" ".join((raw_text or "").split()))[:400]
    return {
        "title": (summary[:117] + "...") if len(summary) > 120 else summary,
        "reformatted_summary": summary,
        "key_takeaways": [],
        "tickers": [],
        "sentiment": "NEUTRAL",
        "credibility_score": derive_credibility(source_type),
        "card_type": derive_card_type(source_type),
        "expert_credential": derive_credential(source_type),
    }


def reformat_single(
    raw_text: str,
    source_type: str,
    source_name: str = "",
    original_author: str | None = None,
) -> dict | None:
    """Reformat one raw item into a structured card dict, or None if rejected.

    Returned dict keys: title, reformatted_summary, key_takeaways (list),
    tickers (list), sentiment, credibility_score (int 5-10), card_type,
    expert_credential. card_type is always set here (derived from source_type).
    """
    if not raw_text or not raw_text.strip():
        return None

    floor_cred = derive_credibility(source_type)
    card_type = derive_card_type(source_type)

    # No API key → deterministic passthrough (still a valid, displayable card).
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        card = _passthrough(raw_text, source_type, source_name)
        return card if card["credibility_score"] >= MIN_CREDIBILITY else None

    author_hint = f"Named author/attribution: {original_author}" if original_author else "Author not explicitly named."
    user_prompt = (
        f"Source type: {source_type}\n"
        f"Source name: {source_name}\n"
        f"{author_hint}\n\n"
        f"RAW TEXT:\n{(raw_text or '').strip()[:6000]}"
    )

    try:
        out = deepseek_chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=700,
            temperature=0.2,
        )
        parsed = _safe_json(out)
    except Exception:
        parsed = None

    if not parsed:
        # LLM failure (not a credibility rejection) → keep the card at its floor.
        card = _passthrough(raw_text, source_type, source_name)
        return card if card["credibility_score"] >= MIN_CREDIBILITY else None

    # Normalise the LLM output into the strict contract.
    try:
        cred = int(parsed.get("credibility_score", floor_cred))
    except (TypeError, ValueError):
        cred = floor_cred
    cred = max(0, min(10, cred))
    if cred < MIN_CREDIBILITY:
        return None  # explicit rejection

    def _as_list(val):
        if isinstance(val, list):
            return [strip_emoji(str(x)).strip() for x in val if str(x).strip()][:8]
        if isinstance(val, str) and val.strip():
            return [strip_emoji(val).strip()]
        return []

    sentiment = str(parsed.get("sentiment", "NEUTRAL")).upper().strip()
    if sentiment not in ("BULLISH", "BEARISH", "NEUTRAL"):
        sentiment = "NEUTRAL"

    tickers = [t.upper().strip() for t in _as_list(parsed.get("tickers")) if t.strip()]

    summary = strip_emoji(str(parsed.get("reformatted_summary", ""))).strip()
    if not summary:
        summary = strip_emoji(" ".join((raw_text or "").split()))[:400]

    title = strip_emoji(str(parsed.get("title", ""))).strip()[:300]
    if not title:
        title = summary[:117] + ("..." if len(summary) > 117 else "")

    credential = strip_emoji(str(parsed.get("expert_credential", ""))).strip() or derive_credential(source_type)

    return {
        "title": title,
        "reformatted_summary": summary,
        "key_takeaways": _as_list(parsed.get("key_takeaways")),
        "tickers": tickers,
        "sentiment": sentiment,
        "credibility_score": cred,
        "card_type": card_type,
        "expert_credential": credential,
    }
