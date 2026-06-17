"""Risk scoring layer for stress test outputs (§12)."""
from __future__ import annotations
import numpy as np
from typing import Any

def sigmoid(x: float, midpoint: float = 50.0, steepness: float = 0.1) -> float:
    """Sigmoid mapping to 0-100 scale."""
    return float(100.0 / (1.0 + np.exp(-steepness * (x - midpoint))))

def compute_risk_score(portfolio_vol_annualized: float) -> float:
    """Risk Score (0-100): normalized by unconditional volatility.
    
    Higher score = higher risk (worse).
    """
    return round(sigmoid(portfolio_vol_annualized * 100, midpoint=25.0, steepness=0.08), 1)

def compute_stress_score(cvar_pct: float, benchmark_cvar_pct: float = 15.0) -> float:
    """Stress Score (0-100): Expected Shortfall percentile vs Nifty 50.
    
    Higher score = more resilient (better).
    """
    ratio = cvar_pct / (benchmark_cvar_pct + 0.01)
    score = 100.0 / (1.0 + ratio)
    return round(score, 1)

def compute_macro_fragility_score(macro_betas: dict[str, float]) -> float:
    """Macro Fragility Score (0-100): weighted macro sensitivity.
    
    Higher score = more fragile (worse).
    """
    if not macro_betas:
        return 50.0
    abs_betas = [abs(v) for v in macro_betas.values()]
    avg_abs_beta = np.mean(abs_betas)
    return round(min(100.0, avg_abs_beta * 100), 1)

def compute_tail_risk_score(
    parametric_var_95: float,
    monte_carlo_cvar_99: float,
) -> float:
    """Tail Risk Score (0-100): divergence between Gaussian VaR and CVaR.
    
    Large divergence = fat tails = higher score (worse).
    """
    if parametric_var_95 == 0:
        return 0.0
    divergence = abs(abs(monte_carlo_cvar_99) - abs(parametric_var_95)) / (abs(parametric_var_95) + 0.001)
    return round(min(100.0, divergence * 50), 1)

def compute_all_scores(
    portfolio_vol_annualized: float,
    worst_case_loss_pct: float,
    macro_betas: dict[str, float],
    liquidity_impact_pct: float,
    concentration_hhi: float,
    parametric_var_95_pct: float,
    cvar_99_pct: float,
    liquidity_score_raw: float = 50.0,
) -> dict[str, float]:
    """Compute all 6 risk scores for a stress test scenario."""
    return {
        "risk_score": compute_risk_score(portfolio_vol_annualized),
        "stress_score": compute_stress_score(worst_case_loss_pct),
        "macro_fragility": compute_macro_fragility_score(macro_betas),
        "liquidity_score": round(max(0.0, min(100.0, liquidity_score_raw)), 1),
        "tail_risk_score": compute_tail_risk_score(
            abs(parametric_var_95_pct), abs(cvar_99_pct)
        ),
    }
