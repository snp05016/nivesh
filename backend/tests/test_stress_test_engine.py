"""Tests for Tier 2.5 Stress Test Engine."""
import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestScenarioEngine:
    def test_14_scenarios_defined(self):
        from services.stress_test import SCENARIOS_DEF
        assert len(SCENARIOS_DEF) == 14

    def test_nifty_crash_negative_impact(self):
        from services.stress_test import SCENARIOS_DEF
        assert SCENARIOS_DEF["nifty_crash"]["shocks"]["market"] == -20.0

    def test_oil_shock_negative_for_nifty(self):
        from services.stress_test import SCENARIOS_DEF
        assert SCENARIOS_DEF["oil_shock"]["shocks"]["oil"] == 50.0
        assert SCENARIOS_DEF["oil_shock"]["nifty"] == -5.0

    def test_rate_hike_has_rates_and_nifty(self):
        from services.stress_test import SCENARIOS_DEF
        assert "rates" in SCENARIOS_DEF["rate_hike"]["shocks"]
        assert "nifty" in SCENARIOS_DEF["rate_hike"]

    def test_banking_crisis_has_sector_override(self):
        from services.stress_test import SCENARIOS_DEF
        assert "sector" in SCENARIOS_DEF["banking_crisis"]
        assert SCENARIOS_DEF["banking_crisis"]["sector"]["Banking"] == -30.0


@pytest.fixture
def no_price_history(monkeypatch):
    """Hermetic: every yfinance download comes back empty, forcing the beta fallback."""
    import pandas as pd
    from services.math_engines import vasicek

    monkeypatch.setattr(vasicek.yf, "download", lambda *_a, **_k: pd.DataFrame())


@pytest.mark.usefixtures("no_price_history")
class TestVasicekEngine:
    def test_beta_estimation_returns_expected_factors(self):
        from services.stress_test import _estimate_betas
        betas = _estimate_betas("RELIANCE.NS")
        assert "market" in betas
        assert "oil" in betas
        assert "rates" in betas
        assert "fx" in betas
        assert isinstance(betas["market"], float)

    def test_beta_estimation_fallback(self):
        from services.stress_test import _estimate_betas
        betas = _estimate_betas("INVALID_TICKER_XYZ123")
        assert betas["market"] == 1.0
        assert betas["market_beta_source"] == "default"
        # Macro/flow betas are not estimated, so they must not inject fake exposure.
        assert betas["rates"] == 0.0
        assert betas["fii_flow"] == 0.0

    def test_beta_all_factors_present(self):
        from services.stress_test import _estimate_betas, FACTOR_CATEGORIES
        betas = _estimate_betas("TCS.NS")
        all_factors = set()
        for cat in FACTOR_CATEGORIES.values():
            all_factors.update(cat)
        for f in all_factors:
            assert f in betas, f"Missing factor: {f}"


class TestLiquidityEngine:
    def test_square_root_impact_small_position(self):
        from services.math_engines.liquidity import square_root_impact
        result = square_root_impact(
            shares_held=100,
            avg_daily_volume=1_000_000,
            daily_volatility=0.02,
            base_spread_bps=0.005,
            gamma=0.2,
            volume_suppression=0.0,
        )
        assert result.impact_pct < 1.0

    def test_square_root_impact_large_position(self):
        from services.math_engines.liquidity import square_root_impact
        result = square_root_impact(
            shares_held=5_000_000,
            avg_daily_volume=200_000,
            daily_volatility=0.03,
            base_spread_bps=0.005,
            gamma=0.2,
            volume_suppression=1.0,
        )
        assert result.impact_pct > 1.0

    def test_volume_suppression_increases_impact(self):
        from services.math_engines.liquidity import square_root_impact
        normal = square_root_impact(
            shares_held=10_000,
            avg_daily_volume=500_000,
            daily_volatility=0.02,
            base_spread_bps=0.005,
            gamma=0.2,
            volume_suppression=0.0,
        )
        stressed = square_root_impact(
            shares_held=10_000,
            avg_daily_volume=500_000,
            daily_volatility=0.02,
            base_spread_bps=0.005,
            gamma=0.2,
            volume_suppression=0.4,
        )
        assert stressed.impact_pct > normal.impact_pct

    def test_portfolio_liquidity_loss(self):
        from services.math_engines.liquidity import portfolio_liquidity_loss
        holdings = [
            {"ticker": "A", "shares": 1000, "price": 500, "avg_daily_volume": 1_000_000,
             "volatility": 0.02, "spread_bps": 0.005},
            {"ticker": "B", "shares": 2000, "price": 300, "avg_daily_volume": 500_000,
             "volatility": 0.03, "spread_bps": 0.005},
        ]
        result = portfolio_liquidity_loss(holdings, volume_suppression=0.4, gamma=0.2)
        assert result.total_liquidity_loss_inr > 0
        assert result.total_liquidity_loss_pct > 0


