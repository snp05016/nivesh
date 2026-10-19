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
