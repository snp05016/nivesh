"""
Task 19 — Relative Rotation Graph (RRG).

Computes JdK RS-Ratio and RS-Momentum for each sector vs benchmark.
Quadrants: Leading, Weakening, Lagging, Improving.
"""

from __future__ import annotations
import math
from typing import Optional


def _normalize_series(series: list[float], window: int = 10) -> list[float]:
    """
    Normalize a series to a 0-centered Z-score using a rolling window.
    Final value is compared against rolling mean/std.
    """
    if len(series) < window:
        mean = sum(series) / len(series)
        variance = sum((x - mean) ** 2 for x in series) / len(series) if len(series) > 1 else 1
        std = math.sqrt(variance) or 1
        return [(x - mean) / std for x in series]

    normalized = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        w = series[start : i + 1]
        mean = sum(w) / len(w)
        variance = sum((x - mean) ** 2 for x in w) / len(w) if len(w) > 1 else 1
        std = math.sqrt(variance) or 1
        normalized.append((series[i] - mean) / std)
    return normalized


def _compute_rs_ratio(
    sector_returns: list[float],
    benchmark_returns: list[float],
    period: int = 10,
) -> list[Optional[float]]:
    """
    JdK RS-Ratio: rolling ratio of sector cumulative return vs benchmark,
    normalized to 100 = neutral.
    """
    if len(sector_returns) != len(benchmark_returns):
        raise ValueError("sector_returns and benchmark_returns must have same length")

    ratios: list[Optional[float]] = []
    for i in range(len(sector_returns)):
        start = max(0, i - period + 1)
        sec_cum = 1.0
        ben_cum = 1.0
        for j in range(start, i + 1):
            sec_cum *= 1 + sector_returns[j]
            ben_cum *= 1 + benchmark_returns[j]
        rs_raw = sec_cum / ben_cum if ben_cum else 1.0
        ratios.append(rs_raw)

    # Normalize to 100 scale using rolling window
    valid = [r for r in ratios if r is not None]
    if not valid:
        return ratios
    mean_r = sum(valid) / len(valid)
    variance_r = sum((x - mean_r) ** 2 for x in valid) / len(valid) if len(valid) > 1 else 1
    std_r = math.sqrt(variance_r) or 1

    return [100 + (r - mean_r) / std_r * 10 for r in ratios]  # type: ignore[misc]


def _compute_rs_momentum(rs_ratio_series: list[float], period: int = 14) -> list[float]:
    """
    RS-Momentum: rate of change (momentum) of RS-Ratio over period.
    Normalized to 100 scale.
    """
    momentum = []
    for i in range(len(rs_ratio_series)):
        if i < period:
            momentum.append(100.0)
        else:
            prev = rs_ratio_series[i - period]
            curr = rs_ratio_series[i]
            if prev:
                mom = 100 + (curr - prev) / abs(prev) * 100
            else:
                mom = 100.0
            momentum.append(mom)
    return momentum


def _classify_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    """
    Classify into RRG quadrant.
    RS-Ratio axis: >100 = outperforming benchmark
    RS-Momentum axis: >100 = momentum improving

    Quadrants:
      Leading   (ratio > 100, momentum > 100): outperforming + improving
      Weakening (ratio > 100, momentum < 100): outperforming but fading
      Lagging   (ratio < 100, momentum < 100): underperforming + worsening
      Improving (ratio < 100, momentum > 100): underperforming but recovering
    """
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "LEADING"
    elif rs_ratio >= 100 and rs_momentum < 100:
        return "WEAKENING"
    elif rs_ratio < 100 and rs_momentum >= 100:
        return "IMPROVING"
    else:
        return "LAGGING"


