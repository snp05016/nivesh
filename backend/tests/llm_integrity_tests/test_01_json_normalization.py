"""
test_01_json_normalization.py
=============================
Tests the strict JSON extractor and normalizer to ensure it forces the LLM outputs
into the 20+ field schema mandated by the Karpathy principles.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

from services.orchestrator import _extract_json_from_text, _normalize_response

def run():
    runner = TestRunner("01_json_normalization")

    # Test 1: Extract JSON from markdown
    raw_text = \"\"\"
Here is your analysis:
```json
{
  "signal": "buy",
  "confidence_pct": 95,
  "target_prices": {"bull": 100, "base": 90, "bear": 80}
}
```
Good luck!
\"\"\"
    try:
        extracted = _extract_json_from_text(raw_text)
        parsed = json.loads(extracted)
        if parsed.get("signal") == "buy":
            runner.ok("extract_json", "Successfully extracted JSON from markdown block")
        else:
            runner.fail("extract_json", "Extracted wrong content")
    except Exception as e:
        runner.fail("extract_json", f"Extraction crashed: {e}")

    # Test 2: Normalize missing fields
    partial_data = {
        "signal": "strong_buy",
        "confidence_pct": "80", # Should be cast to int
        # Missing targets, arrays, etc.
    }
    
    try:
        norm = _normalize_response(partial_data)
        
        # Test basic casts
        if norm["signal"] == "BULLISH" and norm["confidence_pct"] == 80:
            runner.ok("normalize_basic", "Normalized signal to uppercase and cast int")
        else:
            runner.fail("normalize_basic", f"Failed basic normalization: {norm}")
            
        # Test structural repairs
        if isinstance(norm.get("bull_case"), list) and isinstance(norm.get("target_prices"), dict):
            runner.ok("normalize_structure", "Repaired missing lists and dicts")
        else:
            runner.fail("normalize_structure", f"Failed to repair missing nested structures")
            
    except Exception as e:
        runner.fail("normalize_crash", f"Normalizer crashed on partial data: {e}")


    passed, failed = runner.summarize()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
