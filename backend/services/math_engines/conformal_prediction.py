"""
Task 20 — Conformal Prediction price bounds.

Provides distribution-free coverage guarantees on price predictions.
"""

from __future__ import annotations
import math


def _simple_price_prediction(prices: list[float], horizon: int = 1) -> float:
    """Simple AR(1) prediction: next price = last price + mean daily change."""
    if len(prices) < 2:
        return prices[-1] if prices else 0.0
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    mean_change = sum(changes) / len(changes)
    return prices[-1] + mean_change * horizon


def compute_conformal_bounds(
    historical_prices: list[float],
    alpha: float = 0.1,
    calibration_fraction: float = 0.2,
    horizon_days: int = 1,
) -> dict:
    """
    Conformal Prediction price bounds with (1-alpha) coverage guarantee.

    Method:
      1. Split into training and calibration sets.
      2. Fit a simple AR(1) model on training set.
      3. Compute non-conformity scores on calibration set (|actual - predicted|).
      4. Find (1-alpha) quantile of non-conformity scores.
      5. Prediction interval = [predicted ± quantile].

    Args:
        historical_prices: chronological list of closing prices.
        alpha: miscoverage rate (0.1 = 90% coverage guarantee).
        calibration_fraction: fraction of data used for calibration (default 0.2).
        horizon_days: days ahead for prediction (default 1).

    Returns:
        dict with 'lower', 'upper', 'predicted', 'coverage_guarantee',
        'quantile_score', 'calibration_size', 'description'
    """
    if len(historical_prices) < 10:
        return {
            "lower": None,
            "upper": None,
            "predicted": None,
            "coverage_guarantee": 1 - alpha,
            "quantile_score": None,
            "calibration_size": 0,
            "description": "Insufficient data (need 10+ prices)",
            "error": True,
        }

    n = len(historical_prices)
    cal_size = max(5, int(n * calibration_fraction))
    train_end = n - cal_size

    if train_end < 5:
        train_end = 5
        cal_size = n - train_end

    train_prices = historical_prices[:train_end]
    cal_prices = historical_prices[train_end:]

    # Compute non-conformity scores on calibration set
    # Score: |actual_t - predicted_t| where prediction uses all data up to t-1
    non_conformity_scores: list[float] = []

    for i in range(1, len(cal_prices)):
        # Use train + cal[:i] to predict cal[i]
        context = train_prices + cal_prices[:i]
        predicted = _simple_price_prediction(context, horizon=1)
        actual = cal_prices[i]
        score = abs(actual - predicted)
        non_conformity_scores.append(score)

    if not non_conformity_scores:
        return {
            "lower": None,
            "upper": None,
            "predicted": None,
            "coverage_guarantee": 1 - alpha,
            "quantile_score": None,
            "calibration_size": 0,
            "description": "Could not compute calibration scores",
            "error": True,
        }

    # Find the (1-alpha) * (1 + 1/n) quantile (finite-sample correction)
    n_cal = len(non_conformity_scores)
    q_level = min(1.0, (1 - alpha) * (1 + 1.0 / n_cal))
    sorted_scores = sorted(non_conformity_scores)

    # Empirical quantile
    idx = min(int(math.ceil(q_level * n_cal)) - 1, n_cal - 1)
    idx = max(0, idx)
    quantile_score = sorted_scores[idx]

    # Prediction for next day
    predicted = _simple_price_prediction(historical_prices, horizon=horizon_days)
    lower = predicted - quantile_score
    upper = predicted + quantile_score

    # Compute realized coverage on calibration set (sanity check)
    coverage_count = sum(
        1 for s in non_conformity_scores if s <= quantile_score
    )
    realized_coverage = coverage_count / n_cal if n_cal else 0

    return {
        "lower": round(lower, 2),
        "upper": round(upper, 2),
        "predicted": round(predicted, 2),
        "current_price": round(historical_prices[-1], 2),
        "coverage_guarantee": 1 - alpha,
        "realized_calibration_coverage": round(realized_coverage, 4),
        "quantile_score": round(quantile_score, 4),
        "calibration_size": n_cal,
        "horizon_days": horizon_days,
        "description": (
            f"{int((1-alpha)*100)}% conformal prediction interval: "
            f"[{lower:.2f}, {upper:.2f}] for {horizon_days}-day horizon"
        ),
        "error": False,
    }


if __name__ == "__main__":
    import random
    random.seed(99)

    prices = [100.0]
    for _ in range(99):
        prices.append(prices[-1] * (1 + random.uniform(-0.015, 0.018)))

    result = compute_conformal_bounds(prices, alpha=0.1)
    print(f"Conformal bounds (90%): [{result['lower']}, {result['upper']}]")
    print(f"Predicted: {result['predicted']}, Score: {result['quantile_score']}")
    assert result["lower"] < result["predicted"] < result["upper"]
    assert result["coverage_guarantee"] == 0.9
    print(f"Realized calibration coverage: {result['realized_calibration_coverage']:.1%}")
    print("All conformal_prediction tests passed.")
