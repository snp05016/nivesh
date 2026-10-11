"""FAKE-18: holdings the stress test could not price are flagged, never passed off as measured."""
from types import SimpleNamespace

import pytest

from services import stress_test
from services.math_engines.vasicek import MacroBetasResponse

HOLDING = SimpleNamespace(ticker="ABC", company_name="Abc Industries", shares=10, buy_price=100)


@pytest.fixture
def edges(monkeypatch):
    monkeypatch.setattr(stress_test, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(stress_test, "_yf_fetch_info", lambda sym: {"beta": 1.0, "averageVolume": 1e6})
    monkeypatch.setattr(stress_test, "get_adjusted_macro_betas", lambda sym, sector: MacroBetasResponse(
        market=1.0, midcap=0.0, smallcap=0.0, oil=0.0, rates=0.0,
        fx=0.0, inflation=0.0, fii_flow=0.0, dii_flow=0.0,
    ))


def _raise(*_a, **_k):
    raise TimeoutError("yfinance timeout")


def test_price_failure_is_cost_basis(edges, monkeypatch):
    monkeypatch.setattr(stress_test, "_yf_price", _raise)

    row = stress_test.enrich_holdings([HOLDING])[0]

    assert row["price"] == 100
    assert row["price_source"] == "cost_basis"


def test_enrichment_failure_fallback_is_flagged(edges, monkeypatch):
    monkeypatch.setattr(stress_test, "_yf_price", lambda sym: (120.0, 118.0))
    monkeypatch.setattr(stress_test, "get_adjusted_macro_betas", _raise)

    row = stress_test.enrich_holdings([HOLDING])[0]

    assert row["price"] == 100  # _build_fallback: cost basis and default inputs
    assert row["price_source"] == "cost_basis"
    assert row["adv_source"] == "default"
    assert row["betas"]["market_beta_source"] == "default"


def test_live_price_is_not_estimated(edges, monkeypatch):
    monkeypatch.setattr(stress_test, "_yf_price", lambda sym: (120.0, 118.0))

    row = stress_test.enrich_holdings([HOLDING])[0]

    assert row["price"] == 120.0
    assert row["price_source"] == "live"
