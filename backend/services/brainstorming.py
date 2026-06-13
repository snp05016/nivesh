import json
from services.llm_utils import deepseek_chat
from helpers import _extract_json_from_text

def generate_brainstorming_ideas(topic: str, risk_tolerance: str) -> dict:
    """
    Generate 3-5 investment strategies related to the topic, and suggest 3-5 Indian stock tickers.
    """
    prompt = f"""You are a financial advisor for the Indian stock market.
The user wants to brainstorm investment ideas based on the following topic: "{topic}".
Their risk tolerance is: {risk_tolerance}.

Provide 3-5 investment strategies related to this topic, and suggest 3-5 relevant Indian stock tickers.
Ensure all numbers are in Lakhs/Crores. Never use Million, Billion, or Trillion.

Output your response ONLY in valid JSON format with the following structure:
{{
    "ideas": ["Strategy 1", "Strategy 2", ...],
    "tickers": ["TICKER1.NS", "TICKER2.NS", ...]
}}
Do not include any other text or markdown outside the JSON.
"""
    messages = [{"role": "user", "content": prompt}]
    
    response = deepseek_chat(messages, max_tokens=1024, temperature=0.7)
    
    # Extract JSON string
    json_str = _extract_json_from_text(response)
    
    # Parse JSON
    parsed = json.loads(json_str)
    
    # Enforce Indian numbering system
    from main import _ban_western_scale
    _ban_western_scale(json.dumps(parsed))
    
    return parsed
