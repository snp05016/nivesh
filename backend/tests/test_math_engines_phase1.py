"""Phase 1 regression tests for backend math engines."""

from __future__ import annotations

import pytest

from services.math_engines.calibration_metrics import CalibrationMetricsEngine
from services.math_engines.monte_carlo_bootstrap import MonteCarloBootstrapEngine


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
