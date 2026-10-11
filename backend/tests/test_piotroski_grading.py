"""MATH-18: Piotroski grade is availability-normalised and NaN rows count as missing."""
import importlib.util
import pathlib
from types import SimpleNamespace

import pandas as pd
import pytest

# conftest replaces sys.modules["services.piotroski"] with a MagicMock for the API
# tests, so load the real module straight from its file. Its `import yfinance` still
# resolves to the conftest yfinance mock, so patching piotroski.yf.Ticker stays hermetic.
_spec = importlib.util.spec_from_file_location(
    "_piotroski_real", pathlib.Path(__file__).resolve().parents[1] / "services" / "piotroski.py"
)
piotroski = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(piotroski)

NAN = float("nan")


def _frame(rows: dict) -> pd.DataFrame:
    # yfinance layout: rows are line items, columns are fiscal years (latest first).
    return pd.DataFrame.from_dict(rows, orient="index", columns=["2025", "2024"])


@pytest.fixture
def fake_ticker(monkeypatch):
    """Bank-like statements: no Gross Profit, Current Assets/Liabilities or Revenue rows."""
    data = {
        "fi": {"Net Income": [100.0, 80.0]},
        "bs": {
            "Total Assets": [1000.0, 1000.0],
            "Long Term Debt": [100.0, 200.0],
            "Ordinary Shares Number": [10.0, 10.0],
        },
        "cf": {"Operating Cash Flow": [150.0, 120.0]},
    }

    def ticker(_symbol):
        return SimpleNamespace(
            financials=_frame(data["fi"]),
            balance_sheet=_frame(data["bs"]),
            cashflow=_frame(data["cf"]),
        )

    monkeypatch.setattr(piotroski.yf, "Ticker", ticker)
    return data


def test_six_of_six_available_all_passing_grades_strong(fake_ticker):
    result = piotroski.compute_piotroski("HDFCBANK")
    assert result["max_possible"] == 6
    assert result["f_score"] == 6
    assert set(result["checks"].values()) == {"PASS"}
    assert result["grade"] == "STRONG"  # was NEUTRAL: absolute >=7 unreachable with 6 checks


def test_nan_net_income_is_missing_not_failed(fake_ticker):
    fake_ticker["fi"]["Net Income"] = [NAN, 80.0]
    result = piotroski.compute_piotroski("NEWCO")
    for key in ("roa_positive", "roa_improving", "accruals_low"):
        assert key not in result["checks"]
    assert result["max_possible"] == 3
    assert result["f_score"] == 3
    # 3/3 passing used to grade WEAK under the absolute 7/4 thresholds.
    assert result["grade"] == "STRONG"


def test_debt_free_both_years_passes_leverage(fake_ticker):
    fake_ticker["bs"]["Long Term Debt"] = [0.0, 0.0]
    result = piotroski.compute_piotroski("DEBTFREE")
    assert result["checks"]["leverage_decreasing"] == "PASS"


def test_partial_pass_ratio_grades_neutral_and_weak(fake_ticker):
    # Net income falls and debt rises: roa_improving and leverage fail -> 4/6 = 0.67.
    fake_ticker["fi"]["Net Income"] = [100.0, 120.0]
    fake_ticker["bs"]["Long Term Debt"] = [300.0, 200.0]
    assert piotroski.compute_piotroski("MID")["grade"] == "NEUTRAL"

    # Loss-making, cash-burning, levering up and diluting: 1/6 passes -> WEAK.
    fake_ticker["fi"]["Net Income"] = [-100.0, 120.0]
    fake_ticker["cf"]["Operating Cash Flow"] = [-50.0, 120.0]
    fake_ticker["bs"]["Ordinary Shares Number"] = [20.0, 10.0]
    result = piotroski.compute_piotroski("BAD")
    assert result["max_possible"] == 6
    assert result["grade"] == "WEAK"
