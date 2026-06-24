"""
Calibration analysis for ML models.
Computes Expected Calibration Error (ECE), Maximum Calibration Error (MCE),
and bucketing for probability outputs.
"""

from __future__ import annotations

from typing import Any
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

# ── Calibration Buckets ───────────────────────────────────────────────────────

CALIBRATION_BUCKETS = [
    (0.0, 0.3, "low"),
    (0.3, 0.5, "medium-low"),
    (0.5, 0.7, "medium-high"),
    (0.7, 1.0, "high"),
]

def compute_calibration_report(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, Any]:
    """Compute calibration metrics across predefined probability buckets.

    Parameters
    ----------
    y_true : np.ndarray
        Binary ground truth labels (0 or 1).
    y_prob : np.ndarray
        Predicted probabilities in [0, 1].

    Returns
    -------
    dict with "buckets" list, "ece" (Expected Calibration Error),
    and "mce" (Maximum Calibration Error).
    """
    if y_true is None or y_prob is None:
        return {"buckets": [], "ece": 0.0, "mce": 0.0}

    y_true = np.asarray(y_true, dtype=float).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()

    if len(y_true) == 0 or len(y_prob) == 0:
        return {"buckets": [], "ece": 0.0, "mce": 0.0}

    n_total = len(y_true)
    buckets: list[dict[str, Any]] = []
    ece = 0.0
    mce = 0.0

    for low, high, label in CALIBRATION_BUCKETS:
        if label == "high":
            mask = (y_prob >= low) & (y_prob <= high)
        else:
            mask = (y_prob >= low) & (y_prob < high)

        count = int(mask.sum())
        if count == 0:
            buckets.append({
                "label": label,
                "range": f"[{low:.1f}, {high:.1f})" if label != "high" else f"[{low:.1f}, {high:.1f}]",
                "count": 0,
                "accuracy": 0.0,
                "avg_probability": 0.0,
                "overconfidence": 0.0,
            })
            continue

        accuracy = float(y_true[mask].mean())
        avg_prob = float(y_prob[mask].mean())
        overconf = avg_prob - accuracy
        gap = abs(overconf)

        ece += (count / n_total) * gap
        mce = max(mce, gap)

        buckets.append({
            "label": label,
            "range": f"[{low:.1f}, {high:.1f})" if label != "high" else f"[{low:.1f}, {high:.1f}]",
            "count": count,
            "accuracy": round(accuracy, 4),
            "avg_probability": round(avg_prob, 4),
            "overconfidence": round(overconf, 4),
        })

    return {
        "buckets": buckets,
        "ece": round(ece, 4),
        "mce": round(mce, 4),
    }

class IsotonicCalibration:
    """Wrapper for Isotonic Regression calibration."""
    def __init__(self):
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        
    def fit(self, y_prob: np.ndarray, y_true: np.ndarray) -> None:
        self.calibrator.fit(y_prob, y_true)
        
    def predict_proba(self, y_prob: np.ndarray) -> np.ndarray:
        return self.calibrator.predict(y_prob)

class PlattScalingCalibration:
    """Wrapper for Platt Scaling (Logistic Regression) calibration."""
    def __init__(self):
        self.calibrator = LogisticRegression()
        
    def fit(self, y_prob: np.ndarray, y_true: np.ndarray) -> None:
        self.calibrator.fit(y_prob.reshape(-1, 1), y_true)
        
    def predict_proba(self, y_prob: np.ndarray) -> np.ndarray:
        return self.calibrator.predict_proba(y_prob.reshape(-1, 1))[:, 1]

