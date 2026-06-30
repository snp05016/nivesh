import math
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class ImpliedVolatilityResponse(BaseModel):
    implied_volatility: Optional[float]

def norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x):
    return math.exp(-x**2 / 2.0) / math.sqrt(2.0 * math.pi)

def calculate_bs_price(S, K, T, r, sigma, option_type):
    if T <= 0 or sigma <= 0:
        if option_type == "call":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)
            
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

def vega(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return S * norm_pdf(d1) * math.sqrt(T)

def calculate_implied_volatility(market_price, S, K, T, r, option_type="call", max_iter=100, tol=1e-5) -> ImpliedVolatilityResponse:
    """
    Calculate Implied Volatility using Newton-Raphson method.
    
    Args:
        market_price (float): Observed market price of the option
        S (float): Current underlying asset price
        K (float): Strike price
        T (float): Time to expiration in years
        r (float): Risk-free interest rate (annual)
        option_type (str): "call" or "put"
        max_iter (int): Maximum number of iterations
        tol (float): Tolerance for convergence
        
    Returns:
        ImpliedVolatilityResponse: Implied volatility, or None if it fails to converge
    """
    # Check bounds
    if option_type == "call":
        intrinsic_value = max(0.0, S - K * math.exp(-r * T))
    elif option_type == "put":
        intrinsic_value = max(0.0, K * math.exp(-r * T) - S)
    else:
        raise ValueError("option_type must be 'call' or 'put'")
        
    if market_price < intrinsic_value:
        return ImpliedVolatilityResponse(implied_volatility=None) # Arbitrage violation, IV is undefined
        
    # Initial guess
    sigma = math.sqrt(2 * math.pi / T) * (market_price / S) if S > 0 and T > 0 else 0.5
    if sigma <= 0 or sigma > 5.0:
        sigma = 0.5 # fallback

    for i in range(max_iter):
        price = calculate_bs_price(S, K, T, r, sigma, option_type)
        diff = price - market_price
        
        if abs(diff) < tol:
            return ImpliedVolatilityResponse(implied_volatility=sigma)
            
        v = vega(S, K, T, r, sigma)
        if v == 0.0:
            break
            
        sigma = sigma - diff / v
        
        if sigma <= 0:
            sigma = 1e-4 # prevent negative IV
            
    return ImpliedVolatilityResponse(implied_volatility=sigma)
