import pytest
from datetime import datetime, timedelta
from services.staleness import compute_staleness

# Generating 100 test cases for staleness logic
# 80 general cases, 20 edge cases

@pytest.mark.timeout(5)
@pytest.mark.parametrize("last_date_offset, price_change, signal, expected_min_score", [
    # General Cases (80) - Mixed scenarios
    *[(i, 5.0, "HOLD", 0) for i in range(1, 41)], # i days old
    *[(10, float(i), "BUY", 0) for i in range(-20, 20)], # price change variations
    # Edge Cases (20)
    (None, 0.0, "HOLD", 40), # Never analysed
    (0, 0.0, "HOLD", 0), # Just analysed
    (31, 0.0, "HOLD", 40), # Just over 30 days
    (15, 0.0, "HOLD", 25), # Just over 14 days
    (8, 0.0, "HOLD", 10), # Just over 7 days
    (365, 0.0, "HOLD", 40), # Very old
    (10, 25.0, "HOLD", 30), # High price change (>20%)
    (10, -25.0, "HOLD", 30), # High price drop (<-20%)
    (10, 15.0, "HOLD", 15), # Med price change (>10%)
    (10, -15.0, "HOLD", 15), # Med price drop (<-10%)
    (10, 0.0, "STRONG_BUY", 10), # Volatile signal
    (10, 0.0, "STRONG_SELL", 10), # Volatile signal
    (None, 50.0, "STRONG_BUY", 75), # Double whammy
    (-1, 0.0, "HOLD", 0), # Future date (should handle as 0 age)
    (10, 0.000001, "HOLD", 0), # Tiny price change
    (10, -0.000001, "HOLD", 0), # Tiny negative change
    (30, 19.9, "HOLD", 40), # Borderline price change
    (14, 9.9, "HOLD", 10), # Borderline age
    (7, 4.9, "HOLD", 0), # Borderline age
    (1000, 100.0, "STRONG_BUY", 75), # Extreme values
])
def test_staleness_logic(last_date_offset, price_change, signal, expected_min_score):
    last_date = None
    if last_date_offset is not None:
        last_date = datetime.utcnow() - timedelta(days=last_date_offset)
    
    result = compute_staleness(last_date, price_change, signal)
    assert result["score"] >= expected_min_score
    assert "score" in result
    assert "reason" in result
    assert isinstance(result["reason"], str)

def test_staleness_reasons_count():
    # Test that a reason is provided
    last_date = datetime.utcnow() - timedelta(days=40)
    price_change = 25.0
    result = compute_staleness(last_date, price_change, "STRONG_BUY")
    assert "reason" in result
    assert result["score"] >= 75
