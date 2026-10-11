"""Display-only fundamentals (spec 4.7, 11.1; package ml-descriptive). No network."""

from __future__ import annotations

import copy
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from research import fundamentals as fm
from research.contract import Fundamentals

AS_OF = date(2026, 10, 9)
FORBIDDEN = re.compile(r"(^|_)(zone|flag|grade|rating|threshold)s?($|_)")
FETCHED = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
T, P = "2026-03-31", "2025-03-31"


def _payload(**info_overrides: Any) -> dict[str, Any]:
    income = {
        "Total Revenue": (1000.0, 900.0), "Cost Of Revenue": (600.0, 560.0), "Gross Profit": (400.0, 340.0),
        "Operating Income": (150.0, 120.0), "EBIT": (160.0, 125.0), "Net Income": (100.0, 80.0),
        "Selling General And Administration": (90.0, 85.0), "Reconciled Depreciation": (40.0, 38.0),
    }
    balance = {
        "Total Assets": (2000.0, 1900.0), "Current Assets": (800.0, 700.0),
        "Current Liabilities": (400.0, 380.0), "Long Term Debt": (300.0, 320.0), "Total Debt": (350.0, 380.0),
        "Stockholders Equity": (1000.0, 900.0), "Total Liabilities Net Minority Interest": (1000.0, 1000.0),
        "Retained Earnings": (600.0, 520.0), "Working Capital": (400.0, 320.0), "Net PPE": (900.0, 880.0),
        "Accounts Receivable": (150.0, 130.0), "Ordinary Shares Number": (102.0, 100.0),
    }
    cashflow = {"Operating Cash Flow": (130.0, 90.0)}

    def by_period(items: dict[str, tuple[float, float]]) -> dict[str, dict[str, float]]:
        return {T: {k: v[0] for k, v in items.items()}, P: {k: v[1] for k, v in items.items()}}

    info = {"sector": "Industrials", "industry": "Specialty Industrial Machinery", "trailingPE": 24.6,
            "priceToBook": 3.8, "enterpriseToEbitda": 14.2, "trailingAnnualDividendYield": 0.0085,
            "marketCap": 1.5e12}
    info.update(info_overrides)
    return {"symbol": "ABC", "fetched_at": FETCHED.isoformat(), "info": info,
            "income": by_period(income), "balance": by_period(balance), "cashflow": by_period(cashflow)}


def _keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in _keys(v)}
    return set()


def test_full_payload_values_and_contract() -> None:
    block = fm.fundamentals_block(_payload(), as_of=AS_OF, peer_pes=[10, 15, 20, 30, 40])
    Fundamentals.model_validate(block.model_dump())
    assert (block.status, block.reason, block.point_in_time, block.is_financial) == ("ok", None, False, False)
    assert block.fiscal_period_end == date(2026, 3, 31)
    v, q = block.valuation, block.quality
    assert (v.pe_ttm.display, v.pb.display, v.ev_ebitda.display) == ("24.6x", "3.8x", "14.2x")
    assert v.dividend_yield_pct.value == pytest.approx(0.85)
    assert v.pe_sector_pctl.value == pytest.approx(100 * (3 + 0.5) / 6)  # 3 of 5 peers below 24.6
    assert q.roe_pct.value == pytest.approx(10.0)
    assert q.operating_margin_pct.value == pytest.approx(15.0)
    assert q.debt_to_equity.value == pytest.approx(0.35)
    assert q.cfo_to_pat.value == pytest.approx(1.3)
    pio = block.piotroski
    assert {s.id: s.value for s in pio.signals}["no_dilution"] == 0  # shares rose 100 -> 102
    assert (pio.f_score.value, pio.max_possible.value) == (8, 9)
    assert block.altman_z_em.applicable is True
    assert block.altman_z_em.value.value == pytest.approx(6.56 * 0.2 + 3.26 * 0.3 + 6.72 * 0.08 + 1.05 * 1.0)
    dsri = (150 / 1000) / (130 / 900)
    gmi = (340 / 900) / (400 / 1000)
    aqi = (1 - (800 + 900) / 2000) / (1 - (700 + 880) / 1900)
    sgi = 1000 / 900
    depi = (38 / (38 + 880)) / (40 / (40 + 900))
    sgai = (90 / 1000) / (85 / 900)
    tata = (100 - 130) / 2000
    lvgi = ((400 + 300) / 2000) / ((380 + 320) / 1900)
    m = (-4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi + 0.115 * depi - 0.172 * sgai
         + 4.679 * tata - 0.327 * lvgi)
    assert block.beneish_m.value.value == pytest.approx(m)
    assert block.beneish_m.applicable is True


