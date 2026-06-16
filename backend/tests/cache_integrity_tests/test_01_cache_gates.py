"""
test_01_cache_gates.py
======================
Tests the cache staleness scoring logic to ensure API credits are not wasted
on unnecessary LLM runs.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

from services.staleness import compute_staleness, is_pre_market, UAE_OFFSET

def run():
    runner = TestRunner("01_cache_gates")

    now = datetime.utcnow() + UAE_OFFSET

    # Test 1: Fresh analysis (0-19)
    # Just analyzed, no price movement
    fresh_date = now - timedelta(hours=2)
    res1 = compute_staleness(last_analysis_date=fresh_date, price_change_7d_pct=1.0)
    score1 = res1["score"]
    if score1 < 20:
        runner.ok("score_fresh", f"Recent analysis got FRESH score: {score1}")
    else:
        runner.fail("score_fresh", f"Recent analysis got non-fresh score {score1}: {res1['reason']}")

    # Test 2: Price movement (>10%) should force STALE (score > 44)
    # Wait, the rule is: 35 for price movement + 45 for age > 2 days = 80.
    # But if age is < 2 days, score is 35 (AGING, not STALE).
    res2 = compute_staleness(last_analysis_date=fresh_date, price_change_7d_pct=11.0)
    score2 = res2["score"]
    if score2 >= 35:
        runner.ok("score_price_movement", f"11% move got score: {score2}")
    else:
        runner.fail("score_price_movement", f"11% move ignored, score: {score2}")

    # Test 3: Governance event forces URGENT (100)
    res3 = compute_staleness(
        last_analysis_date=fresh_date,
        price_change_7d_pct=0.0,
        governance_event_detected=True
    )
    score3 = res3["score"]
    if score3 == 100:
        runner.ok("score_governance", "Governance event correctly forced score to 100")
    else:
        runner.fail("score_governance", f"Governance event didn't force 100, got {score3}")

    # Test 4: Missing analysis forces STALE
    res4 = compute_staleness(last_analysis_date=None, price_change_7d_pct=0.0)
    score4 = res4["score"]
    if score4 >= 40:
        runner.ok("score_never_analysed", f"Never analysed got score: {score4}")
    else:
        runner.fail("score_never_analysed", f"Never analysed got low score: {score4}")

    # Test 5: Ex-dividend price drop exception
    res5 = compute_staleness(
        last_analysis_date=fresh_date,
        price_change_7d_pct=-15.0,
        is_ex_dividend=True
    )
    score5 = res5["score"]
    # If ex-dividend, price drop is ignored
    if score5 < 20:
        runner.ok("score_ex_dividend", f"Ex-dividend drop correctly ignored, score: {score5}")
    else:
        runner.fail("score_ex_dividend", f"Ex-dividend drop punished with score {score5}: {res5['reason']}")

    passed, failed = runner.summarize()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
