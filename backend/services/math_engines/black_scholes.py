import math

def norm_cdf(x):
    """Cumulative distribution function for standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def calculate_d1_d2(S, K, T, r, sigma):
    """Calculate d1 and d2 parameters for Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return 0.0, 0.0
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2

def black_scholes_price(S, K, T, r, sigma, option_type="call"):
    """
    Calculate Black-Scholes option price.
    
    Args:
        S (float): Current underlying asset price
        K (float): Strike price
        T (float): Time to expiration in years
        r (float): Risk-free interest rate (annual)
        sigma (float): Implied volatility
        option_type (str): "call" or "put"
        
    Returns:
        float: Option price
    """
    if T <= 0:
        if option_type == "call":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)
            
    if sigma <= 0:
        if option_type == "call":
            return max(0.0, S - K * math.exp(-r * T))
        else:
            return max(0.0, K * math.exp(-r * T) - S)

    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    
    if option_type == "call":
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    elif option_type == "put":
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    else:
        raise ValueError("option_type must be 'call' or 'put'")
        
    return price
