"""Stress-test scenario wiring, units and end-to-end engine contract (no network)."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from services import stress_test
from services.math_engines.liquidity import liquidity_score, square_root_impact
from services.math_engines.vasicek import MacroBetasResponse
from services.stress_test import SCENARIOS_DEF, _holding_impact_pct


def _holding(ticker="INFY", sector="IT", size="large", market_beta=1.0):
    return {
        "ticker": ticker,
        "sector": sector,
        "size_bucket": size,
        "betas": {"market": market_beta, "oil": 0.0, "rates": 0.0, "fx": 0.0,
                  "inflation": 0.0, "fii_flow": 0.0, "dii_flow": 0.0},
        "value": 100_000.0,
    }


def _betas(market=1.0):
    return MacroBetasResponse(
        market=market, midcap=0.0, smallcap=0.0, oil=0.0, rates=0.0,
        fx=0.0, inflation=0.0, fii_flow=0.0, dii_flow=0.0,
    )


def _unit_returns(daily_std, n=252, seed=0):
    r = np.random.default_rng(seed).normal(size=n)
    return (r - r.mean()) / r.std(ddof=1) * daily_std


@pytest.fixture
def market_edges(monkeypatch):
    """Mock only the network edges; the engines themselves run for real."""
    state = {"returns": lambda sym: _unit_returns(0.015, n=300), "history_calls": []}

    def fake_history(tickers, period="2y"):
        state["history_calls"].append(list(tickers))
        return {t: state["returns"](t) for t in tickers}

    monkeypatch.setattr(stress_test, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(stress_test, "_yf_price", lambda sym: (1000.0, 990.0))
    monkeypatch.setattr(
        stress_test,
        "_yf_fetch_info",
        lambda sym: {"beta": 1.0, "averageVolume": 1e6, "marketCap": 5e12, "currentPrice": 1000},
    )
    monkeypatch.setattr(stress_test, "get_adjusted_macro_betas", lambda sym, sector: _betas())
    monkeypatch.setattr(
        "services.math_engines.covariance.fetch_historical_returns", fake_history
    )
    return state


def test_every_downside_scenario_is_non_positive():
    h = _holding()
    impacts = {key: _holding_impact_pct(h, sc) for key, sc in SCENARIOS_DEF.items()}
    for key, impact in impacts.items():
        if key != "rate_cut":
            assert impact < 0, f"{key} produced {impact}"
    # The scenario's Nifty leg is applied (beta 1.0 x nifty) when there is no market shock.
    assert impacts["oil_shock"] == -5.0
    assert impacts["currency_crash"] == -10.0
    assert impacts["fii_exodus"] == -12.0
    assert impacts["dii_exodus"] == -6.0
    assert impacts["rate_cut"] == 3.0


def test_market_beta_scales_nifty_leg():
    assert _holding_impact_pct(_holding(market_beta=0.9), SCENARIOS_DEF["oil_shock"]) == pytest.approx(-4.5)


def test_midcap_crash_uses_size_leg():
    sc = SCENARIOS_DEF["midcap_crash"]
    assert _holding_impact_pct(_holding(size="mid"), sc) == -25.0
    assert _holding_impact_pct(_holding(size="large"), sc) == -10.0
    assert _holding_impact_pct(_holding(size="small"), SCENARIOS_DEF["smallcap_crash"]) == -30.0


def test_policy_shock_psu_override():
    sc = SCENARIOS_DEF["policy_shock"]
    assert _holding_impact_pct(_holding(ticker="SBIN", sector="Banking"), sc) == -48.0
    assert _holding_impact_pct(_holding(ticker="INFY"), sc) == -18.0


def test_cash_is_never_shocked():
    assert _holding_impact_pct(_holding(ticker="CASH", sector="Cash"), SCENARIOS_DEF["nifty_crash"]) == 0.0


def test_liquidity_impact_daily_vol():
    liq = square_root_impact(
        shares_held=10_000,
        avg_daily_volume=1e6,
        daily_volatility=0.0145,
        base_spread_bps=0.0005,
        gamma=0.2,
        volume_suppression=0.4,
    )
    assert liq.mkt_impact_pct < 0.1


def test_liquidity_score_monotonic():
    assert liquidity_score(0.1) > liquidity_score(1.0)


def test_run_stress_test_end_to_end_serialisable(market_edges):
    holdings = [
        SimpleNamespace(ticker="TCS", company_name="Tata Consultancy Services", shares=10, buy_price=900),
        SimpleNamespace(ticker="CASH", company_name="Cash", shares=5000, buy_price=1),
    ]

    results = stress_test.run_stress_test(holdings, ["nifty_crash", "oil_shock"])

    assert len(results) == 2
    json.dumps(results)  # stored as result_json; must be plain JSON types
    nifty, oil = results
    assert nifty["total_value"] == 15000.0  # 10 x 1000 live + 5000 cash
    assert nifty["impact_pct"] < oil["impact_pct"] < 0
    assert nifty["worst_case_pct"] <= nifty["impact_pct"]
    for score in nifty["scores"].values():
        assert 0.0 <= score <= 100.0
    assert market_edges["history_calls"] == [["TCS.NS"]]  # cash is never fetched
    assert nifty["data_quality"]["degraded"] is False
    assert nifty["assumptions"]


def test_var_uses_daily_sigma(market_edges):
    """sigma_daily 1.45% (~23% annual): 10-day 95% VaR ~7.5%, not ~120%."""
    market_edges["returns"] = lambda sym: _unit_returns(0.0145)
    holdings = [SimpleNamespace(ticker="TCS", company_name="Tata Consultancy Services", shares=10, buy_price=900)]

    scores = stress_test.run_stress_test(holdings, ["nifty_crash"])[0]["scores"]

    # Risk score from annualized vol 0.0145 * sqrt(252) = 23.0%: sigmoid(23, 25, 0.08) = 46.0
    assert scores["risk_score"] == pytest.approx(46.0, abs=0.2)
    # Stress score with the correct horizon is ~58 (the annual-as-daily bug gave ~8).
    assert 50.0 < scores["stress_score"] < 67.0


def test_cash_has_zero_variance(market_edges):
    holdings = [
        SimpleNamespace(ticker="TCS", company_name="Tata Consultancy Services", shares=10, buy_price=900),
        SimpleNamespace(ticker="CASH", company_name="Cash", shares=5000, buy_price=1),
    ]

    result = stress_test.run_stress_test(holdings, ["nifty_crash"])[0]

    mrc = {row["ticker"]: row for row in result["concentration"]["marginal_risk_contributions"]}
    assert mrc["CASH"]["risk_contribution"] == 0.0
    assert mrc["TCS"]["risk_contribution"] > 0.0
