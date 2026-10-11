"""Investment brainstorming service.

This module provides an interface to an LLM to generate thematic investment strategies
and stock ideas based on user-provided topics and risk tolerances.
"""
import json
from services.llm_utils import _deepseek_chat
from helpers import _extract_json_from_text, _ban_western_scale

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
    
    response = _deepseek_chat(messages, max_tokens=1024, temperature=0.7)
    
    # Extract JSON string
    json_str = _extract_json_from_text(response)
    
    # Parse JSON
    parsed = json.loads(json_str)
    
    # Enforce Indian numbering system
    _ban_western_scale(json.dumps(parsed))
    
    return parsed
