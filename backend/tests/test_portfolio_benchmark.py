"""MATH-04: portfolio vs Nifty is money-weighted, never annualizes a sub-year period,
and reports no Nifty number when Nifty data is missing (pure, no network)."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from services.portfolio_service import compute_benchmark, holding_cashflows

TODAY = date(2026, 1, 1)


def test_short_period_is_absolute():
    flows = [(TODAY - timedelta(days=1), -1_00_000.0)]

    r = compute_benchmark(flows, 1_01_500.0, None, TODAY)

    assert r["return_basis"] == "absolute"
    assert r["portfolio_cagr_pct"] == 1.5  # not 1.015 ** 365.25 - 1 (~22,900%)
    assert r["period_days"] == 1


def test_long_period_xirr():
    r = compute_benchmark([(date(2024, 1, 1), -100.0)], 121.0, None, TODAY)

    assert r["return_basis"] == "annualized_xirr"
    assert r["portfolio_cagr_pct"] == pytest.approx(10.0, abs=0.1)


def test_nifty_pme_matches_flows():
    start = TODAY - timedelta(days=100)
    flows = [(start, -1000.0)]
    nifty = [(start, 100.0), (TODAY, 110.0)]

    r = compute_benchmark(flows, 1150.0, nifty, TODAY)

    assert r["nifty_cagr_pct"] == 10.0
    assert r["portfolio_cagr_pct"] == 15.0
    assert r["alpha_pct"] == 5.0


def test_nifty_pme_buys_at_each_flow_date():
    """A second BUY when Nifty is at 200 buys half the units of the first at 100."""
    d1, d2 = TODAY - timedelta(days=200), TODAY - timedelta(days=100)
    flows = [(d1, -1000.0), (d2, -1000.0)]
    nifty = [(d1, 100.0), (d2, 200.0), (TODAY, 200.0)]

    r = compute_benchmark(flows, 2000.0, nifty, TODAY)

    assert r["nifty_cagr_pct"] == 50.0  # 10 + 5 units x 200 = 3000 on 2000 in


def test_nifty_unavailable_returns_none():
    r = compute_benchmark([(TODAY - timedelta(days=10), -100.0)], 110.0, None, TODAY)

    assert r["nifty_cagr_pct"] is None
    assert r["alpha_pct"] is None


def test_nifty_none_when_sells_exceed_pme_units():
    """Sold 90% of a 5x winner: PME units go negative, XIRR has no root -> None, no raise."""
    flows = [(date(2024, 1, 1), -10_000.0), (date(2025, 1, 1), 45_000.0)]
    nifty = [(date(2024, 1, 1), 100.0), (date(2025, 1, 1), 100.0), (TODAY, 200.0)]

    r = compute_benchmark(flows, 5_000.0, nifty, TODAY)

    assert r["nifty_cagr_pct"] is None
    assert r["alpha_pct"] is None
    assert r["portfolio_cagr_pct"] is not None


def _tx(kind, qty, price, when, fees=0.0):
    return SimpleNamespace(transaction_type=kind, quantity=qty, price=price, fees=fees, date=when)


def test_cashflows_use_trade_dates_and_restart_at_adjust():
    flows = holding_cashflows(
        [
            _tx("BUY", 10, 100.0, datetime(2024, 1, 1), fees=5.0),
            _tx("SELL", 5, 120.0, datetime(2024, 6, 1)),
            _tx("SPLIT", 2, 0.0, datetime(2024, 7, 1)),
        ],
        shares=10, buy_price=50.0, fallback_date=TODAY,
    )
    assert flows == [(date(2024, 1, 1), -1005.0), (date(2024, 6, 1), 600.0)]

    restated = holding_cashflows(
        [_tx("BUY", 10, 100.0, datetime(2024, 1, 1)), _tx("ADJUST", 4, 90.0, datetime(2025, 1, 1))],
        shares=4, buy_price=90.0, fallback_date=TODAY,
    )
    assert restated == [(date(2025, 1, 1), -360.0)]


def test_ledgerless_holding_is_one_buy_on_fallback_date():
    assert holding_cashflows([], 2, 100.0, date(2025, 3, 5)) == [(date(2025, 3, 5), -200.0)]


def test_ios_benchmark_keys_mirror_pct_values():
    """DB-V2: the shipped iOS BenchmarkData decodes portfolio_cagr/benchmark_cagr/alpha."""
    start = TODAY - timedelta(days=100)
    r = compute_benchmark([(start, -1000.0)], 1150.0, [(start, 100.0), (TODAY, 110.0)], TODAY)

    assert (r["portfolio_cagr"], r["benchmark_cagr"], r["alpha"]) == (15.0, 10.0, 5.0)
    assert r["tracking_error"] is None and r["information_ratio"] is None
    assert r["return_basis"] == "absolute"  # iOS labels it a return, not a CAGR
