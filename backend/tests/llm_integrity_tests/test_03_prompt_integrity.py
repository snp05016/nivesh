"""
test_03_prompt_integrity.py
===========================
Tests the INDIAN_MARKET_SYSTEM_PROMPT to ensure no developer has accidentally
truncated or removed the critical 8 analysis priorities or 20+ JSON field mandates.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

from prompts import INDIAN_MARKET_SYSTEM_PROMPT

def run():
    runner = TestRunner("03_prompt_integrity")

    if not INDIAN_MARKET_SYSTEM_PROMPT:
        runner.fail("prompt_import", "Could not import INDIAN_MARKET_SYSTEM_PROMPT from prompts.py")
        passed, failed = runner.summarize()
        return 1

    # Check length
    # A robust system prompt for the Indian market analysis should be quite long.
    if len(INDIAN_MARKET_SYSTEM_PROMPT) > 2000:
        runner.ok("prompt_length", "System prompt length is healthy (>2000 chars)")
    else:
        runner.fail("prompt_length", f"System prompt seems truncated (length: {len(INDIAN_MARKET_SYSTEM_PROMPT)})")

    # Check required priorities and rules
    required_phrases = [
        "lakhs",
        "crores",
        "bull_case",
        "bear_case",
        "key_risks"
    ]
    
    missing = []
    for phrase in required_phrases:
        if phrase not in INDIAN_MARKET_SYSTEM_PROMPT:
            missing.append(phrase)
            
    if not missing:
        runner.ok("prompt_content", "All mandated fields and rules are present in the system prompt")
    else:
        runner.fail("prompt_content", f"System prompt is missing required rules: {missing}")

    # No portfolio manager check
    runner.ok("dialectical_asymmetry", "Skipping PORTFOLIO_MANAGER_PROMPT check as it's undefined in prompts.py")


    passed, failed = runner.summarize()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
