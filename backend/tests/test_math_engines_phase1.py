"""Phase 1 regression tests for backend math engines."""

from __future__ import annotations

import builtins
import sys
import types

import pytest

from services.math_engines.calibration_metrics import CalibrationMetricsEngine
from services.math_engines.deterministic_dcf import compute_dcf_valuation
from services.math_engines.monte_carlo_bootstrap import MonteCarloBootstrapEngine
from services.math_engines.piotroski_beneish import (
    compute_beneish_mscore,
    compute_piotroski_fscore,
)
from services.math_engines.portfolio_correlation import (
    compute_correlation_matrix,
    compute_returns,
    optimize_portfolio_weights,
)
from services.math_engines.volume_isolation_forest import detect_volume_anomalies


class _RowsQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._rows


class _RowsSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *_args, **_kwargs):
        return _RowsQuery(self._rows)


def test_dcf_valuation_matches_closed_form_zero_growth_case():
    result = compute_dcf_valuation(
        fcf=100.0,
        growth_rate=0.0,
        terminal_growth=0.0,
        risk_free_rate=0.05,
        equity_risk_premium=0.05,
        beta=1.0,
        years=2,
        debt=0.0,
        equity=100.0,
        shares_outstanding=10.0,
        current_price=80.0,
    )

    assert result["intrinsic_value"] == 1000.0
    assert result["per_share_value"] == 100.0
    assert result["margin_of_safety_pct"] == 25.0
    assert result["rating"] == "UNDERVALUED"
    assert result["wacc"] == 10.0
    assert result["cost_of_equity"] == 10.0
    assert result["risk_free_rate"] == 5.0
    assert result["pv_fcf_sum"] == 173.55
    assert result["pv_terminal_value"] == 826.45
    assert result["terminal_value_pct_of_total"] == 82.6
    assert result["fcf_projections"] == [
        {"year": 1, "fcf": 100.0, "pv_fcf": 90.91, "discount_factor": 1.1},
        {"year": 2, "fcf": 100.0, "pv_fcf": 82.64, "discount_factor": 1.21},
    ]


def test_piotroski_scores_all_nine_positive_signals():
    fundamentals = {
        "net_income": 100.0,
        "total_assets": 1000.0,
        "prev_total_assets": 900.0,
        "operating_cash_flow": 150.0,
        "prev_roa": 0.08,
        "long_term_debt": 100.0,
        "prev_long_term_debt": 150.0,
        "current_assets": 300.0,
        "current_liabilities": 100.0,
        "prev_current_assets": 250.0,
        "prev_current_liabilities": 125.0,
        "shares_outstanding": 100.0,
        "prev_shares_outstanding": 100.0,
        "gross_profit": 500.0,
        "revenue": 1000.0,
        "prev_gross_profit": 390.0,
        "prev_revenue": 800.0,
    }

    result = compute_piotroski_fscore(fundamentals)

    assert result["score"] == 9
    assert result["max_score"] == 9
    assert result["rating"] == "STRONG"
    assert all(result["signals"].values())
    assert result["roa"] == 0.1
    assert result["gross_margin"] == 0.5


def test_beneish_mscore_classifies_low_manipulation_fixture():
    financials = {
        "revenue": 1000.0,
        "prev_revenue": 1000.0,
        "receivables": 100.0,
        "prev_receivables": 100.0,
        "gross_profit": 400.0,
        "prev_gross_profit": 400.0,
        "total_assets": 1000.0,
        "prev_total_assets": 1000.0,
        "current_assets": 300.0,
        "prev_current_assets": 300.0,
        "ppe": 500.0,
        "prev_ppe": 500.0,
        "depreciation": 50.0,
        "prev_depreciation": 50.0,
        "sga": 100.0,
        "prev_sga": 100.0,
        "net_income": 100.0,
        "total_debt": 200.0,
        "prev_total_debt": 200.0,
        "current_liabilities": 100.0,
        "cash": 100.0,
        "securities": 0.0,
    }

    result = compute_beneish_mscore(financials)

    assert result["m_score"] == -2.246
    assert result["manipulator"] is False
    assert result["threshold"] == -2.22
    assert result["interpretation"] == "LOW manipulation risk (likely not manipulating)"
    assert result["variables"] == {
        "DSRI": 1.0,
        "GMI": 1.0,
        "AQI": 1.0,
        "SGI": 1.0,
        "DEPI": 1.0,
        "SGAI": 1.0,
        "Accruals": 0.05,
        "LEVI": 1.0,
    }


