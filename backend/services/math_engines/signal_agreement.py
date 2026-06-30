import logging
"""
Task 27 — Signal Agreement Multiplier.

Combines technical, fundamental, sentiment, and macro signals using
vector cosine agreement to produce a confidence-weighted composite.
"""

from __future__ import annotations
import math
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class SignalBreakdown(BaseModel):
    raw_signal: float
    weight: float
    weighted_contribution: float
    label: str

class SignalAgreementResponse(BaseModel):
    composite_signal: float
    weighted_signal: float
    confidence_multiplier: float
    agreement_score: float
    pairwise_agreement: float
    direction: str
    signal_breakdown: Dict[str, SignalBreakdown]
    conflicts: List[str]
    high_confidence: bool
    description: str


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(y ** 2 for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (mag_a * mag_b)))


def _pairwise_agreement_matrix(signals: list[float]) -> list[list[float]]:
    """Compute pairwise agreement (sign agreement) between all signal pairs."""
    n = len(signals)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            else:
                # Agreement: +1 if same sign, -1 if opposite, 0 if either neutral
                if signals[i] * signals[j] > 0:
                    matrix[i][j] = 1.0
                elif signals[i] * signals[j] < 0:
                    matrix[i][j] = -1.0
                else:
                    matrix[i][j] = 0.0
    return matrix


def compute_signal_agreement(
    technical_signal: float,
    fundamental_signal: float,
    sentiment_signal: float,
    macro_signal: float,
    weights: dict[str, float] | None = None,
) -> SignalAgreementResponse:
    """
    Vector agreement multiplier across four signal dimensions.

    Higher inter-signal agreement → higher confidence multiplier.
    Conflicting signals → lower confidence, dampened composite.

    Args:
        technical_signal:   -1.0 (bearish) to +1.0 (bullish).
        fundamental_signal: -1.0 to +1.0.
        sentiment_signal:   -1.0 to +1.0.
        macro_signal:       -1.0 to +1.0.
        weights: optional dict with keys 'technical', 'fundamental',
                 'sentiment', 'macro'. Default: equal weights.

    Returns:
        dict with 'composite_signal', 'confidence_multiplier',
        'weighted_signal', 'agreement_score', 'direction', 'signal_breakdown'
    """
    if weights is None:
        weights = {
            "technical": 0.30,
            "fundamental": 0.35,
            "sentiment": 0.15,
            "macro": 0.20,
        }

    # Normalize weights to sum to 1
    total_w = sum(weights.values())
    w = {k: v / total_w for k, v in weights.items()}

    signal_values = [
        technical_signal,
        fundamental_signal,
        sentiment_signal,
        macro_signal,
    ]
    signal_names = ["technical", "fundamental", "sentiment", "macro"]
    signal_weights = [w.get(n, 0.25) for n in signal_names]

    # Clamp to [-1, 1]
    signal_values = [max(-1.0, min(1.0, s)) for s in signal_values]

    # Weighted average composite
    composite = sum(s * wt for s, wt in zip(signal_values, signal_weights))

    # Cosine similarity between signal vector and ideal agreement vector
    # Ideal vector: all signals pointing in composite direction
    direction_vector = [composite] * len(signal_values)
    cosine_agree = _cosine_similarity(signal_values, direction_vector)

    # Pairwise agreement: fraction of signal pairs that agree in direction
    pairwise = _pairwise_agreement_matrix(signal_values)
    n = len(signal_values)
    off_diag = [(pairwise[i][j]) for i in range(n) for j in range(n) if i != j]
    pairwise_agreement = sum(off_diag) / len(off_diag) if off_diag else 0.0

    # Agreement score: blend of cosine and pairwise
    agreement_score = 0.5 * (cosine_agree + 1) + 0.5 * ((pairwise_agreement + 1) / 2)
    agreement_score = max(0.0, min(1.0, agreement_score))

    # Confidence multiplier: 1.0 at full agreement, 0.5 at full disagreement
    confidence_multiplier = 0.5 + 0.5 * agreement_score

    # Weighted signal (dampened by confidence)
    weighted_signal = composite * confidence_multiplier

    # Direction classification
    if weighted_signal > 0.3:
        direction = "BULLISH"
    elif weighted_signal > 0.1:
        direction = "MILD_BULLISH"
    elif weighted_signal < -0.3:
        direction = "BEARISH"
    elif weighted_signal < -0.1:
        direction = "MILD_BEARISH"
    else:
        direction = "NEUTRAL"

    # Per-signal breakdown
    signal_breakdown = {
        name: SignalBreakdown(
            raw_signal=round(val, 4),
            weight=round(wt, 3),
            weighted_contribution=round(val * wt, 4),
            label="BULLISH" if val > 0.1 else ("BEARISH" if val < -0.1 else "NEUTRAL"),
        )
        for name, val, wt in zip(signal_names, signal_values, signal_weights)
    }

    # Identify conflicting signals
    conflicts = []
    for i, (n1, s1) in enumerate(zip(signal_names, signal_values)):
        for j, (n2, s2) in enumerate(zip(signal_names, signal_values)):
            if j > i and s1 * s2 < 0 and abs(s1) > 0.2 and abs(s2) > 0.2:
                conflicts.append(f"{n1} vs {n2}")

    return SignalAgreementResponse(
        composite_signal=round(composite, 4),
        weighted_signal=round(weighted_signal, 4),
        confidence_multiplier=round(confidence_multiplier, 4),
        agreement_score=round(agreement_score, 4),
        pairwise_agreement=round(pairwise_agreement, 4),
        direction=direction,
        signal_breakdown=signal_breakdown,
        conflicts=conflicts,
        high_confidence=agreement_score > 0.75,
        description=(
            f"Signals {direction} with {agreement_score:.0%} agreement "
            f"and {confidence_multiplier:.2f}x confidence multiplier."
            + (f" Conflicts: {', '.join(conflicts)}." if conflicts else "")
        ),
    )


if __name__ == "__main__":
    # High agreement bullish case
    result = compute_signal_agreement(
        technical_signal=0.7,
        fundamental_signal=0.6,
        sentiment_signal=0.5,
        macro_signal=0.4,
    )
    logging.info(f"All bullish: composite={result.composite_signal:.3f}, "
          f"agreement={result.agreement_score:.2%}, "
          f"direction={result.direction}")
    assert result.direction in {"BULLISH", "MILD_BULLISH"}
    assert result.confidence_multiplier > 0.7

    # Conflicting signals
    result2 = compute_signal_agreement(
        technical_signal=0.8,
        fundamental_signal=-0.6,
        sentiment_signal=0.3,
        macro_signal=-0.5,
    )
    logging.info(f"Mixed signals: composite={result2.composite_signal:.3f}, "
          f"agreement={result2.agreement_score:.2%}, "
          f"conflicts={result2.conflicts}")
    assert result2.confidence_multiplier < 0.8
    assert len(result2.conflicts) > 0

    # All bearish
    result3 = compute_signal_agreement(-0.7, -0.8, -0.6, -0.5)
    logging.info(f"All bearish: direction={result3.direction}, high_conf={result3.high_confidence}")
    assert result3.direction in {"BEARISH", "MILD_BEARISH"}

    logging.info("All signal_agreement tests passed.")