def compute_rrg_vectors(
    sector_returns: dict[str, list[float]],
    benchmark_returns: list[float],
    rs_period: int = 10,
    momentum_period: int = 14,
) -> dict:
    """
    Compute JdK RS-Ratio and RS-Momentum for each sector vs benchmark.

    Args:
        sector_returns: dict mapping sector name → list of daily returns (floats, e.g. 0.01 = 1%)
        benchmark_returns: list of daily benchmark returns (same length as each sector).
        rs_period: period for RS-Ratio calculation.
        momentum_period: period for RS-Momentum calculation.

    Returns:
        dict mapping sector → {
            'rs_ratio': float,
            'rs_momentum': float,
            'quadrant': str,
            'trend': str,  # trajectory direction
            'rs_ratio_history': list[float],  # last 10 values for tail drawing
        }
    """
    results: dict[str, dict] = {}

    for sector, returns in sector_returns.items():
        if len(returns) < 2:
            results[sector] = {
                "rs_ratio": 100.0,
                "rs_momentum": 100.0,
                "quadrant": "LAGGING",
                "trend": "INSUFFICIENT_DATA",
                "rs_ratio_history": [],
                "error": "Insufficient data",
            }
            continue

        # Align lengths
        min_len = min(len(returns), len(benchmark_returns))
        sec = returns[-min_len:]
        bench = benchmark_returns[-min_len:]

        rs_ratio_series = _compute_rs_ratio(sec, bench, rs_period)
        # Filter out None (shouldn't happen here)
        rs_valid = [r for r in rs_ratio_series if r is not None]

        if not rs_valid:
            continue

        rs_momentum_series = _compute_rs_momentum(rs_valid, momentum_period)

        current_ratio = rs_valid[-1]
        current_momentum = rs_momentum_series[-1]
        quadrant = _classify_quadrant(current_ratio, current_momentum)

        # Compute trajectory (last 3 quadrants)
        tail_length = min(5, len(rs_valid))
        history_ratio = rs_valid[-tail_length:]
        history_momentum = rs_momentum_series[-tail_length:]

        if len(history_ratio) >= 2:
            delta_ratio = history_ratio[-1] - history_ratio[0]
            delta_momentum = history_momentum[-1] - history_momentum[0]
            if delta_ratio > 0 and delta_momentum > 0:
                trend = "STRENGTHENING"
            elif delta_ratio < 0 and delta_momentum < 0:
                trend = "WEAKENING"
            elif delta_ratio > 0:
                trend = "RATIO_IMPROVING"
            else:
                trend = "MOMENTUM_IMPROVING"
        else:
            trend = "STABLE"

        results[sector] = {
            "rs_ratio": round(current_ratio, 2),
            "rs_momentum": round(current_momentum, 2),
            "quadrant": quadrant,
            "trend": trend,
            "rs_ratio_history": [round(x, 2) for x in history_ratio],
            "rs_momentum_history": [round(x, 2) for x in history_momentum],
        }

    # Summary: rank sectors by quadrant priority
    quadrant_order = {"LEADING": 1, "IMPROVING": 2, "WEAKENING": 3, "LAGGING": 4}
    ranked = sorted(
        results.items(),
        key=lambda x: (quadrant_order.get(x[1].get("quadrant", "LAGGING"), 4), -x[1].get("rs_ratio", 0))
    )

    return {
        "sectors": results,
        "ranked_sectors": [s for s, _ in ranked],
        "leading_sectors": [s for s, v in results.items() if v.get("quadrant") == "LEADING"],
        "lagging_sectors": [s for s, v in results.items() if v.get("quadrant") == "LAGGING"],
        "improving_sectors": [s for s, v in results.items() if v.get("quadrant") == "IMPROVING"],
        "weakening_sectors": [s for s, v in results.items() if v.get("quadrant") == "WEAKENING"],
    }


if __name__ == "__main__":
    import random
    random.seed(7)

    n = 60
    benchmark = [random.uniform(-0.01, 0.012) for _ in range(n)]
    sectors = {
        "IT": [random.uniform(-0.005, 0.018) for _ in range(n)],       # slight outperform
        "Banking": [random.uniform(-0.015, 0.01) for _ in range(n)],   # slight underperform
        "FMCG": [random.uniform(-0.008, 0.013) for _ in range(n)],     # neutral
        "Auto": [random.uniform(0.000, 0.020) for _ in range(n)],      # strong outperform
    }

    rrg = compute_rrg_vectors(sectors, benchmark)
    print("RRG Results:")
    for s, v in rrg["sectors"].items():
        print(f"  {s}: RS-Ratio={v['rs_ratio']:.1f}, RS-Mom={v['rs_momentum']:.1f}, Quadrant={v['quadrant']}")
    print(f"Leading: {rrg['leading_sectors']}")
    print(f"Lagging: {rrg['lagging_sectors']}")
    assert set(rrg["sectors"].keys()) == set(sectors.keys())
    print("All relative_rotation_graph tests passed.")
