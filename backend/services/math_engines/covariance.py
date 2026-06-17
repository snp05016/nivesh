"""Covariance matrices for stress testing — normal and crisis regimes."""
from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional

def fetch_historical_returns(tickers: list[str], period: str = "2y") -> dict[str, np.ndarray]:
    """Fetch daily returns for a list of tickers via yfinance."""
    returns_dict = {}
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            hist = ticker_obj.history(period=period)
            if not hist.empty and "Close" in hist.columns:
                rets = hist["Close"].pct_change().dropna()
                returns_dict[t] = rets.values
            else:
                returns_dict[t] = np.array([])
        except Exception:
            returns_dict[t] = np.array([])
    return returns_dict

def fetch_and_compute_covariance(tickers: list[str], period: str = "2y") -> np.ndarray:
    """Construct an N x N covariance matrix from historical returns (fetch via yfinance)."""
    returns_dict = fetch_historical_returns(tickers, period)
    return compute_covariance_matrix(returns_dict, tickers)

def compute_covariance_matrix(
    returns: dict[str, np.ndarray],
    ticker_order: list[str],
) -> np.ndarray:
    """Compute sample covariance matrix from aligned return arrays.
    
    Returns NxN matrix where N = len(ticker_order).
    """
    n = len(ticker_order)
    aligned = []
    for ticker in ticker_order:
        rets = returns.get(ticker)
        if rets is None or len(rets) < 5:
            aligned.append(np.array([]))
        else:
            aligned.append(rets)
    
    lengths = [len(a) for a in aligned if len(a) > 0]
    if not lengths:
        return np.eye(n) * 0.0001
    common_len = min(lengths)
    
    matrix = []
    for arr in aligned:
        if len(arr) == 0:
            matrix.append(arr)
        else:
            matrix.append(arr[-common_len:])
    
    data = np.column_stack([m for m in matrix if len(m) > 0])
    if data.shape[1] < 2:
        return np.eye(n) * 0.0001
    
    cov = np.cov(data.T)
    full_cov = np.eye(n) * np.mean(np.diag(cov) if cov.size > 0 else 0.0001)
    valid_indices = [i for i, arr in enumerate(matrix) if len(arr) > 0]
    for i, vi in enumerate(valid_indices):
        for j, vj in enumerate(valid_indices):
            if i < cov.shape[0] and j < cov.shape[1]:
                full_cov[vi, vj] = cov[i, j]
    return full_cov

def compute_crisis_covariance(
    returns: dict[str, np.ndarray],
    ticker_order: list[str],
    broken_arrow_corr: float = 0.85,
) -> np.ndarray:
    """Broken Arrow heuristic: In a severe crash scenario, artificially inflate 
    all pairwise equity correlations to ~0.85 to simulate correlation breakdown.
    
    During stress tests, this matrix replaces the normal covariance to
    model correlation breakdown.
    """
    n = len(ticker_order)
    if n == 0:
        return np.array([])
    
    # Base covariance
    cov = compute_covariance_matrix(returns, ticker_order)
    
    if cov.size == 0:
        return cov
        
    # Extract variances to compute volatilities
    variances = np.diag(cov)
    vols = np.sqrt(np.maximum(variances, 1e-12))
    
    # Broken Arrow Protocol: inflate correlations
    corr = np.ones((n, n)) * broken_arrow_corr
    np.fill_diagonal(corr, 1.0)
    
    # Reconstruct covariance: Σ = D * R * D
    vol_matrix = np.outer(vols, vols)
    crisis_cov = corr * vol_matrix
    
    return crisis_cov

def conditional_shock_propagation(
    shocked_factors: dict[str, float],
    unshocked_factors: list[str],
    factor_cov: np.ndarray,
    factor_names: list[str],
    factor_means: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    """MSCI/BlackRock conditional expectation propagation (§2).
    
    Given shocks to core factors f1, compute expected moves in
    unshocked factors f2 using the covariance structure:
    
    E[f2 | f1] = μ2 + Σ21 * Σ11⁻¹ * (Δf1 - μ1)
    
    Args:
        shocked_factors: {factor_name: shock_value} for core factors
        unshocked_factors: list of factor names to estimate
        factor_cov: NxN factor covariance matrix
        factor_names: ordered list of all factor names
        factor_means: optional dict of factor means
    
    Returns:
        dict of factor_name -> propagated_shock_value
    """
    if factor_means is None:
        factor_means = {}
    
    n = len(factor_names)
    shocked_indices = [factor_names.index(f) for f in shocked_factors if f in factor_names]
    unshocked_indices = [factor_names.index(f) for f in unshocked_factors if f in factor_names]
    
    if not shocked_indices or not unshocked_indices:
        return {f: 0.0 for f in unshocked_factors}
    
    sigma_11 = factor_cov[np.ix_(shocked_indices, shocked_indices)]
    sigma_21 = factor_cov[np.ix_(unshocked_indices, shocked_indices)]
    sigma_22 = factor_cov[np.ix_(unshocked_indices, unshocked_indices)]
    
    mu_1 = np.array([factor_means.get(factor_names[i], 0.0) for i in shocked_indices])
    mu_2 = np.array([factor_means.get(factor_names[i], 0.0) for i in unshocked_indices])
    delta_f1 = np.array([shocked_factors.get(factor_names[i], 0.0) for i in shocked_indices])
    
    try:
        sigma_11_inv = np.linalg.inv(sigma_11)
        propagated = mu_2 + sigma_21 @ sigma_11_inv @ (delta_f1 - mu_1)
    except np.linalg.LinAlgError:
        diag_11 = np.diag(sigma_11)
        diag_11[diag_11 < 1e-10] = 1e-10
        corr_ratio = sigma_21 / diag_11[np.newaxis, :]
        propagated = mu_2 + np.mean(corr_ratio * (delta_f1 - mu_1), axis=1)
    
    result = {}
    for i, idx in enumerate(unshocked_indices):
        result[factor_names[idx]] = float(propagated[i])
    return result
