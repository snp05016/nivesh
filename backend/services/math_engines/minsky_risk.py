"""
Task 26 — Minskyan Risk from FII/DII Flow Derivatives.

Minsky's financial instability hypothesis: markets cycle through
hedge → speculative → Ponzi phases based on flow acceleration.
Second derivative of combined flows signals the phase.
"""

from __future__ import annotations
import math


def compute_minsky_risk(
    fii_flows: list[float],
    dii_flows: list[float],
) -> dict:
    """
    Compute Minskyan Risk from FII and DII net flows.

    Minskyan Risk = second derivative of (FII + DII net flows).
    Positive second derivative = acceleration toward risk (Ponzi phase).
    Negative second derivative = deceleration (hedge/speculative phase).

    Args:
        fii_flows: chronological list of FII net flows (INR Crores, + = buying).
        dii_flows: chronological list of DII net flows (INR Crores, + = buying).

    Returns:
        dict with 'phase', 'risk_score', 'first_derivative',
        'second_derivative', 'description', 'combined_flows'
    """
    if len(fii_flows) != len(dii_flows):
        raise ValueError("fii_flows and dii_flows must have the same length")

    n = len(fii_flows)
    if n < 3:
        return {
            "phase": "UNKNOWN",
            "risk_score": 50,
            "first_derivative": None,
            "second_derivative": None,
            "combined_flows": [],
            "description": "Need at least 3 data points",
            "cumulative_flow": 0.0,
        }

    combined = [f + d for f, d in zip(fii_flows, dii_flows)]
    first_deriv = [combined[i] - combined[i - 1] for i in range(1, n)]
    second_deriv = [first_deriv[i] - first_deriv[i - 1] for i in range(1, len(first_deriv))]

    current_flow = combined[-1]
    current_first = first_deriv[-1]
    current_second = second_deriv[-1] if second_deriv else 0.0

    cumulative = sum(combined)
    mean_flow = sum(combined) / n
    std_flow = math.sqrt(sum((x - mean_flow) ** 2 for x in combined) / n) or 1

    # Classify Minsky phase
    # Hedge: positive flows, decelerating (stable)
    # Speculative: positive flows, accelerating
    # Ponzi: negative flows, flows worsening (second deriv still negative = accelerating loss)
    if current_flow > 0 and current_first > 0 and current_second > 0:
        phase = "PONZI"
        risk_score = 80
        description = "Flows accelerating upward — euphoric Ponzi phase, high reversal risk"
    elif current_flow > 0 and current_first > 0 and current_second <= 0:
        phase = "SPECULATIVE"
        risk_score = 55
        description = "Positive flows but momentum decelerating — speculative phase"
    elif current_flow > 0 and current_first <= 0:
        phase = "HEDGE"
        risk_score = 30
        description = "Positive net flows, deceleration — stable hedge phase"
    elif current_flow < 0 and current_first < 0 and current_second < 0:
        phase = "PONZI_UNWIND"
        risk_score = 90
        description = "Accelerating outflows — Minsky moment unwind, extreme caution"
    elif current_flow < 0 and current_first < 0:
        phase = "DISTRESS"
        risk_score = 70
        description = "Negative flows, worsening — market distress phase"
    else:
        phase = "TRANSITION"
        risk_score = 50
        description = "Mixed signals — transition between Minsky phases"

    # Normalize second derivative to a risk contribution
    mean_2nd = sum(second_deriv) / len(second_deriv) if second_deriv else 0
    std_2nd = math.sqrt(sum((x - mean_2nd) ** 2 for x in second_deriv) / len(second_deriv)) if len(second_deriv) > 1 else 1

    # Z-score of current 2nd derivative (how extreme is the acceleration?)
    z_accel = (current_second - mean_2nd) / std_2nd if std_2nd else 0
    accel_risk = min(20, max(-20, z_accel * 5))
    adjusted_risk_score = min(100, max(0, risk_score + accel_risk))

    return {
        "phase": phase,
        "risk_score": round(adjusted_risk_score, 1),
        "risk_level": "HIGH" if adjusted_risk_score >= 70 else ("MEDIUM" if adjusted_risk_score >= 40 else "LOW"),
        "current_combined_flow": round(current_flow, 2),
        "first_derivative": round(current_first, 2),
        "second_derivative": round(current_second, 2),
        "acceleration_zscore": round(z_accel, 3),
        "cumulative_flow": round(cumulative, 2),
        "mean_flow": round(mean_flow, 2),
        "combined_flows": [round(x, 2) for x in combined],
        "first_deriv_series": [round(x, 2) for x in first_deriv],
        "second_deriv_series": [round(x, 2) for x in second_deriv],
        "description": description,
        "n_periods": n,
    }


if __name__ == "__main__":
    import random
    random.seed(55)

    # Simulate 30 days of FII/DII flows in INR Crores
    # Euphoric phase: both buying and accelerating
    fii_euphor = [1000 + i * 200 + random.uniform(-100, 100) for i in range(30)]
    dii_euphor = [500 + i * 100 + random.uniform(-50, 50) for i in range(30)]

    result_e = compute_minsky_risk(fii_euphor, dii_euphor)
    print(f"Euphoric phase: {result_e['phase']}, Risk={result_e['risk_score']}")
    print(f"  1st deriv={result_e['first_derivative']:.1f}, 2nd deriv={result_e['second_derivative']:.1f}")
    assert result_e["phase"] in {"PONZI", "SPECULATIVE", "HEDGE", "TRANSITION"}

    # Distress phase: outflows accelerating
    fii_distress = [-500 - i * 150 + random.uniform(-100, 100) for i in range(30)]
    dii_distress = [-200 - i * 50 + random.uniform(-50, 50) for i in range(30)]

    result_d = compute_minsky_risk(fii_distress, dii_distress)
    print(f"Distress phase: {result_d['phase']}, Risk={result_d['risk_score']}")
    assert result_d["risk_score"] > 50
    assert result_d["phase"] in {"PONZI_UNWIND", "DISTRESS", "TRANSITION"}

    print("All minsky_risk tests passed.")
