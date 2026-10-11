"""MATH-22: XIRR falls back to bisection when Newton diverges, and the IV solver
reports None (not a non-converged sigma) when it cannot converge."""
from datetime import date

import pytest

from services.math_engines.implied_volatility_engine import calculate_bs_price, calculate_implied_volatility
from services.math_engines.xirr_calculator import xirr


def test_xirr_two_year_ten_percent():
    flows = [(date(2025, 1, 1), -100.0), (date(2027, 1, 1), 121.0)]  # 730 days
    assert xirr(flows).value == pytest.approx(0.10, abs=1e-4)


def test_xirr_bisection_when_newton_overshoots_below_minus_one():
    # From guess=50 the first Newton step lands near -2260 (rate <= -1): the old
    # solver returned garbage / raised; the fallback must still find 10%.
    flows = [(date(2025, 1, 1), -100.0), (date(2026, 1, 1), 110.0)]  # 365 days
    assert xirr(flows, guess=50.0).value == pytest.approx(0.10, abs=1e-4)


def test_xirr_without_sign_change_raises():
    with pytest.raises(ValueError):
        xirr([(date(2025, 1, 1), -100.0), (date(2026, 1, 1), -10.0)])


def test_iv_recovers_known_sigma():
    price = calculate_bs_price(100.0, 105.0, 0.5, 0.06, 0.25, "call")
    iv = calculate_implied_volatility(price, 100.0, 105.0, 0.5, 0.06, "call").implied_volatility
    assert iv == pytest.approx(0.25, abs=1e-3)


def test_iv_unreachable_price_returns_none():
    # A call can never be worth more than the underlying, so no sigma prices it at 150.
    res = calculate_implied_volatility(150.0, 100.0, 200.0, 0.1, 0.05, "call")
    assert res.implied_volatility is None
