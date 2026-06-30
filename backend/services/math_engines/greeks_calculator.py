import math
from pydantic import BaseModel

class GreeksResponse(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

def norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x):
    return math.exp(-x**2 / 2.0) / math.sqrt(2.0 * math.pi)

def calculate_d1_d2(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0, 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2

def calculate_greeks(S, K, T, r, sigma, option_type="call") -> GreeksResponse:
    """
    Calculate Greeks (Delta, Gamma, Theta, Vega, Rho) for an option.
    
    Args:
        S (float): Current underlying asset price
        K (float): Strike price
        T (float): Time to expiration in years
        r (float): Risk-free interest rate (annual)
        sigma (float): Implied volatility
        option_type (str): "call" or "put"
        
    Returns:
        dict: Dictionary containing Delta, Gamma, Theta, Vega, and Rho
    """
    if T <= 0 or sigma <= 0:
        return GreeksResponse(delta=0.0, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)

    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    
    # Gamma and Vega are the same for calls and puts
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * norm_pdf(d1) * math.sqrt(T) / 100.0  # usually expressed per 1% change in vol
    
    if option_type == "call":
        delta = norm_cdf(d1)
        theta = (- (S * norm_pdf(d1) * sigma) / (2 * math.sqrt(T)) 
                 - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365.0 # usually expressed per day
        rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100.0 # per 1% change in rate
    elif option_type == "put":
        delta = norm_cdf(d1) - 1.0
        theta = (- (S * norm_pdf(d1) * sigma) / (2 * math.sqrt(T)) 
                 + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0
        rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100.0
    else:
        raise ValueError("option_type must be 'call' or 'put'")
        
    return GreeksResponse(
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho
    )
