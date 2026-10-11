"""Outcome scoring os-2 (spec 8.4) and live metrics with the A1 kill-switch (spec 8.5; package ml-assembly-pipeline).

Synthetic panels and ledgers only; no network, no local CSV.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from research.contract import LiveMetricsRequest, OutcomeRequestItem
from research.live import live_metrics, psi
from research.marketdata import store, universe
from research.outcomes import score_outcomes
from research.report import as_timestamp

N_NAMES = 45
N_SESSIONS = 120


def _panel(seed: int = 7) -> pd.DataFrame:
    """45 survivors on a business-day calendar; px_idx = close (dev-style, already adjusted)."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-01-01", periods=N_SESSIONS)
    frames = []
    for i in range(N_NAMES):
        close = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, N_SESSIONS)))
        frames.append(pd.DataFrame({
            "date": days, "entity_id": f"S{i:02d}", "isin": f"S{i:02d}", "symbol": f"S{i:02d}",
            "open": close, "high": close, "low": close, "close": close, "prev_close": np.r_[np.nan, close[:-1]],
            "volume": 1e5, "turnover_inr": close * 1e5, "trades": np.nan, "px_idx": close / close[0],
            "event": "", "quality_flags": "", "source": "local_csv",
        }))
    return pd.concat(frames, ignore_index=True).sort_values(["entity_id", "date"]).reset_index(drop=True)


def _item(pid: int, panel: pd.DataFrame, sym: str, k: int, h: int = 21, **over: Any) -> OutcomeRequestItem:
    t = as_timestamp(store.sessions(panel)[k])
    close = float(panel.loc[(panel["symbol"] == sym) & (panel["date"] == t), "close"].iloc[0])
    row = {"prediction_id": pid, "isin": None, "symbol": sym, "as_of": t.date(), "horizon_days": h,
           "entry_close": close}
    row.update(over)
    return OutcomeRequestItem.model_validate(row)


def _score(items: list[OutcomeRequestItem], panel: pd.DataFrame, index: pd.Series | None = None,
           tmp: Path | None = None) -> list[Any]:
    return score_outcomes(items, panel, universe.membership(panel), index, data_dir=tmp)


# ── outcomes ────────────────────────────────────────────────────────────────


def test_matured_return_excess_and_index(tmp_path: Path) -> None:
    panel = _panel()
    cal = store.sessions(panel)
    index = pd.Series(np.linspace(100.0, 130.0, N_SESSIONS), index=cal)
    [res] = _score([_item(1, panel, "S03", 10)], panel, index, tmp_path)
    px = panel.loc[panel["symbol"] == "S03"].set_index("date")["px_idx"]
    expected = (px[cal[31]] / px[cal[10]] - 1.0) * 100.0
    assert res.outcome_status == "matured" and res.void_reason is None and res.stale_exit is False
    assert res.realized_return_pct == pytest.approx(expected)
    rets = [float(panel.loc[(panel["symbol"] == s) & (panel["date"] == cal[31]), "px_idx"].iloc[0]
                  / panel.loc[(panel["symbol"] == s) & (panel["date"] == cal[10]), "px_idx"].iloc[0] - 1.0)
            for s in sorted(panel["symbol"].unique())]
    median = float(np.median(rets))
    assert res.realized_excess_pp == pytest.approx(expected - median * 100.0)
    assert res.realized_top_half == (expected / 100.0 > median)
    assert res.nifty50_return_pct == pytest.approx((index[cal[31]] / index[cal[10]] - 1.0) * 100.0)
    assert res.scorer_version == "os-2"


def test_entry_price_mismatch_voids(tmp_path: Path) -> None:
    panel = _panel()
    good = _item(1, panel, "S01", 5)
    bad = _item(2, panel, "S01", 5, entry_close=good.entry_close * 1.001)
    near = _item(3, panel, "S01", 5, entry_close=good.entry_close * 1.00005)  # within 0.01%
    res = _score([good, bad, near], panel, tmp=tmp_path)
    assert [r.outcome_status for r in res] == ["matured", "void", "matured"]
    assert res[1].void_reason == "entry_price_mismatch" and res[1].realized_return_pct is None


def test_suspect_entry_voids(tmp_path: Path) -> None:
    panel = _panel()
    item = _item(1, panel, "S02", 8)
    hit = (panel["symbol"] == "S02") & (panel["date"] == pd.Timestamp(item.as_of))
    panel.loc[hit, "quality_flags"] = "suspect"
    panel.loc[hit, "px_idx"] = np.nan
    [res] = _score([item], panel, tmp=tmp_path)
    assert res.outcome_status == "void" and res.void_reason == "suspect_price"


