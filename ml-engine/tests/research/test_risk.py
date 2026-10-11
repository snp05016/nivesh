"""Risk metrics and historical return ranges (spec 4.5, 4.6, 11.1; package ml-descriptive)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research import risk
from research.contract import ReturnRange, Risk

SEED = 20261010


def _panel(px: np.ndarray, start: str = "2018-01-01") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=px.size)
    return pd.DataFrame({"date": dates, "entity_id": "E1", "px_idx": px})


def _path(n: int, vol: float = 0.015, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100.0 * np.cumprod(1.0 + rng.normal(0.0003, vol, n))


# ── VaR, CVaR, backtests ────────────────────────────────────────────────────


def test_cvar99_standard_normal() -> None:
    z = np.random.default_rng(SEED).standard_normal(1_000_000)
    var, cvar = risk.hist_var_cvar(z, 0.99)
    assert cvar == pytest.approx(-2.665, abs=0.01)
    assert var == pytest.approx(-2.326, abs=0.01)


def test_kupiec_known_value() -> None:
    # 10 exceptions in 250 days at 99%: LR = -2 ln[0.99^240 0.01^10] + 2 ln[0.96^240 0.04^10].
    lr, p = risk.kupiec_pof(10, 250, 0.01)
    assert lr == pytest.approx(12.955, abs=0.01)
    assert p == pytest.approx(0.000319, abs=0.00002)
    lr0, p0 = risk.kupiec_pof(0, 250, 0.01)
    assert lr0 == pytest.approx(-2 * 250 * np.log(0.99)) and 0.0 < p0 < 1.0


def test_christoffersen_detects_clustering() -> None:
    spread = np.zeros(250, dtype=int)
    spread[::25] = 1
    clustered = np.zeros(250, dtype=int)
    clustered[100:110] = 1
    assert risk.christoffersen_ind(spread)[1] > 0.05
    assert risk.christoffersen_ind(clustered)[1] < 0.001
    assert risk.christoffersen_ind(np.zeros(250, dtype=int)) == (0.0, 1.0)


def test_var_rows_on_iid_series_are_green_and_ordered() -> None:
    px = _path(1300)
    status, rows = risk.var_block(risk.simple_returns(px), None)
    assert status == "ok" and rows
    keys = [(r.level, r.method) for r in rows]
    assert keys == sorted(keys, key=lambda k: (k[0], ["historical_500d", "fhs_ewma"].index(k[1])))
    for row in rows:
        assert row.var_pct.value is not None and row.var_pct.value < 0
        assert row.cvar_pct.value is not None and row.cvar_pct.value <= row.var_pct.value
        assert row.backtest.window_days == 250
        assert row.backtest.expected == pytest.approx(250 * (1 - row.level))
        assert row.var_pct.id == f"risk.var_1d.{round(row.level * 100)}.{row.method}.var_pct"


def test_red_zone_series_gives_backtest_failed() -> None:
    rng = np.random.default_rng(SEED)
    r = rng.normal(0.0, 0.002, 1300)
    for start in range(1060, 1300, 20):  # paired -10% days through the backtest window
        r[start:start + 2] = -0.10
    px = 100.0 * np.cumprod(1.0 + r)
    status, rows = risk.var_block(risk.simple_returns(px), None)
    assert (status, rows) == ("backtest_failed", [])
    block = risk.risk_block(_panel(px), None, None)
    assert block.var_status == "backtest_failed" and block.var_1d == []


def test_var_unavailable_without_750_returns() -> None:
    status, rows = risk.var_block(risk.simple_returns(_path(700)), None)
    assert (status, rows) == ("unavailable", [])


# ── Beta ────────────────────────────────────────────────────────────────────


def test_dimson_recovers_lagged_beta() -> None:
    rng = np.random.default_rng(SEED)
    n = 400
    m = rng.normal(0.0, 0.01, n)
    r = 0.6 * m + np.concatenate([[0.0], 0.5 * m[:-1]]) + rng.normal(0.0, 0.003, n)
    dates = pd.bdate_range("2024-01-01", periods=n)
    panel = pd.DataFrame({"date": dates, "px_idx": 100.0 * np.cumprod(1.0 + r)})
    index = pd.Series(20000.0 * np.cumprod(1.0 + m), index=dates)
    beta = risk.risk_block(panel, index, None).beta
    assert beta.raw.value is not None and beta.raw.value == pytest.approx(1.1, abs=0.05)
    assert beta.se.value is not None and 0.0 < beta.se.value < 0.1
    assert beta.blume_adjusted.value == pytest.approx(0.67 * beta.raw.value + 0.33)
    assert beta.raw.method == "dimson_lag1_daily_252"


def test_beta_unavailable_without_index_or_pairs() -> None:
    panel = _panel(_path(400))
    no_index = risk.risk_block(panel, None, None).beta
    assert no_index.raw.status == "unavailable" and no_index.raw.reason == "source_unavailable"
    short = _panel(_path(150))
    index = pd.Series(np.linspace(100, 110, 150), index=short["date"])
    few = risk.risk_block(short, index, None).beta
    assert few.raw.reason == "insufficient_history"


# ── Drawdowns ───────────────────────────────────────────────────────────────


def test_max_drawdown_known_path() -> None:
    assert risk.max_drawdown_pct(np.array([100, 120, 90, 110, 130, 104.0])) == pytest.approx(-25.0)
    assert risk.max_drawdown_pct(np.array([100.0, np.nan, 50.0, 100.0])) == pytest.approx(-50.0)
    assert risk.max_drawdown_pct(np.array([np.nan, 100.0])) is None


def test_drawdown_block_known_path() -> None:
    # 300 sessions: rise 100 -> 200 (peak at row 199), fall to 150 at row 249, recover to 180.
    px = np.concatenate([np.linspace(100, 200, 200), np.linspace(199, 150, 50), np.linspace(151, 180, 50)])
    block = risk.risk_block(_panel(px), None, None)
    dd = block.drawdown
    assert dd.max_1y_pct.value == pytest.approx(-25.0)
    assert dd.current_pct.value == pytest.approx(-10.0)
    assert dd.days_since_peak.value == 100
    assert dd.max_3y_pct.status == "unavailable" and dd.max_3y_pct.reason == "insufficient_history"
    assert dd.ulcer_1y.value is not None and dd.ulcer_1y.value > 0
    pts = block.drawdown_series.points
    assert 0 < len(pts) <= 160 and pts[-1][1] == pytest.approx(-10.0)
    assert all(v <= 0 for _, v in pts)


# ── Historical return ranges ────────────────────────────────────────────────


def test_range_equals_numpy_percentiles() -> None:
    px = _path(1000)
    for h in (21, 63):
        rr = risk.return_range_block(px, h)
        s = np.arange(1000 - 756, 1000)
        rets = px[s] / px[s - h] - 1.0
        assert rr.window_sessions == 756
        assert rr.low_pct.value == pytest.approx(np.percentile(rets, 10) * 100)
        assert rr.high_pct.value == pytest.approx(np.percentile(rets, 90) * 100)
        assert rr.method == "empirical_rolling_756d"
        assert rr.text == (f"Over the last 3 years, 8 in 10 of this stock's {h}-trading-day returns fell "
                           f"between {rr.low_pct.display} and {rr.high_pct.display}. This is not a forecast.")


def test_range_400_sessions_text() -> None:
    rr = risk.return_range_block(_path(400), 21)
    assert rr.window_sessions == 400
    assert rr.text is not None and rr.text.startswith("Over the last 19 months, 8 in 10 of this stock's 21-")


def test_range_insufficient_history() -> None:
    rr = risk.return_range_block(_path(200), 63)
    assert rr.low_pct.status == "unavailable" and rr.high_pct.reason == "insufficient_history"
    assert rr.text is None and rr.window_sessions == 200


def test_range_as_of_from_dated_series() -> None:
    panel = _panel(_path(300))
    rr = risk.return_range_block(pd.Series(panel["px_idx"].to_numpy(), index=panel["date"]), 21)
    assert rr.low_pct.as_of == panel["date"].iloc[-1].date()


# ── Assembly ────────────────────────────────────────────────────────────────


def test_risk_block_validates_and_volatility() -> None:
    px = _path(1300, vol=0.02)
    panel = _panel(px).sample(frac=1.0, random_state=1)  # unsorted input is sorted by date
    index = pd.Series(_path(1300, vol=0.01, seed=7), index=pd.bdate_range("2018-01-01", periods=1300))
    universe = np.linspace(10, 60, 200)
    block = risk.risk_block(panel, index, universe)
    Risk.model_validate(block.model_dump())
    for rr in block.return_ranges:
        ReturnRange.model_validate(rr.model_dump())
    assert block.vol_252d_ann_pct.value == pytest.approx(0.02 * np.sqrt(252) * 100, rel=0.15)
    assert block.vol_ewma_ann_pct.value is not None and block.vol_ewma_ann_pct.method == "ewma_0.94"
    vol = block.vol_252d_ann_pct.value
    assert vol is not None
    expected_pctl = 100 * np.mean(universe < vol)
    assert block.vol_pctl.value == pytest.approx(expected_pctl)
    assert [r.horizon_days for r in block.return_ranges] == [21, 63]
    assert block.drawdown.max_5y_pct.status == "ok"
    assert block.drawdown.current_pct.value >= block.drawdown.max_5y_pct.value  # type: ignore[operator]


def test_risk_block_short_history_is_unavailable_not_error() -> None:
    block = risk.risk_block(_panel(_path(40)), None, [20.0, 30.0])
    Risk.model_validate(block.model_dump())
    assert block.var_status == "unavailable" and block.var_1d == []
    assert block.vol_252d_ann_pct.status == "unavailable"
    assert block.vol_pctl.reason == "insufficient_history"
    assert block.vol_ewma_ann_pct.status == "unavailable"


def test_nan_close_drops_adjacent_returns() -> None:
    r = risk.simple_returns(np.array([100.0, 101.0, np.nan, 103.0, 104.0]))
    assert np.isnan(r[[0, 2, 3]]).all() and r[1] == pytest.approx(0.01) and r[4] == pytest.approx(1 / 103)


def test_ewma_variance_recursion() -> None:
    r = np.array([0.01, -0.02, 0.015])
    s2 = risk.ewma_variance(r, 0.94)
    seed = np.mean(r**2)
    assert s2[0] == pytest.approx(seed)
    assert s2[1] == pytest.approx(0.94 * seed + 0.06 * 0.01**2)
    assert s2[3] == pytest.approx(0.94 * s2[2] + 0.06 * 0.015**2)
