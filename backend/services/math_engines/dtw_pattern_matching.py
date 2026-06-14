"""
Task 28 — DTW Chart Pattern Matching.

Uses Dynamic Time Warping (DTW) to match price series against
canonical chart pattern templates.
"""

from __future__ import annotations
import math


def dtw_distance(s1: list[float], s2: list[float]) -> float:
    """
    Classic O(n*m) Dynamic Time Warping distance.

    DTW finds the optimal alignment between two time series,
    allowing elastic matching that's invariant to local time shifts.

    Args:
        s1: first time series (list of floats).
        s2: second time series (list of floats).

    Returns:
        DTW distance (lower = more similar).
    """
    n, m = len(s1), len(s2)
    if n == 0 or m == 0:
        return float("inf")

    # Initialize cost matrix
    INF = float("inf")
    dtw = [[INF] * m for _ in range(n)]
    dtw[0][0] = abs(s1[0] - s2[0])

    for i in range(1, n):
        dtw[i][0] = dtw[i - 1][0] + abs(s1[i] - s2[0])
    for j in range(1, m):
        dtw[0][j] = dtw[0][j - 1] + abs(s1[0] - s2[j])

    for i in range(1, n):
        for j in range(1, m):
            cost = abs(s1[i] - s2[j])
            dtw[i][j] = cost + min(
                dtw[i - 1][j],     # insertion
                dtw[i][j - 1],     # deletion
                dtw[i - 1][j - 1], # match
            )

    return dtw[n - 1][m - 1]


