"""
Nivesh Confidence Engine
------------------------
Deterministic confidence calibration pipeline. Pure math — no AI calls.
Computes signal agreement, conformal prediction bounds, KNN historical
analogues, bear asymmetry adjustment, and aggregate final confidence.

Every function returns safe defaults on error — never crashes the caller.
No monetary values in this file; all outputs are ratios, floats, or percents.
"""

import json
import logging
import re
from typing import Any, Optional

import numpy as np
import pandas as pd

from database import AnalysisHistory, get_session

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Signal extraction: match canonical signal strings in agent reports.
# Order matters: longer patterns first to avoid partial matches.
_SIGNAL_PATTERN = re.compile(
    r'\b(CAUTIOUSLY\s+BULLISH|CAUTIOUSLY\s+BEARISH|BULLISH|BEARISH|NEUTRAL|HOLD)\b',
    re.IGNORECASE,
)

# Normalise granular signals down to 3-category for agreement counting.
_SIGNAL_NORMALIZE: dict[str, str] = {
    "BULLISH": "BULLISH",
    "CAUTIOUSLY BULLISH": "BULLISH",
    "NEUTRAL": "NEUTRAL",
    "HOLD": "NEUTRAL",
    "CAUTIOUSLY BEARISH": "BEARISH",
    "BEARISH": "BEARISH",
}

_AGENT_KEYS = ("governance", "market", "fundamentals", "news")

# Agreement formula coefficients
_AGREEMENT_BASE = 0.60
_AGREEMENT_SLOPE = 0.40

# Conformal prediction trading-day horizons
_CONFORMAL_HORIZONS: dict[str, int] = {
    "short_term_3m": 63,
    "medium_term_12m": 252,
    "long_term_36m": 756,
}
_CONFORMAL_COVERAGE_PCT = 90
_CONFORMAL_MIN_ROWS = 10

# KNN analogue search
_KNN_DEFAULT_K = 10
_KNN_MAX_RECORDS = 500

# Governance hard cap
_GOVERNANCE_CAP_THRESHOLD = 40
_GOVERNANCE_CAP_VALUE = 40

# Bear asymmetry: thresholds for net_direction → signal_override mapping
_BEAR_ASYMMETRY_THRESHOLDS: list[tuple[float, str]] = [
    (0.15, "BULLISH"),
    (0.05, "CAUTIOUSLY BULLISH"),
    (-0.05, "NEUTRAL"),
    (-0.15, "CAUTIOUSLY BEARISH"),
]

# Regex patterns for Bull/Bear confidence extraction in raw LLM output
_BULL_CONFIDENCE_PATTERN = re.compile(
    r'\b(bull|bullish)\s*(?:confidence|conviction|score|strength)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%?',
    re.IGNORECASE,
)
_BEAR_CONFIDENCE_PATTERN = re.compile(
    r'\b(bear|bearish)\s*(?:confidence|conviction|score|strength)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%?',
    re.IGNORECASE,
)

# Default safe values for NaN/invalid feature slots
_FEATURE_DEFAULTS: dict[str, float] = {
    "rsi_14": 50.0,
    "price_vs_sma50_pct": 0.0,
    "hist_vol_21_annualized": 25.0,
    "momentum_score": 0.0,
    "promoter_pledged_pct": 0.0,
    "delivery_pct": 0.0,
    "oi_pcr": 0.0,
    "pe_ratio": 0.0,
}

# ── Helper ─────────────────────────────────────────────────────────────────────


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns 0 if either is zero-norm."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _map_net_direction_to_signal(net_direction: float) -> str:
    """Map continuous net_direction to a discrete signal string."""
    for threshold, signal in _BEAR_ASYMMETRY_THRESHOLDS:
        if net_direction > threshold:
            return signal
    return "BEARISH"


# ── GAP 1: Signal Agreement Multiplier ────────────────────────────────────────


