"""Concentration risk — HHI and Marginal Risk Contribution (§11)."""
from __future__ import annotations
import numpy as np
from typing import Any, List, Dict, Optional
from pydantic import BaseModel

class MarginalRiskContribution(BaseModel):
    ticker: str
    sector: str
    weight_pct: float
    marginal_risk_contribution: float
    risk_contribution: float
    risk_contribution_pct: float

class ConcentrationAnalysisResponse(BaseModel):
    hhi: float
    hhi_classification: str
    sector_concentration: Dict[str, float]
    marginal_risk_contributions: List[MarginalRiskContribution]
    concentration_score: float
    portfolio_volatility: float = 0.0

def compute_hhi(weights: np.ndarray) -> float:
    """Herfindahl-Hirschman Index.
    
    HHI = Σ(w_i * 100)²
    HHI < 1500: Diversified
    HHI 1500-2500: Moderate
    HHI > 2500: Concentrated
    
    Args:
        weights: 1D array of portfolio weights (sum to 1.0)
    """
    return float(np.sum((weights * 100) ** 2))

def hhi_classification(hhi: float) -> str:
    if hhi < 1500:
        return "Diversified"
    elif hhi < 2500:
        return "Moderate"
    return "Concentrated"

def sector_concentration(
    weights: np.ndarray,
    sectors: list[str],
) -> dict[str, float]:
    """Sector-level HHI decomposition."""
    sector_weights = {}
    for w, s in zip(weights, sectors):
        sector_weights[s] = sector_weights.get(s, 0.0) + float(w)
    return sector_weights

def marginal_risk_contribution(
    weights: np.ndarray,
    covariance: np.ndarray,
) -> np.ndarray:
    """Marginal Risk Contribution using Euler's theorem (§11.2).
    
    MRC_i = (Σw)_i / σ_p
    RC_i = w_i * MRC_i
    
    Uses the CRISIS covariance matrix for worst-case analysis.
    
    Args:
        weights: 1D array of portfolio weights
        covariance: NxN covariance matrix (use Σ_crisis for stress testing)
    
    Returns:
        MRC values as 1D array
    """
    n = len(weights)
    if n == 0:
        return np.zeros(0)
    
    portfolio_var = weights @ covariance @ weights
    if portfolio_var <= 0:
        portfolio_vol = 0.0
    else:
        portfolio_vol = float(np.sqrt(portfolio_var))
    
    if portfolio_vol < 1e-10:
        return np.zeros(n)
    
    mrc = (covariance @ weights) / portfolio_vol
    return mrc

def compute_concentration_analysis(
    tickers: list[str],
    weights: np.ndarray,
    sectors: list[str],
    covariance: np.ndarray,
) -> ConcentrationAnalysisResponse:
    """Full concentration analysis for stress test response."""
    n = len(weights)
    if n == 0:
        return ConcentrationAnalysisResponse(
            hhi=0.0, 
            hhi_classification="N/A",
            sector_concentration={},
            marginal_risk_contributions=[],
            concentration_score=100.0,
            portfolio_volatility=0.0,
        )
    
    hhi = compute_hhi(weights)
    sec_conc = sector_concentration(weights, sectors)
    mrc = marginal_risk_contribution(weights, covariance)
    
    portfolio_var = weights @ covariance @ weights
    portfolio_vol = float(np.sqrt(portfolio_var)) if portfolio_var > 0 else 0.0
    
    holdings_mrc = []
    for i in range(n):
        if portfolio_vol > 1e-10:
            rc = float(weights[i] * mrc[i])
        else:
            rc = 0.0
        holdings_mrc.append(MarginalRiskContribution(
            ticker=tickers[i],
            sector=sectors[i],
            weight_pct=round(float(weights[i]) * 100, 2),
            marginal_risk_contribution=round(float(mrc[i]), 6),
            risk_contribution=round(rc, 6),
            risk_contribution_pct=round(rc / (np.sum(np.abs(mrc) * weights) + 1e-10) * 100, 2) if portfolio_vol > 0 else 0.0,
        ))
    
    holdings_mrc.sort(key=lambda x: abs(x.risk_contribution), reverse=True)
    
    conc_score = max(0.0, min(100.0, 100.0 - 20.0 * (np.log(hhi + 1) - np.log(1))))
    
    return ConcentrationAnalysisResponse(
        hhi=round(hhi, 1),
        hhi_classification=hhi_classification(hhi),
        sector_concentration={k: round(v, 4) for k, v in sec_conc.items()},
        marginal_risk_contributions=holdings_mrc[:10],
        concentration_score=round(conc_score, 1),
        portfolio_volatility=round(portfolio_vol, 6),
    )
