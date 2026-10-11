"""MATH-06: options payoff extremes, unlimited flags, breakevens and quantity scaling.

Pure-function tests on services.options_engine; no network, DB or LLM access.
"""

from __future__ import annotations

import pytest
from services.options_engine import compute_options_payoff


def _payoff(*legs, spot=100.0):
    return compute_options_payoff(spot_price=spot, legs=[dict(leg) for leg in legs])


def test_short_put_is_bounded_with_full_downside_loss():
    r = _payoff({"type": "PUT", "position": "SHORT", "strike": 100, "premium": 5})
    assert r["max_profit_unlimited"] is False
    assert r["max_loss_unlimited"] is False
    assert r["max_profit"] == pytest.approx(5)
    assert r["max_loss"] == pytest.approx(-95)
    assert r["breakevens"] == [95.0]
    assert r["pnl_basis"] == "per_share"


def test_long_put_loss_is_premium_and_profit_capped_at_zero_price():
    r = _payoff({"type": "PUT", "position": "LONG", "strike": 100, "premium": 5})
    assert r["max_profit_unlimited"] is False
    assert r["max_loss_unlimited"] is False
    assert r["max_loss"] == pytest.approx(-5)
    assert r["max_profit"] == pytest.approx(95)


def test_short_strangle_has_unlimited_loss_and_credit_as_max_profit():
    r = _payoff(
        {"type": "PUT", "position": "SHORT", "strike": 90, "premium": 3},
        {"type": "CALL", "position": "SHORT", "strike": 110, "premium": 3},
    )
    assert r["max_loss_unlimited"] is True
    assert r["max_loss"] is None
    assert r["max_profit_unlimited"] is False
    assert r["max_profit"] == pytest.approx(6)
    assert r["breakevens"] == [84.0, 116.0]


def test_long_straddle_loss_is_bounded():
    r = _payoff(
        {"type": "CALL", "position": "LONG", "strike": 100, "premium": 4},
        {"type": "PUT", "position": "LONG", "strike": 100, "premium": 4},
    )
    assert r["max_profit_unlimited"] is True
    assert r["max_loss_unlimited"] is False
    assert r["max_loss"] == pytest.approx(-8)
    assert r["breakevens"] == [92.0, 108.0]


def test_long_call_contract_unchanged():
    r = _payoff({"type": "CALL", "position": "LONG", "strike": 100, "premium": 5})
    assert r["max_profit_unlimited"] is True
    assert r["max_loss_unlimited"] is False
    assert r["max_loss"] == -5
    assert r["breakevens"] == [105.0]
    assert len(r["payoff_vector"]) == 100


def test_quantity_scales_pnl_and_marks_position_basis():
    r = _payoff({"type": "CALL", "position": "LONG", "strike": 100, "premium": 5, "quantity": 50})
    assert r["max_loss"] == pytest.approx(-250)
    assert r["net_premium"] == pytest.approx(-250)
    assert r["breakevens"] == [105.0]
    assert r["pnl_basis"] == "position"
    top = r["payoff_vector"][-1]  # S = 120 -> (120 - 100 - 5) * 50
    assert top["pnl"] == pytest.approx(750)


def test_breakeven_outside_chart_window_is_found():
    r = _payoff({"type": "PUT", "position": "SHORT", "strike": 100, "premium": 30})
    assert r["breakevens"] == [70.0]
    assert r["max_loss"] == pytest.approx(-70)


def test_non_positive_quantity_rejected():
    with pytest.raises(ValueError, match="quantity"):
        _payoff({"type": "CALL", "position": "LONG", "strike": 100, "premium": 5, "quantity": 0})
