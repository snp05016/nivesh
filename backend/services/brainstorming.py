"""Investment brainstorming service.

This module provides an interface to an LLM to generate thematic investment strategies
and stock ideas based on user-provided topics and risk tolerances.
"""
import json
import logging

from services.instrument_universe import validate_tickers
from services.llm_utils import _deepseek_chat
from helpers import _extract_json_from_text, _ban_western_scale

logger = logging.getLogger(__name__)

def generate_brainstorming_ideas(topic: str, risk_tolerance: str) -> dict:
    """Generates 3-5 investment strategies related to the topic, suggesting Indian stock tickers.

    Args:
        topic (str): The investment theme or topic to brainstorm around.
        risk_tolerance (str): The user's risk tolerance profile.

    Returns:
        dict: A dictionary containing a list of generated ideas with titles, descriptions, and tickers.
    """
    prompt = f"""You are a financial advisor for the Indian stock market.
The user wants to brainstorm investment ideas based on the following topic: "{topic}".
Their risk tolerance is: {risk_tolerance}.

Provide 3-5 distinct, actionable investment strategies or angles related to this topic in the Indian market.
Each idea should be an object with:
- "title": A short catchy title (e.g. "EV Battery Infrastructure")
- "description": A 1-2 sentence description of why this angle works.
- "ticker": (Optional) An NSE/BSE stock ticker symbol that perfectly fits this idea (e.g. "RELIANCE.NS").

Ensure all numbers are in Lakhs/Crores. Never use Million, Billion, or Trillion.

Output your response ONLY in valid JSON format with the following structure:
{{
    "ideas": [
        {{
            "title": "Strategy Name",
            "description": "Why it works...",
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
