import pytest
import math

# Assuming standard function signature for black_scholes
# You may need to update the import path to point to your actual implementation
try:
    from pricing.black_scholes import black_scholes
except ImportError:
    # Dummy placeholder so tests can be defined
    def black_scholes(S, K, T, r, sigma, option_type="call"):
        return 0.0

def test_black_scholes_deep_itm_call():
    """
    Test a deep in-the-money call option (S >> K).
    The price should approach its lower bound intrinsic value: S - K * exp(-r*T).
    """
    S = 200.0
    K = 50.0
    T = 1.0
    r = 0.05
    sigma = 0.2
    
    price = black_scholes(S, K, T, r, sigma, option_type="call")
    expected_intrinsic = S - K * math.exp(-r * T)
    
    # The price should not be less than the expected intrinsic value
    assert price >= expected_intrinsic - 1e-4
    # With deep ITM, the time value approaches 0, so it should be very close to intrinsic
    assert math.isclose(price, expected_intrinsic, rel_tol=1e-2)

def test_black_scholes_deep_otm_call():
    """
    Test a deep out-of-the-money call option (S << K).
    The option is highly unlikely to be exercised, so its price should approach 0.
    """
    S = 50.0
    K = 200.0
    T = 1.0
    r = 0.05
    sigma = 0.2
    
    price = black_scholes(S, K, T, r, sigma, option_type="call")
    
    assert math.isclose(price, 0.0, abs_tol=1e-4)

def test_black_scholes_deep_itm_put():
    """
    Test a deep in-the-money put option (S << K).
    The price should approach its lower bound intrinsic value: K * exp(-r*T) - S.
    """
    S = 50.0
    K = 200.0
    T = 1.0
    r = 0.05
    sigma = 0.2
    
    price = black_scholes(S, K, T, r, sigma, option_type="put")
    expected_intrinsic = K * math.exp(-r * T) - S
    
    assert price >= expected_intrinsic - 1e-4
    assert math.isclose(price, expected_intrinsic, rel_tol=1e-2)

def test_black_scholes_deep_otm_put():
    """
    Test a deep out-of-the-money put option (S >> K).
    The option is highly unlikely to be exercised, so its price should approach 0.
    """
    S = 200.0
    K = 50.0
    T = 1.0
    r = 0.05
    sigma = 0.2
    
    price = black_scholes(S, K, T, r, sigma, option_type="put")
    
    assert math.isclose(price, 0.0, abs_tol=1e-4)

def test_black_scholes_zero_volatility():
    """
    Test options with 0 volatility.
    Without uncertainty, the price is exactly the discounted intrinsic payoff.
    """
    S = 100.0
    K = 100.0
    T = 1.0
    r = 0.05
    sigma = 0.0000001  # Very close to 0 to avoid division by zero in some implementations
    
    price_call = black_scholes(S, K, T, r, sigma, option_type="call")
    price_put = black_scholes(S, K, T, r, sigma, option_type="put")
    
    intrinsic_call = max(0.0, S - K * math.exp(-r * T))
    intrinsic_put = max(0.0, K * math.exp(-r * T) - S)
    
    assert math.isclose(price_call, intrinsic_call, rel_tol=1e-4, abs_tol=1e-4)
    assert math.isclose(price_put, intrinsic_put, rel_tol=1e-4, abs_tol=1e-4)

def test_black_scholes_zero_time_to_maturity():
    """
    Test options at expiration (T = 0).
    The price should be exactly the payoff function: max(0, S-K) for call, max(0, K-S) for put.
    """
    S = 100.0
    K_itm = 90.0
    K_otm = 110.0
    # Use a tiny T to avoid division by zero if T is in denominator of d1/d2 calculation
    T = 1e-10 
    r = 0.05
    sigma = 0.2
    
    call_itm = black_scholes(S, K_itm, T, r, sigma, option_type="call")
    call_otm = black_scholes(S, K_otm, T, r, sigma, option_type="call")
    put_itm = black_scholes(S, K_otm, T, r, sigma, option_type="put")
    put_otm = black_scholes(S, K_itm, T, r, sigma, option_type="put")
    
    assert math.isclose(call_itm, 10.0, rel_tol=1e-4, abs_tol=1e-4)
    assert math.isclose(call_otm, 0.0, abs_tol=1e-4)
    assert math.isclose(put_itm, 10.0, rel_tol=1e-4, abs_tol=1e-4)
    assert math.isclose(put_otm, 0.0, abs_tol=1e-4)

def test_put_call_parity():
    """
    Test that the implementation satisfies the Put-Call Parity:
    C - P = S - K * exp(-r*T)
    """
    S = 100.0
    K = 100.0
    T = 1.0
    r = 0.05
    sigma = 0.2
    
    call_price = black_scholes(S, K, T, r, sigma, option_type="call")
    put_price = black_scholes(S, K, T, r, sigma, option_type="put")
    
    expected_diff = S - K * math.exp(-r * T)
    actual_diff = call_price - put_price
    
    assert math.isclose(actual_diff, expected_diff, rel_tol=1e-5, abs_tol=1e-5)