def _normalize_pattern(prices: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]."""
    mn = min(prices)
    mx = max(prices)
    rng = mx - mn
    if rng == 0:
        return [0.5] * len(prices)
    return [(p - mn) / rng for p in prices]


def _build_templates() -> dict[str, list[float]]:
    """
    Build canonical chart pattern templates (normalized [0,1], 20 points each).

    Templates are idealized shapes — DTW handles time-warping.
    """
    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    n = 20  # points per template

    templates: dict[str, list[float]] = {}

    # Head and Shoulders (bearish reversal)
    hs = []
    for i in range(n):
        t = i / (n - 1)
        if t < 0.2:
            hs.append(lerp(0.3, 0.6, t / 0.2))       # left shoulder up
        elif t < 0.35:
            hs.append(lerp(0.6, 0.4, (t - 0.2) / 0.15))  # left shoulder down
        elif t < 0.55:
            hs.append(lerp(0.4, 1.0, (t - 0.35) / 0.2))  # head up
        elif t < 0.65:
            hs.append(lerp(1.0, 0.4, (t - 0.55) / 0.1))  # head down
        elif t < 0.8:
            hs.append(lerp(0.4, 0.6, (t - 0.65) / 0.15))  # right shoulder up
        else:
            hs.append(lerp(0.6, 0.1, (t - 0.8) / 0.2))    # breakdown
    templates["HEAD_AND_SHOULDERS"] = hs

    # Inverse Head and Shoulders (bullish reversal)
    ihs = [1.0 - v for v in hs]
    templates["INVERSE_HEAD_AND_SHOULDERS"] = ihs

    # Double Top (bearish)
    dt = []
    for i in range(n):
        t = i / (n - 1)
        if t < 0.25:
            dt.append(lerp(0.3, 1.0, t / 0.25))
        elif t < 0.4:
            dt.append(lerp(1.0, 0.4, (t - 0.25) / 0.15))
        elif t < 0.65:
            dt.append(lerp(0.4, 1.0, (t - 0.4) / 0.25))
        elif t < 0.8:
            dt.append(lerp(1.0, 0.4, (t - 0.65) / 0.15))
        else:
            dt.append(lerp(0.4, 0.1, (t - 0.8) / 0.2))
    templates["DOUBLE_TOP"] = dt

    # Double Bottom (bullish)
    templates["DOUBLE_BOTTOM"] = [1.0 - v for v in dt]

    # Ascending Triangle (bullish)
    at = []
    for i in range(n):
        t = i / (n - 1)
        # Flat top resistance at 1.0, rising support
        support = 0.2 + 0.6 * t
        top = 1.0
        if i % 4 < 2:
            at.append(support + (top - support) * 0.9)  # near top
        else:
            at.append(support)  # bounce off support
    templates["ASCENDING_TRIANGLE"] = at

    # Descending Triangle (bearish)
    templates["DESCENDING_TRIANGLE"] = [1.0 - v for v in at]

    return templates


_TEMPLATES = _build_templates()

# Expected direction for each pattern
_PATTERN_DIRECTION: dict[str, str] = {
    "HEAD_AND_SHOULDERS": "BEARISH",
    "INVERSE_HEAD_AND_SHOULDERS": "BULLISH",
    "DOUBLE_TOP": "BEARISH",
    "DOUBLE_BOTTOM": "BULLISH",
    "ASCENDING_TRIANGLE": "BULLISH",
    "DESCENDING_TRIANGLE": "BEARISH",
}


def detect_chart_pattern(
    prices: list[float],
    min_length: int = 15,
) -> dict:
    """
    Match prices against canonical chart pattern templates using DTW.

    Args:
        prices: chronological list of closing prices (at least 15 points).
        min_length: minimum price window length to consider.

    Returns:
        dict with 'pattern', 'confidence', 'expected_direction',
        'dtw_distance', 'all_scores', 'description'
    """
    if len(prices) < min_length:
        return {
            "pattern": "NONE",
            "confidence": 0.0,
            "expected_direction": "NEUTRAL",
            "dtw_distance": float("inf"),
            "all_scores": {},
            "description": f"Need at least {min_length} price points",
        }

    # Use the last 20-40 prices (recent pattern)
    window_size = min(40, len(prices))
    recent = prices[-window_size:]
    norm_prices = _normalize_pattern(recent)

    # Resample to 20 points (same as templates) using linear interpolation
    target_len = 20
    resampled = []
    for i in range(target_len):
        t = i / (target_len - 1) * (len(norm_prices) - 1)
        lo = int(t)
        hi = min(lo + 1, len(norm_prices) - 1)
        frac = t - lo
        resampled.append(norm_prices[lo] * (1 - frac) + norm_prices[hi] * frac)

    # Compute DTW distance to each template
    scores: dict[str, float] = {}
    for name, template in _TEMPLATES.items():
        dist = dtw_distance(resampled, template)
        scores[name] = round(dist, 4)

    best_pattern = min(scores, key=lambda x: scores[x])
    best_dist = scores[best_pattern]

    # Convert distance to confidence (0-100%)
    # Distance of 0 = perfect match, larger = worse
    max_possible_dist = math.sqrt(target_len)  # worst case with normalized [0,1] values
    confidence = max(0.0, 1.0 - best_dist / max_possible_dist) * 100

    expected_direction = _PATTERN_DIRECTION.get(best_pattern, "NEUTRAL")

    # Only report meaningful patterns (confidence > 30%)
    if confidence < 30:
        return {
            "pattern": "UNCLEAR",
            "confidence": round(confidence, 1),
            "expected_direction": "NEUTRAL",
            "dtw_distance": round(best_dist, 4),
            "all_scores": scores,
            "description": "No clear chart pattern detected",
        }

    return {
        "pattern": best_pattern,
        "confidence": round(confidence, 1),
        "expected_direction": expected_direction,
        "dtw_distance": round(best_dist, 4),
        "all_scores": scores,
        "description": (
            f"Detected {best_pattern.replace('_', ' ').title()} "
            f"with {confidence:.0f}% confidence — {expected_direction} signal"
        ),
    }


if __name__ == "__main__":
    import random
    random.seed(77)

    # Test DTW distance
    s1 = [1, 2, 3, 4, 5]
    s2 = [1, 2, 3, 4, 5]
    assert dtw_distance(s1, s2) == 0.0, "Identical series must have distance 0"

    s3 = [5, 4, 3, 2, 1]
    d = dtw_distance(s1, s3)
    print(f"DTW([1,2,3,4,5], [5,4,3,2,1]) = {d:.2f}")
    assert d > 0

    # Test pattern detection with a synthetic double-top shape
    # Rising, peak, small dip, peak again, then decline
    double_top_prices = (
        [100 + i * 5 for i in range(5)] +    # rise
        [125, 120, 115] +                      # first peak + dip
        [120, 125, 123] +                      # second peak
        [118, 110, 100, 90, 80, 75, 70]        # decline
    )
    result = detect_chart_pattern(double_top_prices)
    print(f"Pattern: {result['pattern']}, Confidence: {result['confidence']}%, "
          f"Direction: {result['expected_direction']}")
    print(f"All scores: {result['all_scores']}")
    assert result["pattern"] in {
        "DOUBLE_TOP", "HEAD_AND_SHOULDERS", "DESCENDING_TRIANGLE", "UNCLEAR"
    }

    # Random walk - likely UNCLEAR
    rand_prices = [100.0]
    for _ in range(30):
        rand_prices.append(rand_prices[-1] * (1 + random.uniform(-0.02, 0.02)))
    result2 = detect_chart_pattern(rand_prices)
    print(f"Random walk: {result2['pattern']}, Confidence: {result2['confidence']}%")

    print("All dtw_pattern_matching tests passed.")
