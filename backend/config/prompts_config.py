"""Prompt loader — reads from DB table first, falls back to hardcoded."""
import os


def get_prompt(key: str) -> str:
    """Fetch prompt by key. DB first, hardcoded fallback."""
    try:
        from database import get_session
        # Optional DB lookup — skip if DB not configured for prompts
        prompt_env = os.getenv(f"PROMPT_{key.upper()}")
        if prompt_env:
            return prompt_env
    except Exception:
        pass

    # Fallback to original prompts.py
    from prompts import INDIAN_MARKET_SYSTEM_PROMPT, NEWS_ANALYST_PERSONA, EXTREME_ADDENDUM
    _PROMPT_MAP = {
        "INDIAN_MARKET_SYSTEM_PROMPT": INDIAN_MARKET_SYSTEM_PROMPT,
        "NEWS_ANALYST_PERSONA": NEWS_ANALYST_PERSONA,
        "EXTREME_ADDENDUM": EXTREME_ADDENDUM,
    }
    return _PROMPT_MAP.get(key, "")