def compute_signal_agreement(agent_reports: dict) -> dict:
    """
    Extract directional signals from agent reports and compute agreement ratio.

    Each report is scanned for the first canonical signal keyword
    (BULLISH/CAUTIOUSLY BULLISH/NEUTRAL/HOLD/CAUTIOUSLY BEARISH/BEARISH).
    Signals are normalised to 3 categories, then the majority signal
    determines the consensus. Agreement is the fraction of voting agents
    aligned with the consensus.

    Args:
        agent_reports: dict with keys 'governance', 'market', 'fundamentals',
                      'news', each containing a text report string.

    Returns:
        dict with:
            agreement_ratio: float 0.0-1.0
            confidence_multiplier: float 0.60-1.0
            vote_counts: dict of {signal: count}
            total_voters: int
    """
    try:
        votes: dict[str, str] = {}
        for key in _AGENT_KEYS:
            report = agent_reports.get(key, "")
            if not isinstance(report, str) or not report.strip():
                continue
            match = _SIGNAL_PATTERN.search(report)
            if match:
                raw = match.group(1).strip().upper()
                canonical = _SIGNAL_NORMALIZE.get(raw, "NEUTRAL")
                votes[key] = canonical

        total_voters = len(votes)
        if total_voters == 0:
            return {
                "agreement_ratio": 0.0,
                "confidence_multiplier": _AGREEMENT_BASE,
                "vote_counts": {},
                "total_voters": 0,
            }

        vote_counts: dict[str, int] = {}
        for v in votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1

        consensus_signal = max(vote_counts, key=vote_counts.get)
        votes_aligned = vote_counts.get(consensus_signal, 0)

        agreement_ratio = votes_aligned / total_voters
        confidence_multiplier = _AGREEMENT_BASE + (_AGREEMENT_SLOPE * agreement_ratio)

        return {
            "agreement_ratio": round(agreement_ratio, 4),
            "confidence_multiplier": round(confidence_multiplier, 4),
            "vote_counts": vote_counts,
            "total_voters": total_voters,
        }

    except Exception as e:
        logger.error(f"[confidence_engine] compute_signal_agreement error: {e}", exc_info=True)
        return {
            "agreement_ratio": 0.0,
            "confidence_multiplier": _AGREEMENT_BASE,
            "vote_counts": {},
            "total_voters": 0,
        }


# ── GAP 5: Conformal Prediction Uncertainty Bounds ────────────────────────────


def compute_conformal_bounds(
    ticker: str,
    current_price: float,
    hist_df: Optional[pd.DataFrame],
) -> dict:
    """
    Compute conformal prediction intervals using historical return percentiles.

    For each horizon (63/252/756 trading days), computes the distribution of
    past rolling returns and takes the 5th/95th percentiles as the 90% coverage
    conformal interval. The current price serves as the mid-point.

    Args:
        ticker: NSE/BSE ticker (for logging).
        current_price: Current market price in INR.
        hist_df: OHLCV DataFrame with a 'Close' column. Must have at least
                 63 rows for short-term bounds.

    Returns:
        dict mapping each horizon to {lower, mid, upper, coverage_pct: 90}.
        On insufficient data, bounds default to 0.0/current_price/0.0.
    """
    defaults: dict[str, dict[str, Any]] = {
        h: {"lower": 0.0, "mid": current_price, "upper": 0.0, "coverage_pct": _CONFORMAL_COVERAGE_PCT}
        for h in _CONFORMAL_HORIZONS
    }

    if hist_df is None or not isinstance(hist_df, pd.DataFrame):
        logger.warning(
            "[confidence_engine] %s: No DataFrame provided for conformal bounds.", ticker
        )
        return defaults

    try:
        close = hist_df["Close"].astype(float).dropna()
        row_count = len(close)

        result: dict[str, dict[str, Any]] = {}
        for horizon_label, window in _CONFORMAL_HORIZONS.items():
            if row_count < window:
                logger.warning(
                    "[confidence_engine] %s: Insufficient data for %s "
                    "(need %d rows, have %d).",
                    ticker, horizon_label, window, row_count,
                )
                result[horizon_label] = {
                    "lower": 0.0,
                    "mid": current_price,
                    "upper": 0.0,
                    "coverage_pct": _CONFORMAL_COVERAGE_PCT,
                }
                continue

            rolling_returns = close.pct_change(periods=window).dropna()
            if len(rolling_returns) < _CONFORMAL_MIN_ROWS:
                result[horizon_label] = {
                    "lower": 0.0,
                    "mid": current_price,
                    "upper": 0.0,
                    "coverage_pct": _CONFORMAL_COVERAGE_PCT,
                }
                continue

            p5 = float(rolling_returns.quantile(0.05))
            p95 = float(rolling_returns.quantile(0.95))

            result[horizon_label] = {
                "lower": round(current_price * (1.0 + p5), 2),
                "mid": round(current_price, 2),
                "upper": round(current_price * (1.0 + p95), 2),
                "coverage_pct": _CONFORMAL_COVERAGE_PCT,
            }

        # Guarantee all horizon keys exist
        for h in _CONFORMAL_HORIZONS:
            if h not in result:
                result[h] = {
                    "lower": 0.0,
                    "mid": current_price,
                    "upper": 0.0,
                    "coverage_pct": _CONFORMAL_COVERAGE_PCT,
                }

        return result

    except Exception as e:
        logger.error(
            "[confidence_engine] %s: compute_conformal_bounds error: %s", ticker, e, exc_info=True
        )
        return defaults


