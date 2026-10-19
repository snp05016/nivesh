"""Market-theme brainstorming service.

This module asks an LLM for educational Indian market themes around a user topic, each
with an illustrative listed company. Output is research, never a recommendation (REG-02).
"""
import json
import logging

from services.instrument_universe import validate_tickers
from services.llm_utils import _deepseek_chat
from services.advisory_guard import NON_ADVISORY_RULES
from helpers import _extract_json_from_text, _ban_western_scale

logger = logging.getLogger(__name__)

def generate_brainstorming_ideas(topic: str, risk_tolerance: str) -> dict:
    """Generates 3-5 educational market themes related to the topic, each with an example ticker.

    Args:
        topic (str): The market theme or topic to brainstorm around.
        risk_tolerance (str): The risk level of themes to describe (a filter, not a profile).

    Returns:
        dict: A dictionary containing a list of generated ideas with titles, descriptions, and tickers.
    """
    prompt = f"""You are an educational research assistant for Indian market themes.
The user wants to explore market themes related to the following topic: "{topic}".
Describe themes whose typical risk level is: {risk_tolerance}.

Provide 3-5 distinct themes related to this topic in the Indian market.
Each idea should be an object with:
- "title": A short title (e.g. "EV Battery Infrastructure")
- "description": A 1-2 sentence factual description of the theme and its main risks.
- "ticker": (Optional) An NSE/BSE ticker symbol of an example listed company in this theme (illustrative, not a recommendation) (e.g. "RELIANCE.NS").

{NON_ADVISORY_RULES}
Ensure all numbers are in Lakhs/Crores. Never use Million, Billion, or Trillion.

Output your response ONLY in valid JSON format with the following structure:
{{
    "ideas": [
        {{
            "title": "Theme name",
            "description": "What the theme is and its main risks...",
            "ticker": "TICKER.NS"
        }}
    ]
}}
Do not include any other text or markdown outside the JSON.
"""
    messages = [{"role": "user", "content": prompt}]
    
    response = _deepseek_chat(messages, max_tokens=1500, temperature=0.7)

    # Extract JSON string
    json_str = _extract_json_from_text(response)

    # Parse JSON (ValueError on malformed output -> router answers 502)
    parsed = json.loads(json_str)
    raw_ideas = parsed.get("ideas") if isinstance(parsed, dict) else None

    # LLM-21: enforce Indian numbering per idea, so one bad sentence drops that idea
    # instead of failing the whole (already paid) call; keep only real listed symbols.
    ideas = []
    for idea in raw_ideas if isinstance(raw_ideas, list) else []:
        if not isinstance(idea, dict) or not idea.get("title") or not idea.get("description"):
            continue
        try:
            _ban_western_scale(json.dumps(idea))
        except ValueError:
            logger.info("[brainstorm] dropped an idea using a Western number scale")
            continue
        valid = validate_tickers([idea["ticker"]])[0] if idea.get("ticker") else []
        ideas.append({"title": str(idea["title"]), "description": str(idea["description"]),
                      "ticker": valid[0] if valid else None})
    if raw_ideas and not ideas:
        raise ValueError("every brainstorming idea failed validation")
    return {"ideas": ideas}
