"""Vasicek Bayesian Shrinkage estimator for equity beta sensitivities (§4.2)."""
from __future__ import annotations
import numpy as np
from typing import Optional

def compute_ewma_beta(
    stock_returns: np.ndarray,
    market_returns: np.ndarray,
    half_life: int = 63,
) -> float:
    """EWMA OLS beta with exponential decay weighting.
    
    Args:
        stock_returns: 1D array of daily log returns
        market_returns: 1D array of daily log returns (same length)
        half_life: decay half-life in trading days (default 63 = ~3 months)
    
    Returns:
        EWMA-weighted beta coefficient
    """
    n = len(stock_returns)
    if n < 20:
        return 1.0
    
    decay = np.log(2) / half_life
    weights = np.exp(-decay * np.arange(n)[::-1])
    weights = weights / weights.sum()
    
    stock_mean = np.average(stock_returns, weights=weights)
    market_mean = np.average(market_returns, weights=weights)
    
    stock_centered = stock_returns - stock_mean
    market_centered = market_returns - market_mean
    
    cov = np.average(stock_centered * market_centered, weights=weights)
    var = np.average(market_centered * market_centered, weights=weights)
    
    if var < 1e-10:
        return 1.0
    return cov / var

def vasicek_shrinkage(
    ts_beta: float,
    ts_se: float,
    prior_beta: float,
    prior_var: float,
) -> float:
    """Vasicek (1973) Bayesian shrinkage estimator.
    
    Shrinks raw time-series beta toward a prior (sector mean) by weighting
    by the relative precision (inverse variance) of each estimate.
    
    β_shrink = w * β_ts + (1-w) * β_prior
    w = σ²_prior / (σ²_prior + σ²_ts)
    
    Args:
        ts_beta: raw time-series (EWMA) beta estimate
        ts_se: standard error of the ts_beta
        prior_beta: cross-sectional prior (sector mean beta)
        prior_var: variance of the prior distribution
    
    Returns:
        Vasicek-shrunk beta
    """
    if prior_var + ts_se**2 < 1e-10:
        return ts_beta
    w = prior_var / (prior_var + ts_se**2)
    return w * ts_beta + (1 - w) * prior_beta

def compute_factor_sensitivities(
    stock_returns: np.ndarray,
    factor_returns: dict[str, np.ndarray],
    half_life: int = 63,
) -> dict[str, float]:
    """Compute Vasicek-shrunk betas for multiple macro factors.
    
    Args:
        stock_returns: 1D array of daily log returns
        factor_returns: dict of factor_name -> 1D daily return array
        half_life: EWMA half-life
    
    Returns:
        dict of factor_name -> shrunk_beta
    """
    betas = {}
    for factor_name, factor_ret in factor_returns.items():
        if len(factor_ret) < 20:
            betas[factor_name] = 0.0
            continue
        raw_beta = compute_ewma_beta(stock_returns, factor_ret, half_life)
        n = min(len(stock_returns), len(factor_ret))
        residuals = stock_returns[-n:] - raw_beta * factor_ret[-n:]
        se_residual = np.std(residuals)
        se_factor = np.std(factor_ret[-n:])
        if se_factor < 1e-10:
            betas[factor_name] = raw_beta
            continue
        ts_se = se_residual / (se_factor * np.sqrt(n))
        shrunk = vasicek_shrinkage(raw_beta, ts_se, prior_beta=0.0, prior_var=1.0)
        betas[factor_name] = float(shrunk)
    return betas