def test_no_grade_zone_or_flag_keys() -> None:
    for payload in (_payload(), _payload(sector="Financial Services", industry="Banks - Regional")):
        keys = _keys(fm.fundamentals_block(payload, as_of=AS_OF).model_dump())
        assert not {k for k in keys if FORBIDDEN.search(k)}
    assert not {k for k in _keys(fm.unavailable_fundamentals().model_dump()) if FORBIDDEN.search(k)}


def test_one_missing_piotroski_input_gives_max_possible_8() -> None:
    payload = _payload()
    del payload["balance"][P]["Current Liabilities"]  # prior-year current ratio unknown
    block = fm.fundamentals_block(payload, as_of=AS_OF)
    signals = {s.id: s.value for s in block.piotroski.signals}
    assert signals["liquidity_up"] is None
    assert block.piotroski.max_possible.value == 8
    assert block.piotroski.f_score.value == 7
    assert block.piotroski.f_score.display == "7"
    assert "grade" not in _keys(block.model_dump())
    assert block.beneish_m.value.status == "unavailable"  # needs the prior year too
    assert block.beneish_m.value.reason == "source_unavailable"


def test_bank_is_not_applicable_for_altman_and_beneish() -> None:
    block = fm.fundamentals_block(_payload(sector="Financial Services", industry="Banks - Regional"), as_of=AS_OF)
    Fundamentals.model_validate(block.model_dump())
    assert block.is_financial is True
    for score in (block.altman_z_em, block.beneish_m):
        assert score.applicable is False
        assert (score.value.status, score.value.reason) == ("unavailable", "not_applicable_financials")
    assert block.valuation.ev_ebitda.reason == "not_applicable_financials"
    assert block.quality.debt_to_equity.reason == "not_applicable_financials"
    assert block.piotroski.max_possible.value == 9  # Piotroski is still shown


@pytest.mark.parametrize("sector,industry,expected", [
    ("Financial Services", "Insurance - Life", True),
    (None, "Credit Services", True),
    ("Technology", "Information Technology Services", False),
    (None, None, None),
])
def test_is_financial(sector: str | None, industry: str | None, expected: bool | None) -> None:
    assert fm.is_financial(sector, industry) is expected


def test_statements_older_than_15_months_are_stale() -> None:
    payload = _payload()
    payload["income"] = {"2025-03-31": payload["income"][T], "2024-03-31": payload["income"][P]}
    payload["balance"] = {"2025-03-31": payload["balance"][T], "2024-03-31": payload["balance"][P]}
    payload["cashflow"] = {"2025-03-31": payload["cashflow"][T], "2024-03-31": payload["cashflow"][P]}
    stale = fm.fundamentals_block(payload, as_of=AS_OF)  # 2025-03-31 is about 18 months before
    Fundamentals.model_validate(stale.model_dump())
    assert (stale.status, stale.reason) == ("stale", "stale_source")
    assert stale.quality.roe_pct.status == "stale" and stale.quality.roe_pct.reason == "stale_source"
    assert stale.altman_z_em.value.status == "stale"
    assert stale.valuation.pe_ttm.status == "ok"  # price-based ratio from the fetch itself
    assert fm.is_stale(date(2025, 7, 8), AS_OF) is True  # cutoff is 2025-07-09
    assert fm.is_stale(date(2025, 7, 9), AS_OF) is False
    assert fm.is_stale(date(2026, 3, 31), AS_OF) is False


def test_sector_pctl_needs_five_peers() -> None:
    assert fm.pe_sector_pctl(20.0, [10, 15, 25, 30]) is None
    assert fm.pe_sector_pctl(20.0, [10, 15, 25, 30, -5, float("nan")]) is None
    assert fm.pe_sector_pctl(20.0, [10, 15, 25, 30, 35]) == pytest.approx(100 * 2.5 / 6)
    block = fm.fundamentals_block(_payload(), as_of=AS_OF, peer_pes=[10, 15, 25, 30])
    assert block.valuation.pe_sector_pctl.status == "unavailable"


