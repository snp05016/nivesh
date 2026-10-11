"""Live metrics and the A1 kill-switch for one procedure and horizon (spec 8.5, D13, D28).

Population: matured rows only (the backend already drops ``prices_fallback_yfinance``
predictions); void and stale-exit counts are reported alongside.

- Daily RankIC = Spearman(score, realized_excess_pp) per as-of date (at least 40
  names), HAC t (Hansen-Hodrick, Bartlett fallback) and a block-bootstrap CI.
- ``independent_periods`` = floor(matured_dates / h); ``collecting`` below 12.
- **A1** (the only status change): the rolling 12-month mean IC is below 0 at 6
  consecutive completed month-ends. Evaluated only from 12 independent periods on,
  and only at month-ends whose 12-month window is fully covered by live IC. It sets
  ``under_review``; reinstatement is a new procedure version promoted by hand.
- Admin warnings, never a status change: ``calibrator_drift`` (a bucket's live
  frequency outside its stored CI for 3 consecutive months, buckets with at least
  100 matured rows that month) and ``psi_warning`` (score PSI > 0.25).
- ``live_gate_passed`` (G7) = periods >= 12, HAC t >= 1.65, live mean IC >=
  0.5 x OOS mean IC (``validation.json`` ``rank_ic.mean``) and no A1 alarm.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .config import LIVE
from .contract import LiveAlarm, LiveMetrics, LiveMetricsRequest, LiveMetricsResponse
from .models.calibration import CohortCalibrator
from .validation import metrics

__all__ = ["live_metrics", "psi"]

PSI_BINS = 10
_PSI_EPS = 1e-4


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def psi(reference: np.ndarray, current: np.ndarray, bins: int = PSI_BINS) -> float | None:
    """Population stability index of ``current`` against decile bins of ``reference``."""
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref, cur = ref[np.isfinite(ref)], cur[np.isfinite(cur)]
    if ref.size < bins or cur.size < bins:
        return None
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)[1:-1]))
    p = np.bincount(np.searchsorted(edges, ref, side="right"), minlength=edges.size + 1) / ref.size
    q = np.bincount(np.searchsorted(edges, cur, side="right"), minlength=edges.size + 1) / cur.size
    p, q = np.clip(p, _PSI_EPS, None), np.clip(q, _PSI_EPS, None)
    return float(np.sum((q - p) * np.log(q / p)))


def _a1(ic: pd.Series) -> LiveAlarm | None:
    """Rolling 12-month mean IC < 0 at 6 consecutive month-ends, anywhere in the live history.

    A month-end is the last IC date of a completed month (the month of the latest IC
    date is still open). Only month-ends whose trailing window is fully covered by
    live history are evaluated; earlier ones neither count towards the run nor reset it.
    """
    a1 = LIVE["a1"]
    ic = ic.dropna().sort_index()
    if ic.empty:
        return None
    idx = pd.DatetimeIndex(ic.index)
    months = np.asarray(idx.to_period("M").asi8)
    run = 0
    for m in idx[:-1][months[1:] != months[:-1]]:  # last IC date of each completed month
        start = m - pd.DateOffset(months=a1["window_months"])
        if idx[0] > start + pd.Timedelta(days=1):
            continue  # partial window
        window = ic.loc[(idx > start) & (idx <= m)]
        run = run + 1 if float(window.mean()) < a1["ic_below"] else 0
        if run >= a1["consecutive_month_ends"]:
            return LiveAlarm(code="rolling_ic_negative", detail=(
                f"rolling {a1['window_months']}-month mean IC below {a1['ic_below']:g} at {run} "
                f"consecutive month-ends through {m.date().isoformat()}"
            ))
    return None


def _calibrator_drift(rows: pd.DataFrame, cal: CohortCalibrator) -> list[LiveAlarm]:
    """Buckets whose monthly live frequency left the stored CI for 3 consecutive months."""
    cfg = LIVE["calibrator_drift"]
    if not cal.available:
        return []
    m = rows.loc[rows["bucket"].notna() & rows["realized_top_half"].notna()].copy()
    if m.empty:
        return []
    m["month"] = pd.DatetimeIndex(m["as_of"]).to_period("M")
    m["top"] = m["realized_top_half"].astype(float)
    stats = m.groupby(["bucket", "month"])["top"].agg(["mean", "size"])
    alarms: list[LiveAlarm] = []
    for entry in cal.buckets:
        lo, hi = _num(entry.get("ci_low")), _num(entry.get("ci_high"))
        b = int(entry["bucket"])
        if lo is None or hi is None or b not in stats.index.get_level_values("bucket"):
            continue
        run, prev, worst = 0, None, 0
        for month, row in stats.loc[b].iterrows():
            if row["size"] >= cfg["min_rows_per_bucket_month"] and not lo <= row["mean"] <= hi:
                run = run + 1 if prev is not None and (month - prev).n == 1 else 1
                prev = month
            else:  # in range, too few rows, or (via the gap check above) a missing month
                run, prev = 0, None
            worst = max(worst, run)
        if worst >= cfg["consecutive_months"]:
            alarms.append(LiveAlarm(code="calibrator_drift", detail=(
                f"bucket {b}: live frequency outside the stored interval for {worst} consecutive months"
            )))
    return alarms


def live_metrics(
    request: LiveMetricsRequest | Mapping[str, Any],
    validation_json: Mapping[str, Any] | None,
    calibrator_json: Mapping[str, Any] | None,
) -> LiveMetricsResponse:
    """LiveMetricsResponse (6.5) for one (procedure, horizon) from its ledger rows.

    ``validation_json`` and ``calibrator_json`` are the active artefact's files
    (None when missing: the OOS ratio then fails G7 and probability metrics are null).
    """
    req = request if isinstance(request, LiveMetricsRequest) else LiveMetricsRequest.model_validate(request)
    h = req.horizon_days
    g7 = LIVE["g7"]
    cols = ["as_of", "symbol", "score", "rank_pct", "bucket", "p_top_half", "outcome_status",
            "realized_excess_pp", "realized_top_half", "stale_exit"]
    rows = pd.DataFrame([r.model_dump() for r in req.rows], columns=cols)
    rows["as_of"] = pd.to_datetime(rows["as_of"])
    matured = rows.loc[rows["outcome_status"] == "matured"].reset_index(drop=True)
    void_n = int((rows["outcome_status"] == "void").sum())
    stale_n = int(matured["stale_exit"].fillna(False).astype(bool).sum())
    matured_dates = int(matured["as_of"].nunique())
    periods = matured_dates // h

    keyed = matured.set_index(["as_of", "symbol"])
    ic = metrics.rank_ic_daily(keyed["score"].astype(float), keyed["realized_excess_pp"].astype(float)).dropna()
    ic_mean = _num(ic.mean()) if len(ic) else None
    hac = _num(metrics.hac_t(ic, h))
    ci = metrics.block_bootstrap_ci(ic, metrics.daily_block(h))
    ci95 = (ci[0], ci[1]) if all(_num(v) is not None for v in ci) else None
    oos_mean = _num(((validation_json or {}).get("rank_ic") or {}).get("mean"))

    cal = CohortCalibrator.from_json(calibrator_json)
    hit = None
    if len(matured):
        top = matured["realized_top_half"].astype(float)
        neutral = cal.neutral_array(matured["bucket"].astype(float).to_numpy())
        hit = _num(metrics.hit_rate_directional(matured["rank_pct"].astype(float), top, matured["as_of"], h,
                                                neutral=neutral)["value"])
    prob = matured.loc[matured["p_top_half"].notna() & matured["realized_top_half"].notna()]
    brier = bss = ece = None
    if len(prob):
        p = prob["p_top_half"].to_numpy(dtype=float)
        y = prob["realized_top_half"].astype(float).to_numpy()
        brier = _num(metrics.brier(p, y))
        bss = _num(metrics.bss(p, y, cal.base_rate)) if cal.base_rate is not None else None
        if len(prob) / h >= LIVE["ece_min_n_eff"]:
            ece = _num(metrics.ece_bins(p, y))

    alarms: list[LiveAlarm] = []
    a1 = _a1(ic) if periods >= g7["min_independent_periods"] else None
    if a1 is not None:
        alarms.append(a1)
    alarms.extend(_calibrator_drift(matured, cal))
    dates = sorted(set(rows["as_of"]))
    if len(dates) >= 2 * h:
        value = psi(rows.loc[rows["as_of"].isin(dates[:h]), "score"].to_numpy(dtype=float),
                    rows.loc[rows["as_of"].isin(dates[-h:]), "score"].to_numpy(dtype=float))
        if value is not None and value > LIVE["psi_warning"]:
            alarms.append(LiveAlarm(code="psi_warning", detail=f"score PSI {value:.3f} (latest {h} dates vs first {h})"))

    if periods < g7["min_independent_periods"]:
        status = "collecting"
    else:
        status = "under_review" if a1 is not None else "ok"
    gate = (
        periods >= g7["min_independent_periods"]
        and hac is not None and hac >= g7["min_hac_t"]
        and ic_mean is not None and oos_mean is not None and ic_mean >= g7["min_ic_ratio_vs_oos"] * oos_mean
        and a1 is None
    )
    window = None
    if matured_dates:
        window = f"{matured['as_of'].min().date().isoformat()} to {matured['as_of'].max().date().isoformat()}"
    return LiveMetricsResponse(
        live_status=status,
        matured_n=int(len(matured)),
        void_n=void_n,
        stale_exit_n=stale_n,
        matured_dates=matured_dates,
        independent_periods=periods,
        live_gate_passed=bool(gate),
        metrics=LiveMetrics(
            rank_ic_mean=ic_mean, rank_ic_hac_t=hac, rank_ic_ci95=ci95, oos_rank_ic_mean=oos_mean,
            hit_rate_directional=hit, brier=brier, bss=bss, ece=ece, window=window,
        ),
        alarms=alarms,
    )
