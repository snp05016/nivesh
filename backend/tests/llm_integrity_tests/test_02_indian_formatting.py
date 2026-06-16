"""
test_02_indian_formatting.py
============================
Tests the enforcement of Indian numeric systems (Lakhs/Crores)
and the strict prohibition of Western scales (Millions/Billions).
Also verifies emoji stripping for clean iOS UI rendering.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

from main import _ban_western_scale
from services.harvester_reformatter import strip_emoji

def run():
    runner = TestRunner("02_indian_formatting")

    # Test 1: Ban Western Scales
    western_string = "Reliance announced a deal worth 500 Million USD."
    try:
        _ban_western_scale(western_string)
        runner.fail("western_scale_ban", "Failed to block 'Million'")
    except ValueError as e:
        runner.ok("western_scale_ban", "Successfully blocked 'Million'")

    western_string_2 = "The market cap crossed a Billion."
    try:
        _ban_western_scale(western_string_2)
        runner.fail("western_scale_ban_2", "Failed to block 'Billion'")
    except ValueError as e:
        runner.ok("western_scale_ban_2", "Successfully blocked 'Billion'")

    # Test 2: Allow valid Indian scales
    indian_string = "Reliance announced a deal worth 500 Crores."
    try:
        res = _ban_western_scale(indian_string)
        if res == indian_string:
            runner.ok("indian_scale_allow", "Successfully allowed 'Crores'")
        else:
            runner.fail("indian_scale_allow", "Modified a valid Indian string")
    except ValueError as e:
        runner.fail("indian_scale_allow", f"Incorrectly blocked Indian string: {e}")

    # Test 3: Emoji stripping
    dirty_string = "The market is bullish! 🚀 Let's go to the moon 🌙"
    clean_string = strip_emoji(dirty_string)
    if "🚀" not in clean_string and "🌙" not in clean_string:
        runner.ok("strip_emoji", "Successfully stripped emojis")
    else:
        runner.fail("strip_emoji", f"Failed to strip emojis: {clean_string}")

    passed, failed = runner.summarize()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
