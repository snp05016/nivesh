"""Stress-test data provenance: NSE symbol resolution, degraded flags, hard failure (no network)."""
from types import SimpleNamespace

import numpy as np
import pytest

from services import stress_test
from services.math_engines.vasicek import MacroBetasResponse


def _betas(sym, sector):
    return MacroBetasResponse(
        market=1.0, midcap=0.0, smallcap=0.0, oil=0.0, rates=0.0,
        fx=0.0, inflation=0.0, fii_flow=0.0, dii_flow=0.0,
    )


@pytest.fixture
def edges(monkeypatch):
    """Record every symbol that reaches a network edge; prices/returns configurable per test."""
    state = {
        "seen": [],
        "price": lambda sym: (100.0, 99.0),
        "returns": lambda sym: np.random.default_rng(1).normal(0, 0.015, 300),
    }

    def fake_price(sym):
        state["seen"].append(sym)
        return state["price"](sym)

    def fake_info(sym):
        state["seen"].append(sym)
        return {"beta": 1.0, "averageVolume": 1e6, "marketCap": 5e12}

    def fake_betas(sym, sector):
        state["seen"].append(sym)
        return _betas(sym, sector)

    def fake_history(tickers, period="2y"):
        state["seen"].extend(tickers)
        return {t: state["returns"](t) for t in tickers}

    monkeypatch.setattr(stress_test, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(stress_test, "_yf_price", fake_price)
    monkeypatch.setattr(stress_test, "_yf_fetch_info", fake_info)
    monkeypatch.setattr(stress_test, "get_adjusted_macro_betas", fake_betas)
    monkeypatch.setattr("services.math_engines.covariance.fetch_historical_returns", fake_history)
    return state


def test_enrich_uses_ns_symbols(edges):
    holding = SimpleNamespace(ticker="HAL", company_name="Hindustan Aeronautics", shares=5, buy_price=4000)

    results = stress_test.run_stress_test([holding], ["nifty_crash"])

    assert edges["seen"]
    assert all(sym.endswith(".NS") for sym in edges["seen"]), edges["seen"]
    assert results[0]["holdings"][0]["ticker"] == "HAL"  # display ticker stays bare


def test_all_data_missing_fails_job(edges):
    edges["price"] = lambda sym: (None, None)
    edges["returns"] = lambda sym: np.array([])
    holdings = [
        SimpleNamespace(ticker="AAA", company_name="Alpha Corp", shares=10, buy_price=100),
        SimpleNamespace(ticker="BBB", company_name="Beta Corp", shares=10, buy_price=100),
    ]

    with pytest.raises(RuntimeError, match="Insufficient market data"):
        stress_test.run_stress_test(holdings, ["nifty_crash"])


def test_partial_data_marks_degraded(edges):
    edges["price"] = lambda sym: (100.0, 100.0) if sym.startswith("AAA") else (None, None)
    edges["returns"] = lambda sym: np.array([])
    holdings = [
        SimpleNamespace(ticker="AAA", company_name="Alpha Corp", shares=95, buy_price=90),
        SimpleNamespace(ticker="BBB", company_name="Beta Corp", shares=5, buy_price=100),
    ]

    result = stress_test.run_stress_test(holdings, ["nifty_crash"])[0]

    dq = result["data_quality"]
    assert dq["coverage_pct"] == 95.0
    assert dq["cost_basis_tickers"] == ["BBB"]
    assert dq["covariance"] == "identity_fallback"
    assert dq["degraded"] is True
    assert all(row["is_estimated"] for row in result["holdings"])


def test_fully_measured_portfolio_is_not_degraded(edges):
    holding = SimpleNamespace(ticker="TCS", company_name="Tata Consultancy Services", shares=10, buy_price=90)

    result = stress_test.run_stress_test([holding], ["oil_shock"])[0]

    assert result["data_quality"]["degraded"] is False
    assert result["data_quality"]["covariance"] == "historical"
    assert result["holdings"][0]["is_estimated"] is False
