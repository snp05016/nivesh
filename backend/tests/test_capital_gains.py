"""MATH-22: FIFO capital gains with a calendar-month LTCG boundary.

Listed equity is long-term only if held *more than* 12 months, so a sale exactly
12 calendar months after the buy (366 days when it spans 29 Feb) is still STCG.
"""
from datetime import date

import pytest

from services.math_engines.capital_gains_calculator import Transaction, calculate_capital_gains


def _gains(*txns):
    return calculate_capital_gains([Transaction(*t) for t in txns])


def test_exactly_twelve_months_across_leap_day_is_stcg():
    gains = _gains((date(2023, 3, 1), "BUY", 10, 100.0), (date(2024, 3, 1), "SELL", 10, 150.0))
    assert gains.STCG == 500.0
    assert gains.LTCG == 0.0


def test_one_day_past_twelve_months_is_ltcg():
    gains = _gains((date(2023, 3, 1), "BUY", 10, 100.0), (date(2024, 3, 2), "SELL", 10, 150.0))
    assert gains.STCG == 0.0
    assert gains.LTCG == 500.0


def test_fifo_splits_a_sale_across_two_buys():
    gains = _gains(
        (date(2022, 1, 10), "BUY", 10, 100.0),  # held > 12 months at sale -> LTCG
        (date(2023, 6, 1), "BUY", 10, 200.0),   # held < 12 months at sale -> STCG
        (date(2023, 12, 1), "SELL", 15, 250.0),
    )
    assert gains.LTCG == 10 * (250.0 - 100.0)
    assert gains.STCG == 5 * (250.0 - 200.0)


def test_oversell_raises():
    with pytest.raises(ValueError):
        _gains((date(2023, 1, 1), "BUY", 5, 100.0), (date(2023, 2, 1), "SELL", 6, 110.0))
