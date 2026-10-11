"""TEST-12: the app's own services.piotroski runs in tests (conftest no longer stubs it).

Imported the normal way, so a MagicMock module in sys.modules would fail these
asserts. yfinance is the conftest mock; only Ticker's statements are faked.
"""
from types import SimpleNamespace

import pandas as pd
import pytest

import services.piotroski as piotroski


def _frame(rows: dict) -> pd.DataFrame:
    # yfinance layout: rows are line items, columns are fiscal years (latest first).
    return pd.DataFrame.from_dict(rows, orient="index", columns=["2025", "2024"])


def _fake_ticker(monkeypatch, fi: dict, bs: dict, cf: dict) -> None:
    statements = SimpleNamespace(financials=_frame(fi), balance_sheet=_frame(bs), cashflow=_frame(cf))
    monkeypatch.setattr(piotroski.yf, "Ticker", lambda _symbol: statements)


def test_module_is_real():
    assert piotroski.compute_piotroski.__module__ == "services.piotroski"


def test_known_fundamentals_score(monkeypatch):
    _fake_ticker(
        monkeypatch,
        fi={
            "Net Income": [100.0, 80.0],
            "Gross Profit": [250.0, 300.0],      # margin 0.25 < 0.273: FAIL
            "Total Revenue": [1000.0, 1100.0],   # turnover 1.0 < 1.1: FAIL
        },
        bs={
            "Total Assets": [1000.0, 1000.0],
            "Long Term Debt": [100.0, 200.0],
            "Current Assets": [500.0, 400.0],
            "Current Liabilities": [250.0, 250.0],
            "Ordinary Shares Number": [10.0, 12.0],
        },
        cf={"Operating Cash Flow": [150.0, 120.0]},
    )

    result = piotroski.compute_piotroski("TESTCO")

    assert result["max_possible"] == 9
    assert result["f_score"] == 7
    assert result["grade"] == "STRONG"  # 7/9 is the STRONG floor
    assert result["confidence"] == "HIGH"
    assert result["checks"]["gross_margin_improving"] == "FAIL"
    assert result["checks"]["asset_turnover_improving"] == "FAIL"
    assert sum(v == "PASS" for v in result["checks"].values()) == 7


def test_empty_statements_degrade(monkeypatch):
    statements = SimpleNamespace(financials=pd.DataFrame(), balance_sheet=pd.DataFrame(), cashflow=pd.DataFrame())
    monkeypatch.setattr(piotroski.yf, "Ticker", lambda _symbol: statements)

    result = piotroski.compute_piotroski("NEWLIST")

    assert result["f_score"] is None
    assert result["grade"] == "INSUFFICIENT_DATA"
    assert result["checks"] == {}


@pytest.mark.parametrize("module", ["services.disk_cache", "services.nse_data_provider", "services.options_scraper"])
def test_app_modules_not_stubbed(module):
    import importlib
    import types

    assert type(importlib.import_module(module)) is types.ModuleType