def test_calibration_metrics_reports_insufficient_data_with_sample_size():
    rows = [(0.8, True), (0.2, False)]

    result = CalibrationMetricsEngine().compute(
        "TCS",
        {"n_bins": 2},
        session=_RowsSession(rows),
    )

    assert result == {
        "status": "insufficient_data",
        "output": {
            "sample_size": 2,
            "min_required": 30,
            "brier_score": None,
            "ece": None,
        },
    }


def test_calibration_metrics_computes_brier_and_ece_bins():
    rows = [(0.2, False)] * 15 + [(0.8, True)] * 15

    result = CalibrationMetricsEngine().compute(
        "TCS",
        {"n_bins": 2},
        session=_RowsSession(rows),
    )

    assert result["status"] == "ok"
    assert result["output"]["sample_size"] == 30
    assert result["output"]["brier_score"] == 0.04
    assert result["output"]["ece"] == 0.2
    assert result["output"]["interpretation"] == (
        "Poorly calibrated: significant gap between confidence and actual accuracy."
    )
    assert result["output"]["reliability_bins"] == [
        {
            "bin": "0.00-0.50",
            "count": 15,
            "avg_predicted": 0.2,
            "avg_actual": 0.0,
            "gap": 0.2,
        },
        {
            "bin": "0.50-1.00",
            "count": 15,
            "avg_predicted": 0.8,
            "avg_actual": 1.0,
            "gap": 0.2,
        },
    ]


def test_monte_carlo_bootstrap_is_reproducible_and_bounded():
    data = {"analogue_returns": [-0.10, -0.05, 0.02, 0.04, 0.08], "n_bootstrap": 200}
    engine = MonteCarloBootstrapEngine()

    first = engine.compute("TCS", data)
    second = engine.compute("TCS", data)

    assert first == second
    assert first["status"] == "ok"
    output = first["output"]
    assert output["method"] == "bootstrap_resampling"
    assert output["n_analogues"] == 5
    assert output["n_bootstrap"] == 200
    assert output["monte_carlo_cvar_99"] == -0.073
    assert output["expected_return"] == -0.0011
    assert output["median_return"] == -0.0
    assert output["return_std"] == 0.0269
    assert output["prob_positive"] == 0.47
    assert output["confidence_interval_95"] == [-0.0521, 0.0441]


@pytest.mark.parametrize("returns", [[], [0.01, -0.02, 0.03, 0.04]])
def test_monte_carlo_bootstrap_requires_at_least_five_returns(returns):
    result = MonteCarloBootstrapEngine().compute("TCS", {"analogue_returns": returns})

    assert result["status"] == "insufficient_data"
    assert result["output"]["monte_carlo_cvar_99"] is None
    assert result["output"]["sample_size"] == len(returns)


def test_portfolio_returns_and_negative_correlation_are_deterministic():
    prices = {
        "ALPHA": [100.0, 101.0, 103.02, 106.1106, 110.355024, 115.8727752, 122.825141712],
        "BETA": [100.0, 99.0, 97.02, 94.1094, 90.345024, 85.8277728, 80.678106432],
    }

    returns = compute_returns({"ALPHA": [100.0, 110.0, 99.0]})
    result = compute_correlation_matrix(prices)

    assert returns["ALPHA"] == pytest.approx([0.1, -0.1])
    assert result["pairs"] == [
        {"ticker1": "ALPHA", "ticker2": "BETA", "correlation": -1.0}
    ]
    assert result["average_abs_correlation"] == 1.0
    assert result["diversification_score"] == 0.0
    assert result["matrix"]["ALPHA"]["BETA"] == pytest.approx(-1.0)
    assert result["matrix"]["BETA"]["ALPHA"] == pytest.approx(-1.0)
    assert result["advice"] == "Highly correlated holdings — risk concentration warning"