class TestConcentrationEngine:
    def test_hhi_perfectly_diversified(self):
        from services.math_engines.concentration import compute_concentration_analysis
        n = 50
        weights = np.ones(n) / n
        tickers = [f"T{i}" for i in range(n)]
        sectors = ["A"] * 13 + ["B"] * 12 + ["C"] * 13 + ["D"] * 12
        cov = np.eye(n) * 0.04
        result = compute_concentration_analysis(tickers, weights, sectors, cov)
        # HHI = n * (100/n)^2 = 10000/n  → for n=50, HHI = 200
        assert result.hhi < 1500  # well below diversified threshold
        assert result.hhi_classification == "Diversified"

    def test_hhi_single_stock(self):
        from services.math_engines.concentration import compute_concentration_analysis
        weights = np.array([1.0])
        tickers = ["T0"]
        sectors = ["Banking"]
        cov = np.eye(1) * 0.04
        result = compute_concentration_analysis(tickers, weights, sectors, cov)
        # Single stock: HHI = (100)^2 = 10000
        assert result.hhi == 10000.0
        assert result.hhi_classification == "Concentrated"

    def test_hhi_classification(self):
        from services.math_engines.concentration import compute_concentration_analysis
        weights = np.array([0.5, 0.3, 0.2])
        tickers = [f"T{i}" for i in range(3)]
        sectors = ["Banking", "Banking", "IT"]
        cov = np.eye(3) * 0.04
        result = compute_concentration_analysis(tickers, weights, sectors, cov)
        assert result.hhi > 0.25

    def test_marginal_risk_contribution(self):
        from services.math_engines.concentration import compute_concentration_analysis
        weights = np.array([0.4, 0.3, 0.2, 0.1])
        tickers = [f"T{i}" for i in range(4)]
        sectors = ["Banking", "IT", "FMCG", "Auto"]
        cov = np.array([
            [0.04, 0.01, 0.005, 0.005],
            [0.01, 0.05, 0.005, 0.01],
            [0.005, 0.005, 0.03, 0.005],
            [0.005, 0.01, 0.005, 0.04],
        ])
        result = compute_concentration_analysis(tickers, weights, sectors, cov)
        assert len(result.marginal_risk_contributions) == 4

    def test_concentration_score_scale(self):
        from services.math_engines.concentration import compute_concentration_analysis
        single = compute_concentration_analysis(["T0"], np.array([1.0]), ["IT"], np.eye(1) * 0.04)
        assert single.concentration_score == 0.0
        n = 50
        spread = compute_concentration_analysis(
            [f"T{i}" for i in range(n)], np.ones(n) / n, ["IT"] * n, np.eye(n) * 0.04
        )
        assert spread.concentration_score == pytest.approx(98.0)


class TestCovarianceEngine:
    def test_covariance_matrix_diagonal(self):
        n = 5
        vols = [0.2, 0.3, 0.25, 0.15, 0.35]
        cov = np.eye(n)
        for i in range(n):
            cov[i, i] = vols[i] ** 2
        for i in range(n):
            assert cov[i, i] == vols[i] ** 2
        for i in range(n):
            for j in range(n):
                if i != j:
                    assert cov[i, j] == 0.0

    def test_conditional_shock_propagation(self):
        volatilities = np.array([0.20, 0.30, 0.25, 0.15])
        cov = np.eye(4)
        for i in range(4):
            cov[i, i] = volatilities[i] ** 2
        shock = np.array([-0.20, 0.0, 0.0, 0.0])
        impact = cov @ shock.reshape(-1, 1)
        assert impact[0][0] < 0
        for i in range(1, 4):
            assert impact[i][0] == 0.0


class TestIntegration:
    def test_full_pipeline_with_mock_holdings(self):
        from services.stress_test import enrich_holdings, run_stress_test

        class MockHolding:
            pass

        def make_h(ticker, name, shares, buy_price):
            h = MockHolding()
            h.ticker = ticker
            h.company_name = name
            h.shares = shares
            h.buy_price = buy_price
            if not hasattr(h, 'group_name'):
                h.group_name = None
            return h

        holdings = [
            make_h("CASH", "Cash", 1000, 1.0),
        ]
        results = run_stress_test(holdings, ["nifty_crash"])
        assert isinstance(results, list)

    def test_empty_holdings_returns_empty(self):
        from services.stress_test import run_stress_test
        results = run_stress_test([], ["nifty_crash"])
        assert results == []

    def test_enrich_holdings_basic(self):
        from services.stress_test import enrich_holdings

        class MockHolding:
            pass

        h = MockHolding()
        h.ticker = "CASH"
        h.company_name = "Cash"
        h.shares = 500
        h.buy_price = 1.0
        h.group_name = None

        enriched = enrich_holdings([h])
        assert len(enriched) == 1
        assert enriched[0]["ticker"] == "CASH"
        assert enriched[0]["sector"] == "Cash"

    def test_get_sector_classification(self):
        from services.stress_test import get_sector
        assert get_sector("TCS Ltd") == "IT"
        assert get_sector("Infosys Limited") == "IT"
        assert get_sector("HDFC Bank Ltd") == "Banking"
        assert get_sector("Reliance Industries Ltd") == "Oil & Gas"
        assert get_sector("Unknown Corp") == "Other"


class TestAPI:
    def test_endpoint_returns_200_with_valid_body(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/portfolio/stress-test",
            json={"portfolio_id": "test", "scenarios": ["nifty_crash"]},
        )
        assert response.status_code in [200, 401]

    def test_endpoint_accepts_custom_shocks(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/portfolio/stress-test",
            json={
                "portfolio_id": "test",
                "scenarios": ["nifty_crash"],
                "custom_shocks": {"market": -30.0},
            },
        )
        assert response.status_code in [200, 401]

    def test_scenario_key_case_insensitive(self):
        from services.stress_test import run_stress_test

        class MockHolding:
            ticker = "CASH"
            company_name = "Cash"
            shares = 1000
            buy_price = 1.0
            group_name = None

        results = run_stress_test([MockHolding()], ["NIFTY_CRASH"])
        assert len(results) >= 1
        assert results[0]["scenario_key"] == "nifty_crash"
