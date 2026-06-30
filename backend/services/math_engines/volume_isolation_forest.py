"""
Task 23 — Volume Anomaly Detection via Isolation Forest.

Uses sklearn IsolationForest to detect unusual price/volume combinations.
Falls back to a statistical Z-score method if sklearn is unavailable.
"""

from __future__ import annotations
import logging
import math
from typing import Optional


def _zscore_anomalies(
    prices: list[float],
    volumes: list[float],
    threshold: float = 2.5,
) -> tuple[list[float], list[bool]]:
    """Fallback Z-score anomaly detection."""
    n = len(prices)
    # Compute returns
    returns = [0.0] + [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, n)]

    # Normalize volumes
    mean_vol = sum(volumes) / n
    std_vol = math.sqrt(sum((v - mean_vol) ** 2 for v in volumes) / n) or 1

    mean_ret = sum(returns) / n
    std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / n) or 1

    scores = []
    anomalies = []
    for ret, vol in zip(returns, volumes):
        z_vol = abs(vol - mean_vol) / std_vol
        z_ret = abs(ret - mean_ret) / std_ret
        combined = math.sqrt(z_vol**2 + z_ret**2)
        scores.append(combined)
        anomalies.append(combined > threshold)

    return scores, anomalies


def detect_volume_anomalies(
    prices: list[float],
    volumes: list[float],
    contamination: float = 0.05,
) -> dict:
    """
    Detect unusual price/volume combinations using IsolationForest.

    Features: [price_return, volume, volume_change, price_volume_ratio]

    Args:
        prices: chronological list of closing prices.
        volumes: corresponding trading volumes.
        contamination: expected proportion of anomalies (default 5%).

    Returns:
        dict with 'anomaly_indices', 'anomaly_scores', 'anomaly_mask',
        'method', 'num_anomalies', 'description'
    """
    if len(prices) != len(volumes):
        raise ValueError("prices and volumes must have same length")
    if len(prices) < 10:
        return {
            "anomaly_indices": [],
            "anomaly_scores": [],
            "anomaly_mask": [False] * len(prices),
            "method": "insufficient_data",
            "num_anomalies": 0,
            "description": "Need at least 10 data points",
        }

    n = len(prices)
    returns = [0.0] + [(prices[i] - prices[i - 1]) / prices[i - 1] if prices[i - 1] else 0.0 for i in range(1, n)]
    vol_changes = [0.0] + [(volumes[i] - volumes[i - 1]) / volumes[i - 1] if volumes[i - 1] else 0.0 for i in range(1, n)]
    pv_ratios = [abs(r) * v for r, v in zip(returns, volumes)]

    try:
        from sklearn.ensemble import IsolationForest
        import numpy as np

        features = np.array(list(zip(returns, volumes, vol_changes, pv_ratios)))

        clf = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        predictions = clf.fit_predict(features)
        raw_scores = clf.score_samples(features)

        # sklearn returns -1 for anomalies, 1 for normal
        anomaly_mask = [bool(p == -1) for p in predictions]
        anomaly_scores = [float(-s) for s in raw_scores]  # negate so higher = more anomalous
        method = "isolation_forest"

    except ImportError:
        # Fallback to Z-score method
        anomaly_scores, anomaly_mask = _zscore_anomalies(prices, volumes)
        method = "zscore_fallback"

    anomaly_indices = [i for i, is_anomaly in enumerate(anomaly_mask) if is_anomaly]
    num_anomalies = len(anomaly_indices)

    # Enrich with context
    anomaly_details = []
    for idx in anomaly_indices:
        detail = {
            "index": idx,
            "price": round(prices[idx], 2),
            "volume": int(volumes[idx]),
            "return_pct": round(returns[idx] * 100, 2),
            "anomaly_score": round(anomaly_scores[idx], 4),
            "type": _classify_anomaly(returns[idx], volumes[idx], volumes),
        }
        anomaly_details.append(detail)

    return {
        "anomaly_indices": anomaly_indices,
        "anomaly_scores": [round(s, 4) for s in anomaly_scores],
        "anomaly_mask": anomaly_mask,
        "anomaly_details": anomaly_details,
        "method": method,
        "num_anomalies": num_anomalies,
        "contamination": contamination,
        "total_periods": n,
        "description": (
            f"Detected {num_anomalies} volume/price anomalies out of {n} periods "
            f"using {method}"
        ),
    }


def _classify_anomaly(price_return: float, volume: float, all_volumes: list[float]) -> str:
    """Classify the type of anomaly."""
    mean_vol = sum(all_volumes) / len(all_volumes)
    high_volume = volume > 2 * mean_vol

    if price_return > 0.03 and high_volume:
        return "BULLISH_BREAKOUT"
    elif price_return < -0.03 and high_volume:
        return "BEARISH_BREAKDOWN"
    elif high_volume:
        return "HIGH_VOLUME_STALL"
    elif abs(price_return) > 0.05:
        return "PRICE_SPIKE_LOW_VOLUME"
    else:
        return "UNUSUAL_PATTERN"


if __name__ == "__main__":
    import random
    random.seed(21)

    prices = [100.0]
    volumes = [1_000_000]
    for i in range(99):
        prices.append(prices[-1] * (1 + random.uniform(-0.015, 0.018)))
        volumes.append(int(random.uniform(500_000, 1_500_000)))

    # Inject clear anomalies
    prices[30] = prices[29] * 1.10   # 10% spike
    volumes[30] = 10_000_000          # 10x volume

    prices[60] = prices[59] * 0.92   # 8% crash
    volumes[60] = 8_000_000           # 8x volume

    result = detect_volume_anomalies(prices, volumes, contamination=0.05)
    logging.info(f"Detected {result['num_anomalies']} anomalies using {result['method']}")
    logging.info(f"Anomaly indices: {result['anomaly_indices']}")
    if result["anomaly_details"]:
        for d in result["anomaly_details"][:3]:
            logging.info(f"  Index {d['index']}: {d['type']} | return={d['return_pct']}% vol={d['volume']:,}")
    assert result["num_anomalies"] > 0, "Should detect at least the injected anomalies"
    logging.info("All volume_isolation_forest tests passed.")
