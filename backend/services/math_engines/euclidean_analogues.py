"""
Euclidean and Cosine historical analogue matching.
Finds historical price patterns that most closely resemble the current window.
"""

from __future__ import annotations
import math


def _normalize_window(prices: list[float]) -> list[float]:
    """
    Applies min-max normalization to scale a price window into the [0, 1] range.

    Args:
        prices: A sequence of historical or current prices.

    Returns:
        list[float]: The normalized sequence of prices.
    """
    min_p = min(prices)
    max_p = max(prices)
    rng = max_p - min_p
    if rng == 0:
        return [0.5] * len(prices)
    return [(p - min_p) / rng for p in prices]


def _euclidean_distance(a: list[float], b: list[float]) -> float:
    """
    Computes the standard Euclidean distance between two equal-length vectors.

    Args:
        a: The first normalized vector.
        b: The second normalized vector.

    Returns:
        float: The computed Euclidean distance.

    Raises:
        ValueError: If vectors differ in length.
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must have same length: {len(a)} vs {len(b)}")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """
    Computes cosine distance (1 - cosine_similarity) between two vectors.

    Args:
        a: The first normalized vector.
        b: The second normalized vector.

    Returns:
        float: 0.0 for identical direction, up to 2.0 for opposite direction.

    Raises:
        ValueError: If vectors differ in length.
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must have same length: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(y ** 2 for y in b))
    if mag_a == 0 or mag_b == 0:
        return 1.0
    similarity = dot / (mag_a * mag_b)
    # Clamp to [-1, 1] to handle floating point errors
    similarity = max(-1.0, min(1.0, similarity))
    return 1.0 - similarity


def find_historical_analogues(
    current_window: list[float],
    historical_windows: list[tuple[str, list[float]]],
    n_analogues: int = 5,
    method: str = "euclidean",
) -> list[dict]:
    """
    Find N closest historical price patterns to the current window.

    Args:
        current_window: Normalized 90-day (or any length) price vector.
        historical_windows: List of (date_str, prices) tuples.
            Each prices list should be the same length as current_window.
        n_analogues: Number of closest analogues to return.
        method: Similarity method, either 'euclidean' or 'cosine'.

    Returns:
        list[dict]: A list of dicts sorted by similarity, each containing 'rank',
            'date', 'distance', 'similarity_pct', and 'forward_return' (if available).
    """
    if not historical_windows:
        return []

    norm_current = _normalize_window(current_window)
    current_len = len(norm_current)

    if method not in {"euclidean", "cosine"}:
        raise ValueError(f"method must be 'euclidean' or 'cosine', got '{method}'")

    dist_fn = _euclidean_distance if method == "euclidean" else _cosine_distance

    scored: list[dict] = []
    for date_str, hist_prices in historical_windows:
        if len(hist_prices) < current_len:
            continue
        # Use the last current_len prices of each historical window
        window = hist_prices[-current_len:]
        norm_hist = _normalize_window(window)

        try:
            dist = dist_fn(norm_current, norm_hist)
        except ValueError:
            continue

        scored.append({
            "date": date_str,
            "distance": round(dist, 6),
            "prices": hist_prices,
        })

    # Sort by distance ascending (lower = more similar)
    scored.sort(key=lambda x: x["distance"])
    top_n = scored[:n_analogues]

    # Compute similarity percentage (1 / (1 + distance)) normalized
    results: list[dict] = []
    for rank, item in enumerate(top_n, start=1):
        sim_pct = round(1.0 / (1.0 + item["distance"]) * 100, 2)
        result = {
            "rank": rank,
            "date": item["date"],
            "distance": item["distance"],
            "similarity_pct": sim_pct,
            "method": method,
        }
        results.append(result)

    return results


def compute_analogue_consensus(
    analogues: list[dict],
    historical_forward_returns: dict[str, float],
    horizon_label: str = "30d",
) -> dict:
    """
    Given analogue dates and a lookup of forward returns, compute consensus.

    Args:
        analogues: Output produced by find_historical_analogues.
        historical_forward_returns: Dictionary mapping date_str to forward_return_pct.
        horizon_label: Label for the horizon (e.g. '30d').

    Returns:
        dict: A dictionary with 'consensus_return', 'bullish_count', 'bearish_count',
            'confidence', and 'description'.
    """
    returns_found = []
    for analogue in analogues:
        fwd = historical_forward_returns.get(analogue["date"])
        if fwd is not None:
            returns_found.append(fwd * analogue["similarity_pct"] / 100)

    if not returns_found:
        return {
            "consensus_return": 0.0,
            "bullish_count": 0,
            "bearish_count": 0,
            "confidence": 0.0,
            "horizon": horizon_label,
            "description": "No forward return data available for analogues",
        }

    # Weighted average by similarity
    total_weight = sum(a["similarity_pct"] / 100 for a in analogues[:len(returns_found)])
    if total_weight == 0:
        consensus = sum(returns_found) / len(returns_found)
    else:
        consensus = sum(returns_found) / total_weight

    bullish = sum(1 for r in returns_found if r > 0)
    bearish = sum(1 for r in returns_found if r < 0)
    confidence = max(bullish, bearish) / len(returns_found) * 100 if returns_found else 0

    return {
        "consensus_return": round(consensus, 4),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "total_analogues": len(returns_found),
        "confidence": round(confidence, 2),
        "horizon": horizon_label,
        "description": (
            f"Analogue consensus: {consensus:.1%} expected return over {horizon_label}. "
            f"{bullish}/{len(returns_found)} analogues bullish."
        ),
    }


if __name__ == "__main__":
    import random
    random.seed(13)

    def gen_window(n: int = 90, drift: float = 0.001) -> list[float]:
        p = [100.0]
        for _ in range(n - 1):
            p.append(p[-1] * (1 + drift + random.uniform(-0.02, 0.02)))
        return p

    current = gen_window(90, drift=0.002)
    hist = [(f"2020-0{i+1}-01", gen_window(90, drift=random.uniform(-0.002, 0.003))) for i in range(9)]

    analogues_e = find_historical_analogues(current, hist, n_analogues=3, method="euclidean")
    print("Euclidean analogues:")
    for a in analogues_e:
        print(f"  Rank {a['rank']}: {a['date']} distance={a['distance']:.4f} sim={a['similarity_pct']}%")
    assert len(analogues_e) <= 3

    analogues_c = find_historical_analogues(current, hist, n_analogues=3, method="cosine")
    print("Cosine analogues:")
    for a in analogues_c:
        print(f"  Rank {a['rank']}: {a['date']} distance={a['distance']:.4f} sim={a['similarity_pct']}%")

    fwd_returns = {f"2020-0{i+1}-01": random.uniform(-0.1, 0.15) for i in range(9)}
    consensus = compute_analogue_consensus(analogues_e, fwd_returns)
    print(f"Consensus: {consensus['description']}")
    print("All euclidean_analogues tests passed.")
