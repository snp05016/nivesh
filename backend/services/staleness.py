"""
Staleness scoring for Nivesh analysis results.
Returns a score 0-100 for how urgently a stock should be re-analysed.
Pure math — no AI calls, no network calls.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

# UAE offset — all timestamp comparisons use UAE Standard Time (UTC+4)
UAE_OFFSET = timedelta(hours=4)
# Market opens at 09:15 IST on weekdays
_MARKET_OPEN_HOUR = 9
_MARKET_OPEN_MINUTE = 15


def is_pre_market(analysis_date: Optional[datetime] = None) -> bool:
    """Check if an analysis was generated before market open (09:15 IST).
    Pre-market analyses use stale pre-open data and should be invalidated
    once live trading begins. Fix 2.34.
    """
    now_uae = datetime.now(timezone.utc) + UAE_OFFSET
    market_open = now_uae.replace(
        hour=_MARKET_OPEN_HOUR, minute=_MARKET_OPEN_MINUTE, second=0, microsecond=0
    )
    if analysis_date is not None:
        anal_time = analysis_date.hour * 60 + analysis_date.minute
        market_open_mins = _MARKET_OPEN_HOUR * 60 + _MARKET_OPEN_MINUTE
        if anal_time < market_open_mins and now_uae > market_open:
            return True
    return False


def compute_staleness(
    last_analysis_date: Optional[datetime],
    price_change_7d_pct: float,
    signal: str = "HOLD",
    is_ex_dividend: bool = False,
    governance_event_detected: bool = False,
    pledge_spike_pct: float = 0.0,
    vix_spike: bool = False,
    earnings_window: bool = False,
    fii_outflow_crores: float = 0.0,
) -> dict:
    score = 0
    reasons = []

    # Age of analysis (weight 40) — uses IST to avoid midnight false positives
    if last_analysis_date is None:
        score += 40
        reasons.append("never analysed")
    else:
        now_uae = datetime.now(timezone.utc) + UAE_OFFSET
        age_days = (now_uae - last_analysis_date).days
        if age_days > 30:
            score += 40
            reasons.append(f"analysis is {age_days}d old")
        elif age_days > 14:
            score += 25
            reasons.append(f"analysis is {age_days}d old")
        elif age_days > 7:
            score += 15
            reasons.append(f"analysis is {age_days}d old")
        elif age_days > 2:
            score += 5
            reasons.append(f"analysis is {age_days}d old")

    # Price movement (weight 35)
    # Fix 2.51: skip price-drop penalty on ex-dividend dates —
    # the mechanical price adjustment is NOT a fundamental decline
    if is_ex_dividend and price_change_7d_pct < 0:
        reasons.append(f"ex-dividend price adjustment ({price_change_7d_pct:+.1f}%) — excluded from staleness")
    else:
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

    # ── Enhanced staleness triggers (GAP 9) ──
    if governance_event_detected:
        score = 100
        reasons.append("governance event detected")
    else:
        if pledge_spike_pct > 5:
            score += 30
            reasons.append(f"pledge spike of {pledge_spike_pct:.1f}%")
        if vix_spike:
            score += 20
            reasons.append("VIX spike detected")
        if fii_outflow_crores > 5000:
            score += 15
            reasons.append(f"FII outflow of ₹{fii_outflow_crores:.0f} Cr")

    if earnings_window:
        score = max(score, 20)
        reasons.append("within earnings window")

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