# ── GAP 7: KNN Historical Analogue Search ─────────────────────────────────────


def _extract_feature_row(full_json_str: str) -> Optional[np.ndarray]:
    """Build an 8-dimensional feature vector from a historical analysis JSON row.

    Returns None if the JSON cannot be parsed or required keys are missing.
    """
    try:
        data = json.loads(full_json_str) if isinstance(full_json_str, str) else full_json_str
        if not isinstance(data, dict):
            return None
        fund = data.get("fundamentals_snapshot") or {}
        features = [
            float(data.get("rsi_14") or data.get("rsi", _FEATURE_DEFAULTS["rsi_14"])),
            float(data.get("price_vs_sma50_pct") or _FEATURE_DEFAULTS["price_vs_sma50_pct"]),
            float(data.get("hist_vol_21_annualized") or _FEATURE_DEFAULTS["hist_vol_21_annualized"]),
            float(data.get("momentum_score") or _FEATURE_DEFAULTS["momentum_score"]),
            float(fund.get("promoter_pledged_pct") or _FEATURE_DEFAULTS["promoter_pledged_pct"]),
            float(data.get("delivery_pct") or _FEATURE_DEFAULTS["delivery_pct"]),
            float(data.get("oi_pcr") or _FEATURE_DEFAULTS["oi_pcr"]),
            float(fund.get("pe_ratio") or _FEATURE_DEFAULTS["pe_ratio"]),
        ]
        return np.array(features, dtype=np.float64)
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        logger.debug("[confidence_engine] _extract_feature_row parse failed: %s", e)
        return None


def _build_feature_vector(fv: dict) -> np.ndarray:
    """Build a normalised 8-dimensional feature vector from a current-state dict."""
    return np.array(
        [
            float(fv.get(k, _FEATURE_DEFAULTS[k]))
            for k in (
                "rsi_14",
                "price_vs_sma50_pct",
                "hist_vol_21_annualized",
                "momentum_score",
                "promoter_pledged_pct",
                "delivery_pct",
                "oi_pcr",
                "pe_ratio",
            )
        ],
        dtype=np.float64,
    )


