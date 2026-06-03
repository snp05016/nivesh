"""
Staleness scoring for Nivesh analysis results.
Returns a score 0-100 for how urgently a stock should be re-analysed.
Pure math — no AI calls, no network calls.
"""
from datetime import datetime
from typing import Optional


def compute_staleness(
    last_analysis_date: Optional[datetime],
    price_change_7d_pct: float,
    signal: str = "HOLD",
) -> dict:
    score = 0
    reasons = []

    # Age of analysis (weight 40)
    if last_analysis_date is None:
        score += 40
        reasons.append("never analysed")
    else:
        age_days = (datetime.utcnow() - last_analysis_date).days
        if age_days > 30:
            score += 40
            reasons.append(f"analysis is {age_days}d old")
        elif age_days > 14:
            score += 25
            reasons.append(f"analysis is {age_days}d old")
        elif age_days > 7:
            score += 10
            reasons.append(f"analysis is {age_days}d old")

    # Price movement (weight 35)
    abs_chg = abs(price_change_7d_pct)
    if abs_chg > 10:
        score += 35
        reasons.append(f"price moved {price_change_7d_pct:+.1f}% in 7d")
    elif abs_chg > 5:
        score += 20
        reasons.append(f"price moved {price_change_7d_pct:+.1f}% in 7d")
    elif abs_chg > 2:
        score += 8
        reasons.append(f"price moved {price_change_7d_pct:+.1f}% in 7d")

    # Signal mismatch (weight 15)
    sig = (signal or "").upper()
    if sig == "BEARISH" and price_change_7d_pct > 5:
        score += 15
        reasons.append("price rising against BEARISH signal")
    elif sig == "BULLISH" and price_change_7d_pct < -5:
        score += 15
        reasons.append("price falling against BULLISH signal")

    score = min(score, 100)

    if score >= 70:
        urgency = "URGENT"
    elif score >= 45:
        urgency = "STALE"
    elif score >= 20:
        urgency = "AGING"
    else:
        urgency = "FRESH"

    return {
        "score": score,
        "urgency": urgency,
        "reason": reasons[0] if reasons else "analysis is current",
    }
