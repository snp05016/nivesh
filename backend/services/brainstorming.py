import json
from services.llm_utils import _deepseek_chat
from helpers import _extract_json_from_text

def generate_brainstorming_ideas(topic: str, risk_tolerance: str) -> dict:
    """
    Generate 3-5 investment strategies related to the topic, and suggest Indian stock tickers.
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
    try:
        from main import _ban_western_scale
        _ban_western_scale(json.dumps(parsed))
    except ImportError:
        pass
    
    return parsed
