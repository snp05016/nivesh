"""
Nivesh Macro Modifiers
----------------------
GAP 11 — Minskyan Risk as Computed Penalty: Scalar fragility score from
    FII-DII absorption ratio and Nifty P/E z-score, mapped to a confidence penalty.

Pure function only. The monsoon modifier and FII/DII fetch were removed: they
called placeholder endpoints and had no callers. Callers must pass real
FII/DII flows; never call this with literal zeros.
"""
import logging

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Nifty 50 historical parameters (20-year mean/std)
NIFTY_HISTORICAL_MEAN_PE = 20.5
NIFTY_HISTORICAL_STD_PE = 4.2

# Score thresholds
MINSKYAN_THRESHOLD = 0.7
MINSKYAN_PENALTY_SLOPE = 25.0
MINSKYAN_SCORE_MAX = 1.0
MINSKYAN_SCORE_MIN = 0.0
PENALTY_LOWER_BOUND = -0.075
PENALTY_UPPER_BOUND = 0.0

# ── GAP 11: Minskyan Risk as Computed Penalty ───────────────────────────────

def compute_minskyan_risk(
    dii_ytd: float = 0,
    fii_ytd: float = 0,
    nifty_pe: float = 21.5,
) -> dict:
    """Compute Minskyan fragility score and momentum confidence penalty.

    Formula:
        dii_fii_absorption_ratio = abs(dii_ytd) / max(1, abs(fii_ytd))
        cape_zscore = (nifty_pe - 20.5) / 4.2
        minskyan_score = 0.6 * min(dii_absorption / 2.0, 1.0)
                        + 0.4 * min(cape_zscore / 2.0, 1.0)
        if minskyan_score > 0.7:
            penalty = -(minskyan_score - 0.7) * 25

    Args:
        dii_ytd: DII net purchases YTD in crores.
        fii_ytd: FII net outflows YTD in crores (negative = selling).
        nifty_pe: Current Nifty 50 P/E ratio.

    Returns:
        dict with keys: minskyan_score (float 0-1),
        momentum_confidence_penalty (float -0.075 to 0),
        minskyan_flag (bool), reasoning (str).
    """
    try:
        abs_fii = abs(fii_ytd)
        denominator = max(1.0, abs_fii)
        absorption_ratio = abs(dii_ytd) / denominator

        cape_zscore = (nifty_pe - NIFTY_HISTORICAL_MEAN_PE) / NIFTY_HISTORICAL_STD_PE

        capped_absorption = min(absorption_ratio / 2.0, 1.0)
        capped_cape = min(cape_zscore / 2.0, 1.0)

        raw_score = 0.6 * capped_absorption + 0.4 * capped_cape
        minskyan_score = max(MINSKYAN_SCORE_MIN, min(MINSKYAN_SCORE_MAX, raw_score))

        if minskyan_score > MINSKYAN_THRESHOLD:
            penalty = -(minskyan_score - MINSKYAN_THRESHOLD) * MINSKYAN_PENALTY_SLOPE
            # Clamp to [-0.075, 0] as a percentage point modifier
            momentum_confidence_penalty = max(PENALTY_LOWER_BOUND, min(PENALTY_UPPER_BOUND, penalty))
        else:
            momentum_confidence_penalty = 0.0

        if momentum_confidence_penalty < 0:
            minskyan_flag = True
            reasoning = (
                f"Minskyan score {minskyan_score:.2f} exceeds {MINSKYAN_THRESHOLD:.0%} threshold — "
                f"applying {momentum_confidence_penalty:.1%} momentum confidence penalty. "
                f"DII absorption ratio {absorption_ratio:.2f}, Nifty P/E z-score {cape_zscore:.2f}"
            )
        else:
            minskyan_flag = False
            reasoning = (
                f"Minskyan score {minskyan_score:.2f} below threshold — no penalty. "
                f"DII absorption ratio {absorption_ratio:.2f}, Nifty P/E z-score {cape_zscore:.2f}"
            )

        return {
            "minskyan_score": round(minskyan_score, 4),
            "momentum_confidence_penalty": round(momentum_confidence_penalty, 6),
            "minskyan_flag": minskyan_flag,
            "reasoning": reasoning,
        }

    except Exception as e:
        logger.error(f"[minskyan] Computation failed: {e}")
        return {
            "minskyan_score": 0.0,
            "momentum_confidence_penalty": 0.0,
            "minskyan_flag": False,
            "reasoning": f"Minskyan risk unavailable: {e}",
        }
