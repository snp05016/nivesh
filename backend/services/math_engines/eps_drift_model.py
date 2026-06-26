import logging
"""
EPS Drift Model (Post-Earnings Announcement Drift / PEAD).
Evaluates earnings surprises and estimate revision momentum to signal drift.
"""

from __future__ import annotations
import math


def compute_pead_signal(
    actual_eps: float,
    consensus_eps: float,
    historical_surprise_pcts: list[float],
) -> dict:
    """
    Calculates the Post-Earnings Announcement Drift (PEAD) signal.

    Args:
        actual_eps: The reported EPS for the current period.
        consensus_eps: The analyst consensus EPS estimate.
        historical_surprise_pcts: A list of past earnings surprise percentages
            (positive = beat, negative = miss).
            Used to compute standardized unexpected earnings (SUE).

    Returns:
        dict: A dictionary containing 'surprise_pct', 'sue_score', 'drift_direction',
            'expected_drift_magnitude', 'signal', and 'description'.
    """
    if consensus_eps == 0:
        return {
            "surprise_pct": 0.0,
            "sue_score": 0.0,
            "drift_direction": "NEUTRAL",
            "expected_drift_magnitude": 0.0,
            "signal": "NEUTRAL",
            "description": "Consensus EPS is zero — cannot compute surprise",
        }

    # Earnings surprise percentage
    surprise_pct = (actual_eps - consensus_eps) / abs(consensus_eps) * 100

    # Standardized Unexpected Earnings (SUE)
    # SUE = (actual - expected) / std_dev_of_historical_surprises
    if historical_surprise_pcts and len(historical_surprise_pcts) >= 2:
        n = len(historical_surprise_pcts)
        mean_hist = sum(historical_surprise_pcts) / n
        variance = sum((x - mean_hist) ** 2 for x in historical_surprise_pcts) / (n - 1)
        std_hist = math.sqrt(variance) if variance > 0 else 1.0
        sue_score = (surprise_pct - mean_hist) / std_hist
    else:
        # No history: use raw surprise as proxy
        sue_score = surprise_pct / 10.0  # normalize by assuming ~10% = 1 std

    # PEAD drift direction and magnitude
    # Research shows drift lasts 60-90 days post-announcement
    # Magnitude roughly: 0.5-3% for moderate beats, 3-8% for strong beats
    if sue_score > 2.0:
        drift_direction = "STRONG_BULLISH"
        expected_drift_magnitude = min(8.0, 2.0 + sue_score * 1.5)
        signal = "BUY"
        description = f"Strong earnings beat (SUE={sue_score:.2f}). Expect upward PEAD drift."
    elif sue_score > 0.5:
        drift_direction = "BULLISH"
        expected_drift_magnitude = min(5.0, 0.5 + sue_score * 1.0)
        signal = "MILD_BUY"
        description = f"Moderate earnings beat (SUE={sue_score:.2f}). Mild upward drift expected."
    elif sue_score < -2.0:
        drift_direction = "STRONG_BEARISH"
        expected_drift_magnitude = min(8.0, 2.0 + abs(sue_score) * 1.5)
        signal = "SELL"
        description = f"Strong earnings miss (SUE={sue_score:.2f}). Expect downward PEAD drift."
    elif sue_score < -0.5:
        drift_direction = "BEARISH"
        expected_drift_magnitude = min(5.0, 0.5 + abs(sue_score) * 1.0)
        signal = "MILD_SELL"
        description = f"Moderate earnings miss (SUE={sue_score:.2f}). Mild downward drift expected."
    else:
        drift_direction = "NEUTRAL"
        expected_drift_magnitude = 0.0
        signal = "HOLD"
        description = f"Earnings in-line with expectations (SUE={sue_score:.2f}). No significant drift."

    # Directional sign for magnitude
    signed_magnitude = (
        expected_drift_magnitude if "BULLISH" in drift_direction else
        -expected_drift_magnitude if "BEARISH" in drift_direction else
        0.0
    )

    return {
        "actual_eps": actual_eps,
        "consensus_eps": consensus_eps,
        "surprise_pct": round(surprise_pct, 2),
        "sue_score": round(sue_score, 3),
        "drift_direction": drift_direction,
        "expected_drift_pct": round(signed_magnitude, 2),
        "expected_drift_magnitude": round(expected_drift_magnitude, 2),
        "signal": signal,
        "description": description,
        "drift_horizon_days": 60,
    }


def compute_revision_momentum(
    eps_estimates_history: list[float],
    analyst_count: int = 10,
) -> dict:
    """
    Computes earnings estimate revision momentum.
    Tracks the direction and velocity of analyst estimate changes over time.

    Args:
        eps_estimates_history: Chronological list of consensus EPS estimates
            (most recent last).
        analyst_count: The number of analysts in the consensus.

    Returns:
        dict: A dictionary containing 'revision_direction', 'revision_velocity', and 'signal'.
    """
    if len(eps_estimates_history) < 2:
        return {
            "revision_direction": "STABLE",
            "revision_velocity": 0.0,
            "signal": "NEUTRAL",
            "description": "Insufficient estimate history",
        }

    # Direction: compare current vs 3-period-ago
    lookback = min(3, len(eps_estimates_history) - 1)
    current_est = eps_estimates_history[-1]
    past_est = eps_estimates_history[-1 - lookback]

    if past_est == 0:
        pct_change = 0.0
    else:
        pct_change = (current_est - past_est) / abs(past_est) * 100

    # Velocity: rate of change per period
    velocity = pct_change / lookback

    if pct_change > 5:
        direction = "STRONG_UPWARD"
        signal = "BULLISH"
    elif pct_change > 1:
        direction = "UPWARD"
        signal = "MILD_BULLISH"
    elif pct_change < -5:
        direction = "STRONG_DOWNWARD"
        signal = "BEARISH"
    elif pct_change < -1:
        direction = "DOWNWARD"
        signal = "MILD_BEARISH"
    else:
        direction = "STABLE"
        signal = "NEUTRAL"

    return {
        "revision_direction": direction,
        "revision_pct": round(pct_change, 2),
        "revision_velocity": round(velocity, 3),
        "current_estimate": current_est,
        "past_estimate": past_est,
        "lookback_periods": lookback,
        "signal": signal,
        "description": f"EPS estimates {direction.lower()} by {pct_change:.1f}% over {lookback} periods",
    }


if __name__ == "__main__":
    # Strong beat scenario
    result = compute_pead_signal(
        actual_eps=25.50,
        consensus_eps=20.00,
        historical_surprise_pcts=[-2.0, 3.0, 1.5, -1.0, 4.0],
    )
    logging.info(f"Strong beat: signal={result['signal']}, drift={result['expected_drift_pct']}%, SUE={result['sue_score']}")
    assert result["signal"] in {"BUY", "MILD_BUY"}

    # Miss scenario
    result2 = compute_pead_signal(
        actual_eps=15.00,
        consensus_eps=20.00,
        historical_surprise_pcts=[1.0, 2.0, -1.0, 0.5, 1.5],
    )
    logging.info(f"Miss: signal={result2['signal']}, drift={result2['expected_drift_pct']}%, SUE={result2['sue_score']}")
    assert result2["signal"] in {"SELL", "MILD_SELL"}

    # Revision momentum
    rev = compute_revision_momentum([18.0, 18.5, 19.0, 19.8, 20.5])
    logging.info(f"Revision: {rev['revision_direction']}, velocity={rev['revision_velocity']}")
    assert rev["signal"] in {"BULLISH", "MILD_BULLISH"}

    logging.info("All eps_drift_model tests passed.")