def find_historical_analogues(
    ticker: str,
    feature_vector: dict,
    k: int = _KNN_DEFAULT_K,
) -> dict:
    """
    Search AnalysisHistory for the K most similar historical setups.

    Uses cosine similarity between the current feature vector and each past
    analysis entry. Returns win-rate statistics computed from outcome data
    stored in the AnalysisHistory table.

    Args:
        ticker: NSE/BSE ticker.
        feature_vector: dict with keys matching _FEATURE_DEFAULTS.
        k: Number of top analogues to return (default 10).

    Returns:
        dict with:
            k_found: int — number of analogues actually found.
            historical_win_rate_pct: float or None — % of analogues with
                correct directional prediction.
            avg_return_on_wins_pct: float or None — average return % of
                winning analogues.
            analogue_summary: str — human-readable summary.
    """
    try:
        current_vec = _build_feature_vector(feature_vector)

        with get_session() as session:
            rows = (
                session.query(AnalysisHistory)
                .filter(AnalysisHistory.ticker == ticker.upper())
                .order_by(AnalysisHistory.created_at.desc())
                .limit(_KNN_MAX_RECORDS)
                .all()
            )

        if not rows:
            return {
                "k_found": 0,
                "historical_win_rate_pct": None,
                "avg_return_on_wins_pct": None,
                "analogue_summary": "No historical analyses found for this ticker.",
            }

        scored: list[tuple[float, Any]] = []
        for row in rows:
            vec = _extract_feature_row(row.full_json)
            if vec is None:
                continue
            sim = _cosine_similarity(current_vec, vec)
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = scored[:k]

        if not top_k:
            return {
                "k_found": 0,
                "historical_win_rate_pct": None,
                "avg_return_on_wins_pct": None,
                "analogue_summary": "No comparable historical analogues found.",
            }

        k_found = len(top_k)
        wins = 0
        total_return = 0.0
        outcome_count = 0

        for _, row in top_k:
            delta = row.outcome_delta_pct
            correct = row.was_correct
            if delta is not None and correct is not None:
                outcome_count += 1
                if correct:
                    wins += 1
                    total_return += delta

        win_rate = round((wins / outcome_count) * 100, 1) if outcome_count > 0 else None
        avg_wins = round(total_return / wins, 2) if wins > 0 else None

        if win_rate is not None:
            summary = (
                f"{wins} of {outcome_count} similar setups produced positive returns "
                f"({win_rate}% win rate)"
            )
        else:
            summary = f"{k_found} analogues found but no outcome data yet."

        return {
            "k_found": k_found,
            "historical_win_rate_pct": win_rate,
            "avg_return_on_wins_pct": avg_wins,
            "analogue_summary": summary,
        }

    except Exception as e:
        logger.error(
            "[confidence_engine] %s: find_historical_analogues error: %s", ticker, e, exc_info=True
        )
        return {
            "k_found": 0,
            "historical_win_rate_pct": None,
            "avg_return_on_wins_pct": None,
            "analogue_summary": "Error computing historical analogues.",
        }


# ── GAP 12: Bear 1.5x Weight Asymmetry ────────────────────────────────────────


def apply_bear_asymmetry(raw_output: str) -> dict:
    """
    Apply 1.5x bear weight asymmetry to bull/bear confidence scores.

    Parses the raw LLM output for numeric Bull and Bear confidence values
    using regex, then computes a weighted net direction where bear confidence
    is weighted 1.5x relative to bull.

    Formula:
        net_direction = (bull_conf * 1.0 - bear_conf * 1.5) / 2.5

    Args:
        raw_output: Raw text output from the LLM pipeline containing
                    bull and/or bear confidence statements.

    Returns:
        dict with:
            adjustment: float — the asymmetry adjustment (-0.6 to +0.4).
            bull_confidence: float — extracted bull confidence (0-1).
            bear_confidence: float — extracted bear confidence (0-1).
            net_direction: float — weighted directional score.
            signal_override: str — discrete signal derived from net_direction.
    """
    try:
        if not isinstance(raw_output, str) or not raw_output.strip():
            return {
                "adjustment": 0.0,
                "bull_confidence": 0.0,
                "bear_confidence": 0.0,
                "net_direction": 0.0,
                "signal_override": "NEUTRAL",
            }

        bull_matches = _BULL_CONFIDENCE_PATTERN.findall(raw_output)
        bear_matches = _BEAR_CONFIDENCE_PATTERN.findall(raw_output)

        bull_conf = 0.0
        bear_conf = 0.0

        if bull_matches:
            bull_conf = float(bull_matches[-1][1]) / 100.0

        if bear_matches:
            bear_conf = float(bear_matches[-1][1]) / 100.0

        net_direction = (bull_conf * 1.0 - bear_conf * 1.5) / 2.5
        signal_override = _map_net_direction_to_signal(net_direction)

        return {
            "adjustment": round(net_direction, 4),
            "bull_confidence": round(bull_conf, 4),
            "bear_confidence": round(bear_conf, 4),
            "net_direction": round(net_direction, 4),
            "signal_override": signal_override,
        }

    except Exception as e:
        logger.error("[confidence_engine] apply_bear_asymmetry error: %s", e, exc_info=True)
        return {
            "adjustment": 0.0,
            "bull_confidence": 0.0,
            "bear_confidence": 0.0,
            "net_direction": 0.0,
            "signal_override": "NEUTRAL",
        }


# ── GAP 14: Aggregate Confidence Engine ───────────────────────────────────────