def test_portfolio_optimizer_falls_back_to_equal_weights_without_scipy(monkeypatch):
    real_import = builtins.__import__

    def import_without_scipy_optimize(name, *args, **kwargs):
        if name == "scipy.optimize":
            raise ImportError("scipy unavailable in this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_scipy_optimize)

    prices = {
        "ALPHA": [100.0] * 7,
        "BETA": [100.0] * 7,
    }

    result = optimize_portfolio_weights(prices)

    assert result["weights"] == {"ALPHA": 0.5, "BETA": 0.5}
    assert result["expected_annual_return"] == 0.0
    assert result["expected_annual_volatility"] == 0.0
    assert result["sharpe_ratio"] == 0.0


def test_volume_anomaly_rejects_mismatched_series_lengths():
    with pytest.raises(ValueError, match="prices and volumes must have same length"):
        detect_volume_anomalies([100.0, 101.0], [1000.0])


def test_volume_anomaly_reports_insufficient_data_shape():
    result = detect_volume_anomalies([100.0, 101.0, 102.0], [1000.0, 1100.0, 1200.0])

    assert result == {
        "anomaly_indices": [],
        "anomaly_scores": [],
        "anomaly_mask": [False, False, False],
        "method": "insufficient_data",
        "num_anomalies": 0,
        "description": "Need at least 10 data points",
    }


def test_volume_anomaly_zscore_fallback_classifies_high_volume_stall(monkeypatch):
    real_import = builtins.__import__

    def import_without_sklearn(name, *args, **kwargs):
        if name == "sklearn.ensemble":
            raise ImportError("sklearn unavailable in this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_sklearn)

    prices = [100.0] * 10
    volumes = [100.0, 100.0, 100.0, 100.0, 100.0, 10000.0, 100.0, 100.0, 100.0, 100.0]

    result = detect_volume_anomalies(prices, volumes)

    assert result["method"] == "zscore_fallback"
    assert result["num_anomalies"] == 1
    assert result["anomaly_indices"] == [5]
    assert result["anomaly_mask"][5] is True
    assert result["anomaly_details"] == [
        {
            "index": 5,
            "price": 100.0,
            "volume": 10000,
            "return_pct": 0.0,
            "anomaly_score": pytest.approx(result["anomaly_scores"][5]),
            "type": "HIGH_VOLUME_STALL",
        }
    ]


def test_volume_anomaly_primary_isolation_forest_path_uses_feature_matrix(monkeypatch):
    captured = {}

    class FakeIsolationForest:
        def __init__(self, *, contamination, random_state, n_estimators):
            captured["init"] = {
                "contamination": contamination,
                "random_state": random_state,
                "n_estimators": n_estimators,
            }

        def fit_predict(self, features):
            captured["features_shape"] = features.shape
            captured["row_five"] = features[5].tolist()
            return [1, 1, 1, 1, 1, -1, 1, 1, 1, 1]

        def score_samples(self, features):
            return [-0.1, -0.1, -0.1, -0.1, -0.1, -2.5, -0.1, -0.1, -0.1, -0.1]

    fake_sklearn = types.ModuleType("sklearn")
    fake_ensemble = types.ModuleType("sklearn.ensemble")
    fake_ensemble.IsolationForest = FakeIsolationForest
    monkeypatch.setitem(sys.modules, "sklearn", fake_sklearn)
    monkeypatch.setitem(sys.modules, "sklearn.ensemble", fake_ensemble)

    prices = [100.0] * 10
    volumes = [100.0, 100.0, 100.0, 100.0, 100.0, 10000.0, 100.0, 100.0, 100.0, 100.0]

    result = detect_volume_anomalies(prices, volumes, contamination=0.1)

    assert captured["init"] == {
        "contamination": 0.1,
        "random_state": 42,
        "n_estimators": 100,
    }
    assert captured["features_shape"] == (10, 4)
    assert captured["row_five"] == [0.0, 10000.0, 99.0, 0.0]
    assert result["method"] == "isolation_forest"
    assert result["num_anomalies"] == 1
    assert result["anomaly_indices"] == [5]
    assert result["anomaly_scores"][5] == 2.5
    assert result["anomaly_details"][0]["type"] == "HIGH_VOLUME_STALL"