def test_delisting_matures_with_stale_exit(tmp_path: Path) -> None:
    panel = _panel()
    cal = store.sessions(panel)
    gone = (panel["symbol"] == "S04") & (panel["date"] > cal[15])  # last trade at session 15
    panel = panel.loc[~gone].reset_index(drop=True)
    [res] = _score([_item(1, panel, "S04", 10)], panel, tmp=tmp_path)
    px = panel.loc[panel["symbol"] == "S04"].set_index("date")["px_idx"]
    assert res.outcome_status == "matured" and res.stale_exit is True
    assert res.realized_return_pct == pytest.approx((px[cal[15]] / px[cal[10]] - 1.0) * 100.0)
    [short] = _score([_item(2, panel, "S04", 10, h=21)], panel[panel["date"] <= cal[40]], tmp=tmp_path)
    assert short.outcome_status == "matured" and short.stale_exit is True


def test_pending_before_h_sessions(tmp_path: Path) -> None:
    panel = _panel()
    last = N_SESSIONS - 1
    res = _score([_item(1, panel, "S05", last - 20), _item(2, panel, "S05", last - 21),
                  _item(3, panel, "S05", last - 62, h=63)], panel, tmp=tmp_path)
    assert [r.outcome_status for r in res] == ["pending", "matured", "pending"]
    assert res[0].realized_return_pct is None and res[0].void_reason is None


# ── live metrics ────────────────────────────────────────────────────────────