def compute_final_confidence(
    raw_llm_confidence: int,
    governance_score: int,
    signal_agreement_ratio: float,
    regime_multiplier: float,
    delivery_modifier: float,
    microstructure_modifier: float,
    rrg_modifier: float,
    minskyan_penalty: float,
    monsoon_modifier: float,
    cisi_modifier: float,
    auditor_boost: float,
    bear_asymmetry_adjustment: float,
    signal: str,
) -> dict:
    """
    Deterministic confidence calibration engine.

    Collects ALL modifier signals and produces the final mathematically
    calibrated confidence score through a 5-step pipeline:
        1. Signal agreement multiplier
        2. Regime multiplier
        3. Additive modifiers sum
        4. Governance hard cap (score < 40 → cap at 40)
        5. Clamp to 0-100

    Args:
        raw_llm_confidence: Raw confidence 0-100 from the LLM.
        governance_score: Governance assessment 0-100.
        signal_agreement_ratio: Signal agreement ratio 0.0-1.0.
        regime_multiplier: Market regime multiplier 0.65-1.0.
        delivery_modifier: Delivery microstructure -0.10 to +0.05.
        microstructure_modifier: Options PCR/GEX -0.10 to +0.08.
        rrg_modifier: Sector rotation RRG -0.08 to +0.05.
        minskyan_penalty: Minskyan fragility -0.075 to 0.0.
        monsoon_modifier: Monsoon impact -0.10 to +0.08.
        cisi_modifier: Composite sentiment -0.10 to +0.05.
        auditor_boost: Auditor quality -0.05 to +0.05.
        bear_asymmetry_adjustment: Output of apply_bear_asymmetry().
        signal: Final signal string (for context, not used in math).

    Returns:
        dict with:
            final_confidence_pct: int 0-100.
            raw_llm_confidence: int — original input preserved.
            agreement_multiplier: float.
            regime_multiplier: float.
            additive_modifiers_total: float — sum of all additive modifiers.
            governance_cap_applied: bool — whether governance cap was triggered.
            calibration_note: str — human-readable trace of the calibration.
    """
    try:
        raw = float(raw_llm_confidence)

        agreement_multiplier = _AGREEMENT_BASE + (_AGREEMENT_SLOPE * signal_agreement_ratio)
        agreement_adjusted = raw * agreement_multiplier

        regime_adjusted = agreement_adjusted * regime_multiplier

        additive_sum = (
            delivery_modifier
            + microstructure_modifier
            + rrg_modifier
            + minskyan_penalty
            + monsoon_modifier
            + cisi_modifier
            + auditor_boost
            + bear_asymmetry_adjustment
        )
        total_pct_points = regime_adjusted + (raw * additive_sum)

        governance_cap_applied = governance_score < _GOVERNANCE_CAP_THRESHOLD
        if governance_cap_applied:
            final = min(total_pct_points, float(_GOVERNANCE_CAP_VALUE))
        else:
            final = total_pct_points

        final_confidence_pct = max(0, min(100, round(final)))

        calibration_note = (
            f"Raw {raw_llm_confidence}% → Agreement {round(agreement_adjusted)}% "
            f"→ Regime {round(regime_adjusted)}% → Modifiers "
            f"{round(additive_sum * 100, 1)}pp → Final {final_confidence_pct}%"
        )

        return {
            "final_confidence_pct": final_confidence_pct,
            "raw_llm_confidence": raw_llm_confidence,
            "agreement_multiplier": round(agreement_multiplier, 3),
            "regime_multiplier": regime_multiplier,
            "additive_modifiers_total": round(additive_sum, 3),
            "governance_cap_applied": governance_cap_applied,
            "calibration_note": calibration_note,
        }

    except Exception as e:
        logger.error("[confidence_engine] compute_final_confidence error: %s", e, exc_info=True)
        safe_raw = raw_llm_confidence if 0 <= raw_llm_confidence <= 100 else 50
        return {
            "final_confidence_pct": safe_raw,
            "raw_llm_confidence": raw_llm_confidence,
            "agreement_multiplier": _AGREEMENT_BASE,
            "regime_multiplier": 1.0,
            "additive_modifiers_total": 0.0,
            "governance_cap_applied": False,
            "calibration_note": "Confidence calibration failed — using raw LLM confidence as fallback.",
        }
