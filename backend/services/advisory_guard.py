"""Server-side boundary between research output and advice (REG-02).

Nivesh is not a SEBI-registered Research Analyst or Investment Adviser, so by default
no price target, upside or buy/sell instruction leaves the server, and every LLM prompt
that writes user-facing text carries NON_ADVISORY_RULES. Set ADVISORY_OUTPUT_ENABLED=true
only once a SEBI-registered entity operates the app. It re-enables report price targets
(including extreme-scan scenarios/fair value and the Excel Target columns) and, through the
non-zero targets, the personalised /portfolio/timeframe-conflicts text (IA-type advice).
"""
import os

NON_ADVISORY_RULES = (
    "You are not a SEBI-registered adviser or research analyst. Do not recommend buying, "
    "selling, holding, accumulating or exiting any security. Do not give price targets, "
    "stop-losses or entry levels. Do not tell the user what to do. State facts and data only."
)
TARGETS_WITHHELD_NOTE = "Price targets are not provided."

_TARGET_KEYS = ("short_term_3m", "medium_term_12m", "long_term_36m")
_UPSIDE_KEYS = ("short_term", "medium_term", "long_term")


def advisory_output_enabled() -> bool:
    """True only when the operator set ADVISORY_OUTPUT_ENABLED (registered entity)."""
    return os.getenv("ADVISORY_OUTPUT_ENABLED", "false").strip().lower() in ("1", "true", "yes")


def strip_advisory_fields(result: dict) -> dict:
    """Unless advisory output is enabled: zero the price targets, upside and target bounds,
    null the conformal 3M band, empty the extreme-scan scenarios, null the valuation-band
    fair/bull/bear values and note in the disclaimer that targets are not provided.

    The required keys stay because the shipped iOS app decodes them; it hides SCENARIO
    ANALYSIS for an empty scenarios dict and the FAIR VALUE row for a nil fair_value.
    Never adds scenarios/valuation_bands to a standard scan. Mutates and returns result;
    idempotent.
    """
    if advisory_output_enabled():
        return result
    result["target_prices"] = dict.fromkeys(_TARGET_KEYS, 0.0)
    result["upside_downside_pct"] = dict.fromkeys(_UPSIDE_KEYS, 0.0)
    result["target_price_bounds"] = {
        k: {"lower": 0.0, "mid": 0.0, "upper": 0.0, "coverage_pct": None} for k in _TARGET_KEYS
    }
    result["conformal_target_upper_3m"] = None
    result["conformal_target_lower_3m"] = None
    if "scenarios" in result:
        result["scenarios"] = {}
    bands = result.get("valuation_bands")
    if isinstance(bands, dict):
        bands.update(fair_value=None, bull_value=None, bear_value=None)
    disclaimer = str(result.get("disclaimer") or "").strip()
    if TARGETS_WITHHELD_NOTE not in disclaimer:
        result["disclaimer"] = f"{disclaimer} {TARGETS_WITHHELD_NOTE}".strip()
    return result


# ---- Output-side backstop for free-text Copilot replies (ai-copilot-be) ----
import re

ADVICE_REFUSAL_TEXT = (
    "I can't give buy, sell or hold views, price targets or stop-loss levels. I can explain how "
    "something works, summarise your holdings, or open a stock's page in Nivesh."
)

_ACT = r"(?:buy|sell|hold|accumulat|exit|book|add|averag|switch|invest|trim|enter)\w*"
_START = r"(?:^\s*(?:[-*•]\s*|\d+[.)]\s+)?|(?<=[.!?])\s+)"
ADVICE_PATTERNS = {
    "first_person_advice": r"\b(?:i|we)(?:['’]d|\s+would)?\s+(?:strongly\s+)?(?:recommend|suggest|advise)\s+(?:you\s+)?(?:to\s+)?" + _ACT,
    "my_recommendation": r"\bmy\s+(?:recommendation|advice|suggestion)\s+(?:is|would\s+be)\s+to\s+" + _ACT,
    "you_should_act": r"\byou\s+(?:should|must|ought\s+to|might\s+want\s+to|may\s+want\s+to|could\s+consider)\s+(?:consider\s+)?" + _ACT,
    "consider_acting": r"\b(?:consider|try)\s+(?:buy|sell|accumulat|exit|book)\w*",
    "act_now": r"\b(?:buy|sell|accumulate|exit)\s+(?:now|today|immediately|on\s+dips|at\s+(?:₹|rs\.?|inr)?\s?\d)",
    "imperative": _START + r"(?:buy|sell|accumulate|avoid|exit|book\s+profits?(?:\s+(?:in|on))?)\s+(?:it|this|that|these|those|now|today|here|immediately|the\s+stock)\b|" + _START + r"(?:buy|sell|accumulate|avoid|exit|book\s+profits?\s+(?:in|on))\s+(?-i:[A-Z][A-Z0-9&.\-]{1,19}\b|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    "level_with_number": r"\b(?:target\s+price|price\s+target|stop[\s-]?loss|entry\s+(?:price|level))\s*(?:of|at|is|:|near|around)?\s*(?:₹|rs\.?|inr)?\s?\d",
    "hype_terms": r"\b(?:strong\s+(?:buy|sell)|top\s+pick|multi-?bagger|sure[\s-]?shot)\b",
    "guaranteed_returns": _START + r"(?![^.!?]*\b(?:no|not|never|nothing|cannot|can't)\b)[^.!?]*?\b(?:guaranteed|risk[\s-]?free)\s+(?:returns?|profits?|gains?)\b",
    "good_buy": r"\b(?:is|looks|seems)\s+(?:like\s+)?(?:a\s+)?(?:good|great|bad|strong|solid)\s+(?:buy|sell|bet|investment)\b",
    "worth_acting": r"\bworth\s+(?:buying|holding|selling|accumulating|adding)\b",
    "timing": r"\b(?:good|right|best|bad|ideal)\s+time\s+to\s+(?:buy|sell|invest|enter|exit|book)\b",
    "view_terms": r"\b(?:bullish|bearish)\s+on\s+(?-i:[A-Z])",
    "hinglish": r"\b(?:kharid|khareed|bech)\s*(?:lo|do|lijiye|dijiye)\b",
}
_COMPILED = {k: re.compile(v, re.IGNORECASE | re.MULTILINE) for k, v in ADVICE_PATTERNS.items()}


def find_advice(text: str) -> list[str]:
    """Ids of the advice patterns that match `text` (empty when none do)."""
    return [k for k, rx in _COMPILED.items() if rx.search(text)]