def test_non_positive_pe_is_unavailable() -> None:
    block = fm.fundamentals_block(_payload(trailingPE=-12.0), as_of=AS_OF, peer_pes=[10] * 6)
    assert block.valuation.pe_ttm.status == "unavailable"
    assert block.valuation.pe_sector_pctl.status == "unavailable"


def test_missing_or_malformed_payload_is_unavailable() -> None:
    for payload in (None, {"symbol": "ABC"}, {"symbol": "ABC", "fetched_at": FETCHED.isoformat(), "info": {}}):
        block = fm.fundamentals_block(payload, as_of=AS_OF)
        Fundamentals.model_validate(block.model_dump())
        assert (block.status, block.reason) == ("unavailable", "source_unavailable")


def test_payload_helpers() -> None:
    p = _payload()
    assert fm.pe_ttm(p) == 24.6 and fm.sector(p) == "Industrials"
    assert fm.market_cap_cr(p) == pytest.approx(1.5e5)
    assert fm.pe_ttm(None) is None and fm.market_cap_cr(None) is None


# ── Fetch and cache (fake ticker, temporary directory) ──────────────────────


class _FakeTicker:
    calls = 0

    def __init__(self, symbol: str) -> None:
        assert symbol == "ABC.NS"
        _FakeTicker.calls += 1
        cols = [pd.Timestamp(T), pd.Timestamp(P)]
        self.info = {"sector": "Industrials", "trailingPE": 24.6, "longBusinessSummary": "dropped",
                     "priceToBook": float("nan")}
        self.income_stmt = pd.DataFrame({cols[0]: [1000.0, 100.0], cols[1]: [900.0, np.nan]},
                                        index=["Total Revenue", "Net Income"])
        self.balance_sheet = pd.DataFrame({cols[0]: [2000.0], cols[1]: [1900.0]}, index=["Total Assets"])
        self.cashflow = pd.DataFrame()


def _boom(symbol: str) -> Any:
    raise RuntimeError("network must not be used")


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fm, "_THROTTLE", fm._Throttle(0.0))
    _FakeTicker.calls = 0


def test_fetch_writes_cache_and_reuses_it(tmp_path: Path) -> None:
    payload = fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=FETCHED, ticker_factory=_FakeTicker)
    assert payload is not None and _FakeTicker.calls == 1
    path = tmp_path / "raw" / "yfinance" / "fundamentals" / "ABC.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == payload
    assert payload["info"] == {"sector": "Industrials", "trailingPE": 24.6}  # subset, finite only
    assert payload["income"] == {T: {"Total Revenue": 1000.0, "Net Income": 100.0}, P: {"Total Revenue": 900.0}}
    assert payload["cashflow"] == {}
    again = fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=FETCHED + timedelta(days=6), ticker_factory=_boom)
    assert again == payload


def test_expired_cache_respects_budget_and_failures(tmp_path: Path) -> None:
    first = fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=FETCHED, ticker_factory=_FakeTicker)
    later = FETCHED + timedelta(days=8)
    empty = fm.FetchBudget(remaining=0)
    assert fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=later, budget=empty, ticker_factory=_boom) == first
    budget = fm.FetchBudget(remaining=1)
    assert fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=later, budget=budget, ticker_factory=_boom) == first
    assert budget.remaining == 0
    refreshed = fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=later, ticker_factory=_FakeTicker)
    assert refreshed is not None and refreshed["fetched_at"] == later.isoformat()


def test_fetch_failure_without_cache_gives_none(tmp_path: Path) -> None:
    assert fm.fetch_fundamentals("ABC", data_dir=tmp_path, now=FETCHED, ticker_factory=_boom) is None
    assert fm.fundamentals_block(None, as_of=AS_OF).status == "unavailable"


def test_invalid_symbol_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        fm.cache_path("../etc", tmp_path)


def test_frame_round_trip() -> None:
    cols = [pd.Timestamp(P), pd.Timestamp(T)]
    df = pd.DataFrame({cols[0]: [1.0, np.nan], cols[1]: [2.0, 3.0]}, index=["A", "B"])
    back = fm.frame_from_json(fm.frame_to_json(df))
    assert list(back.columns) == [pd.Timestamp(T), pd.Timestamp(P)]
    assert back.at["B", pd.Timestamp(T)] == 3.0 and np.isnan(back.at["B", pd.Timestamp(P)])


def test_payload_is_not_mutated() -> None:
    payload = _payload()
    before = copy.deepcopy(payload)
    fm.fundamentals_block(payload, as_of=AS_OF)
    assert payload == before
