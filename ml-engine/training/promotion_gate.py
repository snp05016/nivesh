"""Promotion gate (ML-05): may a candidate model reach production?

Input is the artifact's out-of-fold predictions (``oof_predictions.csv``, one
row per (date, symbol) with ``split`` = 'oof' for walk-forward folds or
'holdout' for the final year). The gate fails closed: a missing column, a NaN
in a required column, or a fold with fewer than MIN_N_PER_FOLD scored rows is
a FAIL.

Checks (every one must pass):
  a. Brier skill score vs the fold's training base rate, BSS = 1 - Brier(p) /
     Brier(train_base_rate): > 0 in every fold, and the pooled date-block
     bootstrap CI lower bound > 0.
  b. ROC AUC: date-block bootstrap CI lower bound > 0.5 + AUC_MARGIN per fold
     and pooled.
  c. Class balance: of the rows outside the neutral band (|p - base| >
     NEUTRAL_BAND), neither predicted class exceeds MAX_CLASS_SHARE.
  d. Net lift: mean fwd_ret_20d of predicted-up rows minus COST_BPS beats
     always-up and 20d momentum (momentum_20d > 0) on the same rows.
  e. Holdout: the holdout rows alone have BSS > 0 and AUC > 0.5.

Every check scores ``p_raw``, the booster's own output, because that is what
ml-engine serves: no calibrator ships to production and InferenceEngine
compares the raw P(up) with the manifest base_rate / neutral_band. The
calibrated ``p_up`` column is report-only; isotonic calibration can spread a
degenerate always-up booster around the base rate and hide it.

Bootstraps resample dates, not rows: rows on one date share the market move.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata

MIN_N_PER_FOLD = 2000
N_BOOT = 1000
BOOT_SEED = 0
AUC_MARGIN = 0.02
MAX_CLASS_SHARE = 0.80
COST_BPS = 30.0
CI = 0.95
NEUTRAL_BAND = 0.02

REQUIRED_COLUMNS = (
    "date", "symbol", "fold", "split", "p_raw", "y",
    "train_base_rate", "fwd_ret_20d", "momentum_20d",
)


def _num(v: float | None) -> float | None:
    """JSON-safe number: NaN/inf become None."""
    return None if v is None or not np.isfinite(v) else round(float(v), 6)


def _check(value: float | None, threshold: float, passed: bool, ci_low: float | None = None) -> dict[str, Any]:
    return {"value": _num(value), "ci_low": _num(ci_low), "threshold": threshold, "passed": bool(passed)}


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = rankdata(p)
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _bss(y: np.ndarray, p: np.ndarray, base: np.ndarray) -> float:
    ref = float(np.sum((base - y) ** 2))
    return 1.0 - float(np.sum((p - y) ** 2)) / ref if ref > 0 else float("nan")


def _bootstrap_low(df: pd.DataFrame) -> tuple[float, float]:
    """Date-block bootstrap lower CI bounds of (BSS, AUC)."""
    df = df.sort_values("date", kind="mergesort")
    y = df["y"].to_numpy(dtype=float)
    p = df["p_raw"].to_numpy(dtype=float)
    base = df["train_base_rate"].to_numpy(dtype=float)
    counts = df.groupby("date", sort=True).size().to_numpy()
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    sq_p = np.add.reduceat((p - y) ** 2, starts)
    sq_ref = np.add.reduceat((base - y) ** 2, starts)

    rng = np.random.default_rng(BOOT_SEED)
    draws = rng.integers(0, len(counts), size=(N_BOOT, len(counts)))
    ref = sq_ref[draws].sum(axis=1)
    bss = np.where(ref > 0, 1.0 - sq_p[draws].sum(axis=1) / np.where(ref > 0, ref, 1.0), np.nan)

    aucs = np.empty(N_BOOT)
    for b, idx in enumerate(draws):
        c = counts[idx]
        rows = np.repeat(starts[idx] - np.concatenate([[0], np.cumsum(c)[:-1]]), c) + np.arange(c.sum())
        aucs[b] = _auc(y[rows], p[rows])

    q = (1.0 - CI) / 2.0 * 100.0
    # A NaN draw (one class only) counts as a failure, never as a pass.
    return (
        float(np.percentile(np.nan_to_num(bss, nan=-np.inf), q)),
        float(np.percentile(np.nan_to_num(aucs, nan=-np.inf), q)),
    )


def evaluate_gate(oof: pd.DataFrame) -> dict[str, Any]:
    """Run every check on the prediction frame; see the module docstring."""
    checks: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    result: dict[str, Any] = {
        "passed": False, "checks": checks, "reasons": reasons,
        "base_rate": None, "neutral_band": NEUTRAL_BAND,
    }

    missing = [c for c in REQUIRED_COLUMNS if c not in oof.columns]
    if missing:
        reasons.append(f"missing columns: {missing}")
        return result

    df = oof[list(REQUIRED_COLUMNS)].copy()
    nan_cols = [c for c in REQUIRED_COLUMNS if df[c].isna().any()]
    if nan_cols:
        reasons.append(f"NaN values in required columns: {nan_cols}")
        return result
    df["y"] = df["y"].astype(int)
    df["date"] = pd.to_datetime(df["date"])

    folds = df[df["split"] == "oof"]
    holdout = df[df["split"] == "holdout"]
    if folds.empty:
        reasons.append("no scored out-of-fold rows")
        return result
    if holdout.empty:
        reasons.append("no holdout rows")
        return result
    result["base_rate"] = round(float(holdout["train_base_rate"].iloc[0]), 6)

    def record(name: str, check: dict[str, Any], why: str) -> None:
        checks[name] = check
        if not check["passed"]:
            reasons.append(f"{name}: {why}")

    groups = [(f"fold_{f}", g) for f, g in folds.groupby("fold", sort=True)] + [("holdout", holdout)]
    for name, g in groups:
        record(f"n_{name}", _check(len(g), MIN_N_PER_FOLD, len(g) >= MIN_N_PER_FOLD),
               f"{len(g)} scored rows < {MIN_N_PER_FOLD}")
    if reasons:  # too few rows for any statistic to mean something
        return result

    def arrays(g: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (g["y"].to_numpy(dtype=float), g["p_raw"].to_numpy(dtype=float),
                g["train_base_rate"].to_numpy(dtype=float))

    auc_min = 0.5 + AUC_MARGIN
    for name, g in groups[:-1]:
        y, p, base = arrays(g)
        bss = _bss(y, p, base)
        record(f"bss_{name}", _check(bss, 0.0, bss > 0), f"Brier skill {bss:.4f} <= 0 (no better than the base rate)")
        _, auc_low = _bootstrap_low(g)
        record(f"auc_{name}", _check(_auc(y.astype(int), p), auc_min, auc_low > auc_min, auc_low),
               f"AUC CI low {auc_low:.4f} <= {auc_min:.2f}")

    # (a, b) pooled over every fold
    y, p, base = arrays(folds)
    bss_low, auc_low = _bootstrap_low(folds)
    record("bss_pooled", _check(_bss(y, p, base), 0.0, bss_low > 0, bss_low),
           f"Brier skill CI low {bss_low:.4f} <= 0")
    record("auc_pooled", _check(_auc(y.astype(int), p), auc_min, auc_low > auc_min, auc_low),
           f"AUC CI low {auc_low:.4f} <= {auc_min:.2f}")

    # (c) class balance outside the neutral band
    edge = p - base
    n_up, n_down = int((edge > NEUTRAL_BAND).sum()), int((edge < -NEUTRAL_BAND).sum())
    share = max(n_up, n_down) / (n_up + n_down) if n_up + n_down else float("nan")
    record("class_share", _check(share, MAX_CLASS_SHARE, n_up + n_down > 0 and share <= MAX_CLASS_SHARE),
           f"largest predicted-class share {share:.4f} > {MAX_CLASS_SHARE} (or no directional predictions)")

    # (d) net-of-cost lift of the predicted-up rows over naive strategies
    ret = folds["fwd_ret_20d"].to_numpy(dtype=float)
    up = edge > NEUTRAL_BAND
    model_net = ret[up].mean() - COST_BPS / 1e4 if up.any() else float("nan")
    momentum = folds["momentum_20d"].to_numpy(dtype=float) > 0
    baseline = max(ret.mean(), ret[momentum].mean() if momentum.any() else -np.inf)
    lift = model_net - baseline
    record("net_lift", _check(lift, 0.0, bool(np.isfinite(lift) and lift > 0)),
           f"predicted-up return net of {COST_BPS:.0f} bps does not beat always-up / momentum (lift {lift:.5f})")

    # (e) the holdout year on its own
    y, p, base = arrays(holdout)
    h_bss, h_auc = _bss(y, p, base), _auc(y.astype(int), p)
    record("bss_holdout", _check(h_bss, 0.0, h_bss > 0), f"holdout Brier skill {h_bss:.4f} <= 0")
    record("auc_holdout", _check(h_auc, 0.5, h_auc > 0.5), f"holdout AUC {h_auc:.4f} <= 0.5")

    result["passed"] = not reasons
    return result
