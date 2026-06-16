"""
test_02_concurrency_dedup.py
============================
Tests the threading lock deduplication to ensure identical requests
for the same ticker don't spawn redundant LLM jobs.
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

from core.concurrency import (
    _acquire_analysis_slot,
    _release_analysis_slot,
    _force_clear_analysis_slot,
    _running_analyses
)

def run():
    runner = TestRunner("02_concurrency_dedup")

    # Clean state
    _force_clear_analysis_slot(999)

    # Test 1: First request should acquire the slot immediately
    acquired1 = _acquire_analysis_slot(999)
    if acquired1:
        runner.ok("slot_initial", "First slot acquisition successful")
    else:
        runner.fail("slot_initial", "Failed to acquire initial slot")

    # Test 2: Second identical request should fail (or block until timeout)
    acquired2 = _acquire_analysis_slot(999)
    if not acquired2:
        runner.ok("slot_dedup", "Second concurrent request correctly blocked/deduped")
    else:
        runner.fail("slot_dedup", "Second request bypassed the lock!")

    # Test 3: Release the slot and acquire again
    _release_analysis_slot(999)
    acquired3 = _acquire_analysis_slot(999)
    if acquired3:
        runner.ok("slot_release", "Successfully acquired slot after release")
    else:
        runner.fail("slot_release", "Failed to acquire slot after release")
    
    _release_analysis_slot(999)

    # Test 4: Different user should acquire fine
    acquired4 = _acquire_analysis_slot(999)
    acquired5 = _acquire_analysis_slot(1000)
    if acquired4 and acquired5:
        runner.ok("slot_independent", "Different users acquired slots independently")
    else:
        runner.fail("slot_independent", "Different users collided on lock")
        
    _release_analysis_slot(999)
    _release_analysis_slot(1000)

    passed, failed = runner.summarize()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
