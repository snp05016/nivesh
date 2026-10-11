"""Vasicek Bayesian Shrinkage estimator for equity beta sensitivities (§4.2)."""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class MacroBetasResponse(BaseModel):
    market: float
    midcap: float
    smallcap: float
    oil: float
    rates: float
    fx: float
    inflation: float
    fii_flow: float
    dii_flow: float
    # "estimated" when market beta came from >= 20 aligned daily returns, else "default" (1.0)
    market_beta_source: str = "estimated"

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
    var_beta = ts_se ** 2
    if prior_var + var_beta < 1e-10:
        return ts_beta
    w = prior_var / (prior_var + var_beta)
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

SECTOR_PRIOR_BETAS = {
    "IT": 1.1,
    "Banking": 1.2,
    "FMCG": 0.8,
    "Auto": 1.15,
    "Pharma": 0.75,
    "Oil & Gas": 1.05,
    "Power": 0.9,
    "Metals": 1.3,
    "Cement": 1.1,
    "NBFC": 1.25,
    "Defence": 1.0,
    "Infra": 1.1,
    "Real Estate": 1.3,
    "Telecom": 1.05,
    "Other": 1.0
}

def get_adjusted_macro_betas(ticker: str, sector: str = "Other") -> MacroBetasResponse:
    """
    Fetch 1-year historical daily returns for the ticker and benchmark (^NSEI) using yfinance.
    Compute empirical beta and its standard error, then shrink towards a sector mean.
    Returns the adjusted macro factor betas required by stress_test.py.
    Only the market beta is estimated; the other factor betas are 0.0.
    """
    beta_source = "estimated"
    try:
        # Fetch 1-year historical daily returns
        stock_data = yf.download(ticker, period="1y", interval="1d", progress=False)
        market_data = yf.download("^NSEI", period="1y", interval="1d", progress=False)
        
        if stock_data.empty and not ticker.endswith(".NS"):
            stock_data = yf.download(f"{ticker}.NS", period="1y", interval="1d", progress=False)
            
        if stock_data.empty or market_data.empty:
            raise ValueError("Empty data fetched from yfinance")
            
        stock_prices = stock_data["Adj Close"] if "Adj Close" in stock_data else stock_data["Close"]
        market_prices = market_data["Adj Close"] if "Adj Close" in market_data else market_data["Close"]
        
        if isinstance(stock_prices, pd.DataFrame):
            stock_prices = stock_prices.iloc[:, 0]
        if isinstance(market_prices, pd.DataFrame):
            market_prices = market_prices.iloc[:, 0]
            
        stock_ret = np.log(stock_prices / stock_prices.shift(1)).dropna()
        market_ret = np.log(market_prices / market_prices.shift(1)).dropna()
        
        # Align dates
        df = pd.concat([stock_ret, market_ret], axis=1, join="inner").dropna()
        if len(df) < 20:
            logging.warning("[Vasicek] only %d aligned returns for %s, defaulting beta to 1.0", len(df), ticker)
            market_beta = 1.0
            beta_source = "default"
        else:
            s_ret = df.iloc[:, 0].values
            m_ret = df.iloc[:, 1].values
            
            # Empirical beta
            cov = np.cov(s_ret, m_ret)[0, 1]
            var_m = np.var(m_ret, ddof=1)
            emp_beta = cov / var_m if var_m > 1e-10 else 1.0
            
            # Standard error of beta
            residuals = s_ret - emp_beta * m_ret
            se_res = np.std(residuals, ddof=1)
            se_m = np.std(m_ret, ddof=1)
            n = len(s_ret)
            ts_se = se_res / (se_m * np.sqrt(n)) if se_m > 1e-10 else 1.0
            
            # Vasicek Shrinkage
            prior_beta = SECTOR_PRIOR_BETAS.get(sector, 1.0)
            prior_var = 0.05  # Prior variance assumed for the sector
            
            market_beta = vasicek_shrinkage(
                ts_beta=emp_beta,
                ts_se=ts_se,
                prior_beta=prior_beta,
                prior_var=prior_var
            )
            
    except Exception as exc:
        logging.warning("[Vasicek] beta estimation failed for %s, defaulting to 1.0: %s", ticker, exc)
        market_beta = 1.0
        beta_source = "default"

    # ponytail: macro/flow/size betas not estimated (0.0, the stress engine applies the market
    # leg and size buckets instead); add factor regressions (BZ=F, INR=X, ...) when needed
    return MacroBetasResponse(
        market=float(market_beta),
        midcap=0.0,
        smallcap=0.0,
        oil=0.0,
        rates=0.0,
        fx=0.0,
        inflation=0.0,
        fii_flow=0.0,
        dii_flow=0.0,
        market_beta_source=beta_source,
    )