def _ledger(n_dates: int, ic_sign: float = 1.0, names: int = 50, seed: int = 3,
            top_bias: float = 0.0) -> list[dict[str, Any]]:
    """Matured rows: excess = sign * 0.3 * score + noise (IC about 0.28 in absolute value)."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.bdate_range("2025-01-01", periods=n_dates):
        score = rng.normal(size=names)
        excess = ic_sign * 0.3 * score + rng.normal(size=names)
        rp = (pd.Series(score).rank().to_numpy() - 0.5) / names
        bucket = np.minimum(5, np.floor(5 * rp) + 1).astype(int)
        top = excess > np.median(excess) - top_bias
        for i in range(names):
            rows.append({"as_of": d.date(), "symbol": f"S{i:02d}", "score": float(score[i]),
                         "rank_pct": float(rp[i]), "bucket": int(bucket[i]), "p_top_half": 0.5,
                         "outcome_status": "matured", "realized_excess_pp": float(excess[i]),
                         "realized_top_half": bool(top[i]), "stale_exit": False})
    return rows


def _request(rows: list[dict[str, Any]], h: int = 21) -> LiveMetricsRequest:
    return LiveMetricsRequest.model_validate({"procedure_id": "rg-lgbm-v1", "horizon_days": h, "rows": rows})


VALIDATION = {"rank_ic": {"mean": 0.05}}
CALIBRATOR = {
    "buckets": [{"bucket": b, "frequency": 0.3 + 0.1 * b, "ci_low": 0.0, "ci_high": 1.0,
                 "n": 5000, "neutral": b == 3} for b in range(1, 6)],
    "period": "2021-01-01 to 2024-06-28",
    "base_rate": 0.5,
}


def test_under_12_periods_is_collecting() -> None:
    res = live_metrics(_request(_ledger(251)), VALIDATION, CALIBRATOR)
    assert res.matured_dates == 251 and res.independent_periods == 11
    assert res.live_status == "collecting" and res.live_gate_passed is False


def test_13_period_series_passes_g7() -> None:
    rows = _ledger(273)
    rows += [{**rows[0], "symbol": "VOID1", "outcome_status": "void", "realized_excess_pp": None,
              "realized_top_half": None}]
    rows[1] = {**rows[1], "stale_exit": True}
    res = live_metrics(_request(rows), VALIDATION, CALIBRATOR)
    assert res.independent_periods == 13 and res.live_status == "ok"
    assert res.live_gate_passed is True and res.alarms == []
    assert res.void_n == 1 and res.stale_exit_n == 1 and res.matured_n == 273 * 50
    m = res.metrics
    assert m.rank_ic_mean is not None and m.rank_ic_mean > 0.2
    assert m.rank_ic_hac_t is not None and m.rank_ic_hac_t >= 1.65
    assert m.rank_ic_ci95 is not None and m.rank_ic_ci95[0] < m.rank_ic_mean < m.rank_ic_ci95[1]
    assert m.oos_rank_ic_mean == 0.05 and m.window == "2025-01-01 to 2026-01-16"
    assert m.brier == pytest.approx(0.25) and m.ece is not None  # n_eff = 13,650 / 21 >= 500
    assert m.hit_rate_directional is not None and m.hit_rate_directional > 0.5


def test_g7_needs_live_ic_against_oos() -> None:
    res = live_metrics(_request(_ledger(273)), {"rank_ic": {"mean": 0.9}}, CALIBRATOR)
    assert res.live_status == "ok" and res.live_gate_passed is False
    assert live_metrics(_request(_ledger(273)), None, None).live_gate_passed is False


def test_negative_ic_triggers_a1_under_review() -> None:
    # 370 sessions from 2025-01-01 reach June 2026: full-window month-ends Dec 2025 .. May 2026.
    res = live_metrics(_request(_ledger(370, ic_sign=-1.0)), VALIDATION, CALIBRATOR)
    assert res.live_status == "under_review" and res.live_gate_passed is False
    assert [a.code for a in res.alarms] == ["rolling_ic_negative"]
    assert "through 2026-05-29" in (res.alarms[0].detail or "")
    # 273 sessions give only 1 completed full-window month-end (Dec 2025): no alarm yet.
    short = live_metrics(_request(_ledger(273, ic_sign=-1.0)), VALIDATION, CALIBRATOR)
    assert short.live_status == "ok" and short.alarms == []
    early = live_metrics(_request(_ledger(200, ic_sign=-1.0)), VALIDATION, CALIBRATOR)
    assert early.live_status == "collecting" and early.alarms == []  # A1 is gated at 12 periods


def test_early_negative_ic_then_positive_year_does_not_trigger_a1() -> None:
    neg, pos = _ledger(400, ic_sign=-1.0), _ledger(400, ic_sign=1.0)
    first = sorted({r["as_of"] for r in neg})[126]
    rows = [r for r in neg if r["as_of"] < first] + [r for r in pos if r["as_of"] >= first]
    res = live_metrics(_request(rows), VALIDATION, CALIBRATOR)
    assert res.independent_periods == 19 and res.live_status == "ok"
    assert "rolling_ic_negative" not in {a.code for a in res.alarms}


def test_calibrator_drift_only_warns() -> None:
    drifting = {**CALIBRATOR, "buckets": [{**b, "ci_low": 0.0, "ci_high": 0.01} for b in CALIBRATOR["buckets"]]}
    res = live_metrics(_request(_ledger(273)), VALIDATION, drifting)
    assert res.live_status == "ok" and res.live_gate_passed is True
    codes = {a.code for a in res.alarms}
    assert codes == {"calibrator_drift"}
    assert all("consecutive months" in (a.detail or "") for a in res.alarms)


def test_psi_warning_only_warns() -> None:
    rows = _ledger(273)
    dates = sorted({r["as_of"] for r in rows})
    late = set(dates[-21:])
    shifted = [{**r, "score": r["score"] + 3.0} if r["as_of"] in late else r for r in rows]
    res = live_metrics(_request(shifted), VALIDATION, CALIBRATOR)
    assert "psi_warning" in {a.code for a in res.alarms} and res.live_status == "ok"
    rng = np.random.default_rng(0)
    same = psi(rng.normal(size=5000), rng.normal(size=5000))
    moved = psi(rng.normal(size=5000), rng.normal(2.0, 1.0, size=5000))
    assert same is not None and same < 0.05
    assert moved is not None and moved > 0.25
    assert psi(np.array([1.0]), np.array([1.0])) is None


def test_empty_ledger() -> None:
    res = live_metrics(_request([]), None, None)
    assert res.live_status == "collecting" and res.matured_n == 0 and res.live_gate_passed is False
    assert res.metrics.rank_ic_mean is None and res.metrics.window is None


def test_unknown_symbol_voids_as_mismatch(tmp_path: Path) -> None:
    panel = _panel()
    item = OutcomeRequestItem(prediction_id=9, isin=None, symbol="NOSUCH", as_of=date(2025, 1, 2),
                              horizon_days=21, entry_close=100.0)
    [res] = score_outcomes([item], panel, universe.membership(panel), None, data_dir=tmp_path)
    assert res.outcome_status == "void" and res.void_reason == "entry_price_mismatch"
