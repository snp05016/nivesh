"""Deterministic financial service tests with no live market or LLM access."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from services.options_engine import compute_options_payoff
from services.stress_test import get_sector, run_stress_test


def test_options_long_call_payoff_contract_uses_indian_numbering():
    result = compute_options_payoff(
        spot_price=100,
        legs=[{"type": "CALL", "position": "LONG", "strike": 100, "premium": 5}],
    )

    assert result["strategy_type"] == "Long Call"
    assert result["max_profit_unlimited"] is True
    assert result["max_loss_unlimited"] is False
    assert result["max_loss"] == -5
    assert result["net_premium"] == -5
    assert result["net_premium_formatted"] == "-₹5"
    assert "Million" not in result["net_premium_formatted"]
    assert len(result["payoff_vector"]) == 100
    assert result["breakevens"] == [105.0]


def test_options_rejects_invalid_strategy_inputs():
    with pytest.raises(ValueError, match="At least one leg"):
        compute_options_payoff(spot_price=100, legs=[])

    with pytest.raises(ValueError, match="Spot price"):
        compute_options_payoff(spot_price=0, legs=[{"type": "CALL", "position": "LONG", "strike": 100}])

    with pytest.raises(ValueError, match="type must be CALL or PUT"):
        compute_options_payoff(spot_price=100, legs=[{"type": "FUT", "position": "LONG", "strike": 100}])


@dataclass
class Holding:
    ticker: str
    company_name: str
    shares: float
    buy_price: float


def test_stress_test_sector_classification_and_cash_handling(monkeypatch):
    holdings = [
        Holding("INFY", "Infosys Ltd", 10, 1000),
        Holding("CASH", "Cash", 5000, 1),
    ]

    monkeypatch.setattr("services.stress_test._yf_price", lambda ticker: 1200.0)
    monkeypatch.setattr("services.stress_test._yf_fetch_info", lambda ticker: {"beta": 1.2})

    result = run_stress_test(holdings, ["currency_crash"])

    assert get_sector("Infosys Ltd") == "IT"
    assert result[0]["name"] == "CURRENCY_CRASH"
    cash = next(row for row in result[0]["holdings"] if row["ticker"] == "CASH")
    infy = next(row for row in result[0]["holdings"] if row["ticker"] == "INFY")
    assert cash["impact_pct"] == 0.0
    assert infy["impact_pct"] == 0.0


def test_unknown_stress_scenario_is_ignored(monkeypatch):
    monkeypatch.setattr("services.stress_test._yf_price", lambda ticker: 100.0)
    monkeypatch.setattr("services.stress_test._yf_fetch_info", lambda ticker: {"beta": 1.0})

    assert run_stress_test([Holding("TCS", "Tata Consultancy Services", 1, 100)], ["missing"]) == []
