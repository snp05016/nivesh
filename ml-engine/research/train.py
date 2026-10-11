"""Walk-forward training and validation CLI for ``rg-lgbm-v1`` (spec 4.3, 4.4, 5.1-5.8).

::

    python -m research.train --horizon {21,63} --source {store,local_csv} [--data-dir D] [--fast]
        [--open-lockbox --confirm-config-sha SHA] [--null-calibration N] [--train-production]

Steps: panel, PIT membership, fv1 features and labels; quarterly walk-forward
folds (purge h + 21-session embargo, lockbox boundary); the model and every
baseline on identical folds; 5.4 metrics with HAC t, the daily-path portfolio
with costs, DSR in monthly units, PBO, cross-fitted calibration and probability
metrics; gates and tier; ``validation.json``, ``validation.md`` and
``gate_result.json`` under ``models/{model_id}/``. ``--train-production`` also
writes the boosters, ``calibrator.json`` and ``manifest.json`` (promotion stays
a separate operator step: ``python -m research.registry promote``).

- Trials: a ``source=store`` run appends to TRIALS.jsonl; ``--fast``,
  ``--null-calibration`` and ``local_csv`` runs append to TRIALS_DEV.jsonl.
  One run adds one trial per scorer (the model and B3-B8); DSR and PBO read the
  same ledger for this horizon.
- Lockbox: opened once per (procedure, horizon), only with ``--open-lockbox
  --confirm-config-sha <config_sha256()>``; the opening is logged before any
  result is written, and the result block is recorded once in
  ``models/lockbox/{procedure_id}-h{h}.json``. Later runs (production
  training, quarterly refits) reuse that recorded block for G6 and P after
  checking it against the logged ``result_sha256``. Dev runs use
  LOCKBOX_LOG_DEV.jsonl and ``-dev`` result files, never the real lockbox.
  A non-dev ``--train-production`` needs the lockbox recorded first.
  ``rg-lgbm-v1`` is lockbox spent (D13).
- A model directory that already holds ``manifest.json`` is never rewritten;
  such a rerun is refused.
- ``--fast``: 1 seed, 50 rounds, the last 2 folds; marked fast (dev only).
- ``data_checks.manifest_verifies`` (G0) is true only when the run reads a
  hashed raw snapshot (``source=store``) whose ``raw/MANIFEST.jsonl`` entries all
  verify; a local CSV has no raw manifest, so a dev run always fails G0.

Every output is deterministic for fixed inputs (no timestamps in
``validation.json`` unless the lockbox was opened), and training runs in-process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from . import config, registry
from .features import FEATURE_VERSION, FEATURES, cached_raw, rank
from .labels import make_labels
from .marketdata import store, universe
from .models import baselines, lgbm
from .models.calibration import CohortCalibrator
from .validation import metrics
from .validation.costs import portfolio_returns
from .validation.folds import Fold, _inner_split, fold_hash, make_lockbox_fold, make_walkforward_folds
from .validation.gates import evaluate_gates
from .validation.report import render_markdown

log = logging.getLogger("research.train")

MODEL = "lgbm"
TRIAL_SCORERS = (MODEL, "B3", "B4", "B5", "B6", "B7", "B8")  # one trial each per run
FEATS = list(FEATURES)
STRESS_WINDOW = ("2020-02-01", "2020-06-30")


class LockboxRefused(Exception):
    pass


@dataclass(frozen=True)
class RunConfig:
    horizon: int
    source: str = "store"
    data_dir: Path = config.DATA_DIR
    fast: bool = False
    open_lockbox: bool = False
    confirm_config_sha: str | None = None
    null_calibration: int = 0
    train_production: bool = False

    @property
    def dev(self) -> bool:
        return self.fast or self.null_calibration > 0 or self.source == "local_csv"

    @property
    def dates(self) -> dict[str, Any]:
        return config.DATES["dev" if self.source == "local_csv" else "prod"]

    @property
    def seeds(self) -> tuple[int, ...]:
        if self.fast:
            return tuple(config.LGBM_SEEDS[: config.FAST["seeds"]])
        if self.null_calibration:
            return tuple(config.LGBM_SEEDS[: config.NULL_CALIBRATION["seeds"]])
        return tuple(config.LGBM_SEEDS)

    @property
    def max_rounds(self) -> int:
        if self.fast:
            return int(config.FAST["max_rounds"])
        if self.null_calibration:
            return int(config.NULL_CALIBRATION["max_rounds"])
        return int(config.LGBM_MAX_ROUNDS)


@dataclass
class Inputs:
    panel: pd.DataFrame
    quality: str
    data_sha256: str
    sessions: pd.DatetimeIndex
    design: pd.DataFrame  # in-universe rows: ranked features, labels, sess (int session index)
    raw: pd.DataFrame  # raw fv1 features (all panel rows)
    rules: pd.DataFrame  # B3-B7 on the design rows
    px: pd.DataFrame  # session x entity px_idx
    member: pd.DataFrame  # session x entity bool U_t
    adv: pd.DataFrame  # session x entity 63-day median value traded, INR crore
    data_checks: dict[str, Any]


# ── helpers ─────────────────────────────────────────────────────────────────


def git_sha() -> str:
    env = os.environ.get("GIT_SHA")
    if env:
        return env.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=10, check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def jsonable(obj: Any) -> Any:
    """numpy/pandas scalars to Python, NaN/inf to None, dates to ISO strings, tuples to lists."""
    if isinstance(obj, Mapping):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return _num(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.date().isoformat() if isinstance(obj, (pd.Timestamp, datetime)) else obj.isoformat()
    return obj


def _col(frame: pd.DataFrame, name: str) -> pd.Series:
    return cast(pd.Series, frame[name])


def _years(d: pd.DatetimeIndex) -> np.ndarray:
    return d.to_numpy(dtype="datetime64[ns]").astype("datetime64[Y]").astype(np.int64) + 1970


def _day(ts: Any) -> str:
    return pd.Timestamp(ts).date().isoformat()


def _raw_manifest_verifies(rc: RunConfig) -> bool:
    """True when the store's raw snapshot is hashed and every latest manifest entry verifies."""
    if rc.source != "store":
        return False
    latest: dict[str, str] = {}
    for e in store.read_manifest(rc.data_dir):
        latest[str(e["path"])] = str(e["sha256"])
    if not latest:
        return False
    root = Path(rc.data_dir)
    for rel, sha in latest.items():
        f = root / rel
        if not f.is_file() or registry.sha256_file(f) != sha:
            log.error("raw manifest mismatch: %s", rel)
            return False
    return True


# ── inputs ──────────────────────────────────────────────────────────────────


def build_inputs(rc: RunConfig, panel: pd.DataFrame | None = None) -> Inputs:
    """Panel, membership, features, labels and the in-universe design matrix for ``rc.horizon``."""
    h = rc.horizon
    dc = rc.dates
    if panel is None:
        source: Literal["store", "local_csv"] = "local_csv" if rc.source == "local_csv" else "store"
        panel = store.load_panel(start=dc["data_start"], source=source, data_dir=rc.data_dir)
    if panel.empty:
        raise ValueError("the panel is empty")
    mem = universe.membership(panel)
    quality = str(mem.attrs.get("universe_quality", "pit"))
    data_sha = store.data_sha256(panel)
    raw = cached_raw(panel, mem, data_sha, Path(rc.data_dir))
    ranked = rank(raw, mem)
    lab = make_labels(panel, mem, horizons=(h,))
    cal = store.sessions(panel)
    n = len(cal)

    dates = pd.DatetimeIndex(lab.index.get_level_values("date"))
    sess = cal.get_indexer(dates)
    x = ranked.reindex(lab.index)
    y = cast(pd.DataFrame, lab[[f"ret_{h}", f"top_{h}", f"rank_{h}", f"label_end_{h}"]])
    y = y.set_axis(["ret", "top", "rank", "label_end"], axis=1)
    nan_share = x.isna().to_numpy().mean(axis=1)
    considered = (dates >= pd.Timestamp(dc["train_start"])) & (sess + h <= n - 1)
    bad_feat = nan_share > config.FEATURE_RULES["max_row_nan_share"]
    no_label = _col(y, "rank").isna().to_numpy()
    keep = considered & ~bad_feat & ~no_label
    design = pd.concat([x, y], axis=1).loc[keep].copy()
    design["sess"] = sess[keep].astype(np.int64)

    n_considered = int(considered.sum())
    acct = panel.attrs.get("row_accounting") or {}
    panel_drop = float(acct.get("dropped_share", 0.0) or 0.0)
    design_drop = 1.0 - float(keep.sum()) / n_considered if n_considered else 1.0
    data_checks = {
        "drop_share": max(panel_drop, design_drop),
        "panel_dropped_share": panel_drop,
        "rows_considered": n_considered,
        "rows_dropped_nan_features": int((considered & bad_feat).sum()),
        "rows_dropped_missing_label": int((considered & ~bad_feat & no_label).sum()),
        "fold_hashes_identical": None,  # set after the walk-forward
        "manifest_verifies": _raw_manifest_verifies(rc),
    }

    px = panel.pivot(index="date", columns="entity_id", values="px_idx").astype(float)
    member = (
        mem.pivot(index="date", columns="entity_id", values="in_universe")
        .reindex(index=px.index, columns=px.columns).fillna(False).astype(bool)
    )
    adv_s = pd.Series(np.exp(_col(raw, "log_adv_63").to_numpy(dtype=float)) / 1e7, index=raw.index)
    adv = cast(pd.DataFrame, adv_s.unstack("entity_id")).reindex(index=px.index, columns=px.columns)
    rules = baselines.rule_scores(design[FEATS], baselines.momentum_20(panel))
    return Inputs(panel, quality, data_sha, cal, design, raw, rules, px, member, adv, data_checks)


# ── walk-forward ────────────────────────────────────────────────────────────


def _rows(sess: np.ndarray, idx: np.ndarray) -> np.ndarray:
    return np.isin(sess, idx)


def run_model(
    design: pd.DataFrame, folds: Sequence[Fold], rc: RunConfig, y_train: np.ndarray | None = None,
) -> tuple[pd.Series, list[str], dict[int, list[int]]]:
    """Model scores on every fold's test rows, the fold hashes it used, best iterations per fold."""
    sess = design["sess"].to_numpy()
    y = design["rank"].to_numpy(dtype=float) if y_train is None else y_train
    scores = np.full(len(design), np.nan)
    hashes: list[str] = []
    best: dict[int, list[int]] = {}
    for f in folds:
        hashes.append(fold_hash(f))
        mi, mv, mt, ms = (_rows(sess, a) for a in (f.inner_train_idx, f.inner_val_idx, f.train_idx, f.test_idx))
        trained = lgbm.train_procedure(
            design.loc[mi, FEATS], y[mi], sess[mi], design.loc[mv, FEATS], y[mv],
            design.loc[mt, FEATS], y[mt], sess[mt], seeds=rc.seeds, max_rounds=rc.max_rounds,
        )
        best[f.k] = [t.best_iteration for t in trained]
        scores[ms] = lgbm.predict([t.booster for t in trained], design.loc[ms, FEATS])
        log.info("fold %d (%s): best iterations %s", f.k, _day(f.test_start), best[f.k])
    return pd.Series(scores, index=design.index, name=MODEL), hashes, best


def run_baselines(
    design: pd.DataFrame, rules: pd.DataFrame, folds: Sequence[Fold], y_train: np.ndarray | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """B0-B8 on every fold's test rows (B1/B2 are probabilities) and the fold hashes used."""
    sess = design["sess"].to_numpy()
    y = design["rank"].to_numpy(dtype=float) if y_train is None else y_train
    top = design["top"].to_numpy(dtype=float)
    out = pd.DataFrame(np.nan, index=design.index, columns=list(baselines.BASELINE_IDS))
    hashes: list[str] = []
    for f in folds:
        hashes.append(fold_hash(f))
        mi, mv, mt, ms = (_rows(sess, a) for a in (f.inner_train_idx, f.inner_val_idx, f.train_idx, f.test_idx))
        n = int(ms.sum())
        out.loc[ms, "B0"] = baselines.random_scores(n, f.k)
        out.loc[ms, "B1"] = baselines.base_rate(top[mt])
        out.loc[ms, "B2"] = 1.0
        for b in ("B3", "B4", "B5", "B6", "B7"):
            out.loc[ms, b] = rules.loc[ms, b].to_numpy(dtype=float)
        ridge, _ = baselines.fit_ridge(
            design.loc[mi, FEATS], y[mi], design.loc[mv, FEATS], y[mv], design.loc[mt, FEATS], y[mt]
        )
        out.loc[ms, "B8"] = baselines.predict_ridge(ridge, design.loc[ms, FEATS])
    return out, hashes


def cross_fit(oos: pd.DataFrame, folds: Sequence[Fold], h: int) -> pd.DataFrame:
    """rank_pct, bucket, then p / base_rate / neutral from a calibrator fitted before each test quarter."""
    oos = oos.copy()
    oos["rank_pct"] = lgbm.rank_pct(_col(oos, MODEL))
    oos["bucket"] = lgbm.bucket(oos["rank_pct"])
    oos["p"] = np.nan
    oos["base_rate"] = np.nan
    oos["neutral"] = False
    k = oos["k"].to_numpy()
    for f in folds:
        cal = CohortCalibrator.fit(oos, f.test_start, h)
        if not cal.available:
            continue
        m = k == f.k
        b = oos.loc[m, "bucket"].to_numpy()
        oos.loc[m, "p"] = cal.p_array(b)
        oos.loc[m, "base_rate"] = cal.base_rate
        oos.loc[m, "neutral"] = cal.neutral_array(b)
    return oos


def permuted_labels(design: pd.DataFrame, replicate: int) -> np.ndarray:
    """``rank`` labels shuffled across entities within each date (null calibration, 5.7)."""
    rng = np.random.default_rng([config.BOOTSTRAP["seed"], 1000 + replicate])
    sess = design["sess"].to_numpy()
    order = np.lexsort((rng.random(len(design)), sess))  # design is sorted by date
    return design["rank"].to_numpy(dtype=float)[order]


def walk_forward(
    inputs: Inputs, folds: Sequence[Fold], rc: RunConfig, y_train: np.ndarray | None = None,
) -> tuple[pd.DataFrame, dict[str, list[str]], dict[int, list[int]]]:
    """OOS frame (test rows of every fold) with all scores and labels, fold hashes per scorer."""
    design = inputs.design
    model, model_hashes, best = run_model(design, folds, rc, y_train)
    base, base_hashes = run_baselines(design, inputs.rules, folds, y_train)
    sess = design["sess"].to_numpy()
    k = np.full(len(design), -999, dtype=np.int64)
    for f in folds:
        k[_rows(sess, f.test_idx)] = f.k
    test = k != -999
    oos = pd.concat([model, base, design[["ret", "top", "rank", "label_end", "sess"]]], axis=1).loc[test]
    oos["k"] = k[test]
    hashes = {MODEL: model_hashes, **{b: base_hashes for b in baselines.BASELINE_IDS}}
    return oos, hashes, best


# ── metrics ─────────────────────────────────────────────────────────────────


def _ic_stats(ic: pd.Series, h: int) -> dict[str, Any]:
    ic = ic.dropna()
    return {"mean_ic": _num(ic.mean()) if len(ic) else None, "hac_t": _num(metrics.hac_t(ic, h)),
            "n_dates": int(len(ic))}


def _ic(oos: pd.DataFrame, col: str) -> pd.Series:
    return metrics.rank_ic_daily(_col(oos, col), _col(oos, "ret"))


def _portfolio(oos: pd.DataFrame, col: str, inputs: Inputs, h: int, mult: float = 1.0) -> pd.DataFrame:
    scores = cast(pd.DataFrame, _col(oos, col).unstack("entity_id")).reindex(columns=inputs.px.columns)
    return portfolio_returns(scores, inputs.px, inputs.member, inputs.adv, h, mult)


def _mean_pct(s: pd.Series) -> float | None:
    return _num(s.mean() * 100.0) if len(s) else None


def _sr(values: Sequence[float]) -> float | None:
    a = np.asarray([v for v in values if v is not None], dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 2 or not a.std(ddof=1) > 0:
        return None
    return float(a.mean() / a.std(ddof=1))


def _slice_ics(ic: pd.Series, groups: Mapping[str, pd.DatetimeIndex], h: int) -> dict[str, Any]:
    return {name: _ic_stats(ic.reindex(d), h) for name, d in groups.items()}


def _slices(oos: pd.DataFrame, ic: pd.Series, inputs: Inputs, rc: RunConfig) -> dict[str, Any]:
    h = rc.horizon
    d = pd.DatetimeIndex(ic.dropna().index)
    yr = _years(d)
    years = {str(y): d[yr == y] for y in sorted(set(yr.tolist()))}

    vol = cast(pd.Series, _col(inputs.raw, "vol_63").reindex(oos.index).groupby(level=0).mean()).reindex(d)
    v = vol.to_numpy(dtype=float)
    lo, hi = (np.nanquantile(v, [1 / 3, 2 / 3]) if np.isfinite(v).any() else (np.nan, np.nan))
    terciles = {"low": d[v <= lo], "mid": d[(v > lo) & (v <= hi)], "high": d[v > hi]}

    index = store.load_index("NIFTY50", data_dir=rc.data_dir)
    if index is not None and len(index):
        lvl = index.reindex(inputs.sessions).ffill()
        r63 = np.log(lvl / lvl.shift(63))
        basis = config.BENCHMARK_ID
    else:  # dev: no cached index, use the equal-weight U_t trailing 63-session log return
        lp = cast(pd.DataFrame, np.log(inputs.px.where(inputs.px > 0)))
        r63 = (lp - lp.shift(63)).where(inputs.member).mean(axis=1)
        basis = "universe_equal_weight"
    sign = r63.reindex(d).to_numpy(dtype=float)
    nifty = {"basis": basis, **_slice_ics(ic, {"up": d[sign >= 0], "down": d[sign < 0]}, h)}

    adv = inputs.raw["log_adv_63"].reindex(oos.index)
    high = adv.ge(adv.groupby(level=0).transform("median"))
    adv_half = {
        "high": _ic_stats(metrics.rank_ic_daily(oos.loc[high, MODEL], oos.loc[high, "ret"]), h),
        "low": _ic_stats(metrics.rank_ic_daily(oos.loc[~high, MODEL], oos.loc[~high, "ret"]), h),
    }
    mid = len(d) // 2
    covid = d[(d >= pd.Timestamp(STRESS_WINDOW[0])) & (d <= pd.Timestamp(STRESS_WINDOW[1]))]
    return {
        "calendar_year": _slice_ics(ic, years, h),
        "vol_tercile": _slice_ics(ic, terciles, h),
        "nifty_63d_sign": nifty,
        "adv_half": adv_half,
        "period_halves": _slice_ics(ic, {"first": d[:mid], "second": d[mid:]}, h),
        "covid_2020_02_06": {"window": f"{STRESS_WINDOW[0]} to {STRESS_WINDOW[1]}", **_ic_stats(ic.reindex(covid), h)},
    }


def _probability(oos: pd.DataFrame, rc: RunConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Probability block (cross-fitted p from prob_metrics_start) and the B1/B2 probability baselines."""
    h = rc.horizon
    dates = pd.DatetimeIndex(oos.index.get_level_values(0))
    pm = oos.loc[(dates >= pd.Timestamp(rc.dates["prob_metrics_start"])) & oos["p"].notna()]
    empty = {"brier": None, "bss": None, "bss_ci95": [None, None], "log_loss": None, "auc_by_year": {}}
    if pm.empty:
        return empty, {"B1": {"brier": None, "log_loss": None}, "B2": {"brier": None, "log_loss": None}}
    p, top, base = pm["p"].to_numpy(), pm["top"].to_numpy(), pm["base_rate"].to_numpy()
    pd_dates = pm.index.get_level_values(0)
    block = {
        "brier": metrics.brier(p, top),
        "bss": metrics.bss(p, top, base),
        "bss_ci95": list(metrics.bss_ci(p, top, base, pd_dates, h)),
        "log_loss": metrics.log_loss(p, top),
        "auc_by_year": metrics.auc_by_year(p, top, pd_dates, h),
        "n": int(len(pm)),
    }
    probs = {
        b: {"brier": metrics.brier(pm[b].to_numpy(), top), "log_loss": metrics.log_loss(pm[b].to_numpy(), top)}
        for b in baselines.PROBABILITY_IDS
    }
    return block, probs


def _trial_rows(
    ics: Mapping[str, pd.Series], actives: Mapping[str, pd.Series], inputs: Inputs,
    rc: RunConfig, sha: str, suffix: str, scorers: Sequence[str] = TRIAL_SCORERS,
) -> list[dict[str, Any]]:
    rows = []
    for s in scorers:
        ic = ics[s]
        act = actives[s]
        rows.append({
            "procedure_id": config.PROCEDURE_ID,
            "horizon": rc.horizon,
            "scorer_id": s + suffix,
            "config_sha256": config.config_sha256(),
            "git_sha": sha,
            "data_sha256": inputs.data_sha256,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "metrics": jsonable({
                "mean_ic": ic.mean(), "hac_t": metrics.hac_t(ic, rc.horizon), "t_star": metrics.t_star(ic, rc.horizon),
                "net_monthly_pct": _mean_pct(act),
            }),
            "monthly_net_active": [[_day(t), _num(v)] for t, v in act.items()],
        })
    return rows


def _overfitting(model_active: pd.Series, trials: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], float | None]:
    """N, PBO over trials covering every model month, and DSR of the model's monthly net active series."""
    srs = [_sr([v for _, v in t["monthly_net_active"]]) for t in trials]
    months = [_day(t) for t in model_active.index]
    cols = []
    for t in trials:
        series = {d: v for d, v in t["monthly_net_active"]}
        col = [series.get(m) for m in months]
        if all(v is not None for v in col):
            cols.append(col)
    pbo = None
    if len(cols) >= 2 and len(months) >= config.METRICS["cscv_blocks"]:
        pbo = metrics.pbo_cscv(np.asarray(cols, dtype=float).T)
    dsr = metrics.dsr(model_active.to_numpy(dtype=float), [s for s in srs if s is not None])
    return {"n_trials": len(trials), "pbo": _num(pbo)}, _num(dsr)


def summarise(
    oos: pd.DataFrame, inputs: Inputs, folds: Sequence[Fold], hashes: Mapping[str, list[str]], rc: RunConfig,
    sha: str, trial_suffix: str, lockbox: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """validation.json (5.8) with gates and tier, plus this run's trial rows."""
    h = rc.horizon
    ics = {s: _ic(oos, s) for s in (MODEL, *baselines.RANKING_IDS)}
    ic = ics[MODEL]
    ic_clean = ic.dropna()
    fold_of_date = oos["k"].groupby(level=0).first()
    period_means = cast(pd.Series, ic_clean.groupby(fold_of_date.reindex(ic_clean.index)).mean())
    nt = metrics.nonoverlap_t(ic_clean, h)
    nt_ok = nt[np.isfinite(nt)]
    years = _years(pd.DatetimeIndex(ic_clean.index))
    rank_ic = {
        "mean": _num(ic_clean.mean()) if len(ic_clean) else None,
        "hac_t": metrics.hac_t(ic_clean, h),
        "nonoverlap_t_median": float(np.median(nt_ok)) if len(nt_ok) else None,
        "nonoverlap_t_range": [float(nt_ok.min()), float(nt_ok.max())] if len(nt_ok) else [None, None],
        "ci95": list(metrics.block_bootstrap_ci(ic_clean, metrics.daily_block(h))),
        "icir_ann": metrics.icir_ann(ic_clean, h),
        "positive_period_share": float((period_means > 0).mean()) if len(period_means) else None,
        "by_year": {str(y): {"mean": _num(ic_clean[years == y].mean()),
                             "hac_t": _num(metrics.hac_t(ic_clean[years == y], h)),
                             "n_dates": int((years == y).sum())} for y in sorted(set(years))},
    }

    prob, prob_base = _probability(oos, rc)
    base_block: dict[str, Any] = {}
    for b in baselines.BASELINE_IDS:
        base_block[b] = prob_base[b] if b in prob_base else {
            "mean_ic": _num(ics[b].mean()), "hac_t": _num(metrics.hac_t(ics[b], h))}

    pf = {s: _portfolio(oos, s, inputs, h) for s in TRIAL_SCORERS}
    actives = {s: _col(pf[s], "active") for s in TRIAL_SCORERS}
    m1 = pf[MODEL]
    m2 = _portfolio(oos, MODEL, inputs, h, config.COSTS["slippage_multipliers"][1])
    act = _col(m1, "active")
    bench = _col(m1, "net") - act
    trial_rows = _trial_rows(ics, actives, inputs, rc, sha, trial_suffix)
    ledger = registry.read_trials(rc.data_dir, dev=rc.dev, horizon=h)
    trials = registry.distinct_trials([*trial_rows, *ledger])
    overfitting, dsr = _overfitting(act, trials)
    portfolio = {
        "net_monthly_pct": _mean_pct(act),
        "gross_monthly_pct": _mean_pct(_col(m1, "gross") - bench),
        "net_monthly_pct_2x_slippage": _mean_pct(_col(m2, "active")),
        "turnover_monthly_pct": _mean_pct(_col(m1, "turnover")),
        "sharpe_net_ann": _num(act.mean() / act.std(ddof=1) * math.sqrt(12)) if len(act) > 1 else None,
        "dsr": dsr,
        "b4_net_monthly_pct": _mean_pct(actives["B4"]),
        "cost_model": config.COST_MODEL_VERSION,
        "n_months": int(len(act)),
    }

    hit = metrics.hit_rate_directional(
        oos["rank_pct"], oos["top"], oos.index.get_level_values(0), h, neutral=oos["neutral"].to_numpy(dtype=bool),
    )
    lb = dict(lockbox or {})
    prob.update({
        "bss_ci95_lockbox": lb.pop("bss_ci95_lockbox", [None, None]),
        "ece_lockbox": lb.pop("ece_lockbox", None),
        "n_eff_lockbox": lb.pop("n_eff_lockbox", None),
    })
    data_checks = dict(inputs.data_checks)
    data_checks["fold_hashes_identical"] = all(v == hashes[MODEL] for v in hashes.values())
    dates = pd.DatetimeIndex(oos.index.get_level_values(0))
    dc = rc.dates
    summary: dict[str, Any] = {
        "procedure_id": config.PROCEDURE_ID,
        "horizon": h,
        "config_sha256": config.config_sha256(),
        "git_sha": sha,
        "data_sha256": inputs.data_sha256,
        "universe_quality": inputs.quality,
        "oos_period": f"{_day(dates.min())} to {_day(dates.max())}",
        "lockbox_period": f"{_day(dc['lockbox_start'])} to {_day(dc['lockbox_end'])}",
        "lockbox_opened_at": lb.pop("opened_at", None),
        "lockbox_spent": config.LOCKBOX_SPENT,
        "n_dates": int(dates.nunique()),
        "avg_universe_n": float(np.mean(oos.groupby(level=0).size().to_numpy())),
        "source": rc.source,
        "fast": rc.fast,
        "n_folds": len(folds),
        "rank_ic": rank_ic,
        "baselines": base_block,
        "vs_best_baseline": metrics.vs_best_baseline(ic, {b: ics[b] for b in baselines.RANKING_IDS}, h),
        "hit_rate_directional": hit,
        "portfolio": portfolio,
        "probability": prob,
        "overfitting": overfitting,
        "lockbox": {"rank_ic_mean": lb.get("rank_ic_mean"), "hac_t": lb.get("hac_t"),
                    "net_monthly_pct": lb.get("net_monthly_pct"), "n_dates": lb.get("n_dates")},
        "slices": _slices(oos, ic, inputs, rc),
        "data_checks": data_checks,
    }
    summary = jsonable(summary)
    res = evaluate_gates(summary, universe_quality=inputs.quality, horizon=h)
    summary.update({"gates": res["gates"], "tier": res["tier"], "reason_codes": res["reason_codes"],
                    "probability_display_passed": res["probability_display_passed"]})
    return jsonable(summary), trial_rows


# ── lockbox ─────────────────────────────────────────────────────────────────


def check_lockbox(rc: RunConfig) -> None:
    """Refuse unless confirmed with the current config sha and never opened for this procedure and horizon.

    Dev runs read and write LOCKBOX_LOG_DEV.jsonl only, so they can never spend
    the production lockbox. A production artefact (non-dev ``--train-production``)
    trains on lockbox-period labels, so it needs the lockbox recorded first
    (or opened in the same run).
    """
    prior = registry.lockbox_opened(config.PROCEDURE_ID, rc.horizon, rc.data_dir, dev=rc.dev)
    if not rc.open_lockbox:
        if rc.confirm_config_sha:
            raise LockboxRefused("--confirm-config-sha is only valid with --open-lockbox")
        if rc.train_production and not rc.dev and prior is None:
            raise LockboxRefused("--train-production needs the lockbox opened and recorded first (--open-lockbox)")
        return
    if rc.confirm_config_sha != config.config_sha256():
        raise LockboxRefused("opening the lockbox needs --confirm-config-sha equal to config_sha256()")
    if prior is not None:
        raise LockboxRefused(f"lockbox already opened for {config.PROCEDURE_ID} h={rc.horizon} at {prior.get('opened_at')}")


def recorded_lockbox(rc: RunConfig) -> dict[str, Any] | None:
    """The recorded one-shot result (with ``opened_at``) for G6/P, verified against the log.

    A tampered or missing result file raises ArtefactError (fail closed). A
    result recorded under another config is not reused, so G6 fails.
    """
    rec = registry.recorded_lockbox(config.PROCEDURE_ID, rc.horizon, rc.data_dir, dev=rc.dev)
    if rec is None:
        return None
    row, result = rec
    if row.get("config_sha256") != config.config_sha256():
        log.warning("recorded lockbox was opened under config %s, not the current config; G6 fails",
                    str(row.get("config_sha256"))[:8])
        return None
    return {**result, "opened_at": row["opened_at"]}


def open_lockbox(inputs: Inputs, oos: pd.DataFrame, rc: RunConfig, sha: str) -> tuple[dict[str, Any], pd.DataFrame]:
    """Score the one-shot lockbox fold, log the opening, return the lockbox block and its predictions."""
    h = rc.horizon
    fold = make_lockbox_fold(inputs.sessions, rc.dates, h)
    if fold is None:
        raise LockboxRefused("no lockbox row has a complete label yet")
    scores, _, _ = run_model(inputs.design, [fold], rc)
    sess = inputs.design["sess"].to_numpy()
    m = _rows(sess, fold.test_idx)
    lbx = pd.concat([scores, inputs.design[["ret", "top", "rank", "label_end", "sess"]]], axis=1).loc[m]
    lbx["k"] = fold.k
    lbx["rank_pct"] = lgbm.rank_pct(_col(lbx, MODEL))
    lbx["bucket"] = lgbm.bucket(lbx["rank_pct"])
    cal = CohortCalibrator.fit(oos, fold.test_start, h)
    lbx["p"] = cal.p_array(lbx["bucket"].to_numpy()) if cal.available else np.nan
    ic = _ic(lbx, MODEL).dropna()
    act = _col(_portfolio(lbx, MODEL, inputs, h), "active")
    pl = lbx.loc[lbx["p"].notna()]
    block: dict[str, Any] = {
        "rank_ic_mean": _num(ic.mean()) if len(ic) else None,
        "hac_t": _num(metrics.hac_t(ic, h)),
        "net_monthly_pct": _mean_pct(act),
        "n_dates": int(len(ic)),
        "ece_lockbox": metrics.ece_bins(pl["p"], pl["top"]) if len(pl) else None,
        "n_eff_lockbox": len(pl) / h if len(pl) else None,
        "bss_ci95_lockbox": list(metrics.bss_ci(pl["p"], pl["top"], cal.base_rate, pl.index.get_level_values(0), h))
        if len(pl) and cal.base_rate is not None else [None, None],
    }
    block = jsonable(block)
    opened_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    registry.append_lockbox({
        "procedure_id": config.PROCEDURE_ID, "horizon": h, "config_sha256": config.config_sha256(),
        "git_sha": sha, "data_sha256": inputs.data_sha256, "opened_at": opened_at,
        "result_sha256": hashlib.sha256(registry.canonical_json(block)).hexdigest(),
    }, rc.data_dir, dev=rc.dev, result=block)
    return {**block, "opened_at": opened_at}, lbx


# ── production artefact ─────────────────────────────────────────────────────


def model_id_for(rc: RunConfig, data_sha256: str) -> str:
    mid = f"{config.PROCEDURE_ID}-h{rc.horizon}-{data_sha256[:8]}-{config.config_sha256()[:8]}"
    return mid + ("-fast" if rc.fast else "")


def train_production(
    inputs: Inputs, preds: pd.DataFrame, rc: RunConfig, mdir: Path, gate: Mapping[str, Any], sha: str,
) -> str:
    """Boosters on every complete-label session, the production calibrator and the manifest."""
    h = rc.horizon
    cal = inputs.sessions
    n = len(cal)
    lo = int(cal.searchsorted(pd.DatetimeIndex([rc.dates["train_start"]]))[0])
    train_idx = np.arange(lo, n - h, dtype=np.int64)  # i + h <= n - 1
    inner_train, inner_val = _inner_split(train_idx, h, config.EMBARGO)
    d = inputs.design
    sess = d["sess"].to_numpy()
    y = d["rank"].to_numpy(dtype=float)
    mi, mv, mt = (_rows(sess, a) for a in (inner_train, inner_val, train_idx))
    trained = lgbm.train_procedure(
        d.loc[mi, FEATS], y[mi], sess[mi], d.loc[mv, FEATS], y[mv], d.loc[mt, FEATS], y[mt], sess[mt],
        seeds=rc.seeds, max_rounds=rc.max_rounds,
    )
    for t in trained:
        registry.write_atomic(mdir / registry.booster_name(t.seed), t.booster.model_to_string().encode("utf-8"))
    # The latest 36 months of out-of-sample (and opened lockbox) predictions with ended labels.
    after_last = pd.Timestamp(cast(Any, preds["label_end"].max())) + pd.Timedelta(days=1)
    calibrator = CohortCalibrator.fit(preds, after_last, h)
    registry.write_atomic(mdir / "calibrator.json", registry.canonical_json(jsonable(calibrator.to_json())))
    fields = {
        "model_id": mdir.name,
        "procedure_id": config.PROCEDURE_ID,
        "horizon": h,
        "feature_version": FEATURE_VERSION,
        "features": FEATS,
        "objective": config.LGBM_PARAMS["objective"],
        "metric": config.LGBM_PARAMS["metric"],
        "params": dict(config.LGBM_PARAMS),
        "seeds": [t.seed for t in trained],
        "best_iterations": {str(t.seed): t.best_iteration for t in trained},
        "max_rounds": rc.max_rounds,
        "config_sha256": config.config_sha256(),
        "git_sha": sha,
        "data_sha256": inputs.data_sha256,
        "source": rc.source,
        "universe_id": config.UNIVERSE_ID,
        "universe_quality": inputs.quality,
        "cost_model_version": config.COST_MODEL_VERSION,
        "data_period": f"{_day(cal[0])} to {_day(cal[-1])}",
        "trained_through": _day(cal[-1]),
        "gate_result": {k: gate[k] for k in ("tier", "reason_codes", "probability_display_passed")},
        "fast": rc.fast,
    }
    return registry.write_manifest(mdir, jsonable(fields))


# ── entry points ────────────────────────────────────────────────────────────


def _folds(inputs: Inputs, rc: RunConfig) -> list[Fold]:
    folds = make_walkforward_folds(inputs.sessions, rc.dates, rc.horizon)
    if rc.fast:
        folds = folds[-int(config.FAST["last_folds"]):]
    if not folds:
        raise ValueError("no walk-forward folds: the panel does not cover the OOS window")
    return folds


def run_null_calibration(inputs: Inputs, rc: RunConfig, sha: str) -> dict[str, Any]:
    """5.7: N label-permutation replicates; dev trials only; returns the summary written to disk."""
    folds = _folds(inputs, rc)
    results = []
    for i in range(rc.null_calibration):
        y_perm = permuted_labels(inputs.design, i)
        oos, hashes, _ = walk_forward(inputs, folds, rc, y_perm)
        oos = cross_fit(oos, folds, rc.horizon)
        vj, trial_rows = summarise(oos, inputs, folds, hashes, rc, sha, f"+null{i}")
        registry.append_trial(trial_rows[0], dev=True, data_dir=rc.data_dir)  # the model trial only
        results.append({"replicate": i, "tier": vj["tier"], "mean_ic": vj["rank_ic"]["mean"],
                        "hac_t": vj["rank_ic"]["hac_t"]})
    nc = config.NULL_CALIBRATION
    n_weak = sum(r["tier"] in ("weak_evidence", "validated_edge") for r in results)
    n_val = sum(r["tier"] == "validated_edge" for r in results)
    out = {
        "procedure_id": config.PROCEDURE_ID, "horizon": rc.horizon, "data_sha256": inputs.data_sha256,
        "config_sha256": config.config_sha256(), "replicates": rc.null_calibration, "fast": rc.fast,
        "results": results, "weak_or_better": n_weak, "validated": n_val,
        "passed": n_weak <= nc["max_weak"] and n_val <= nc["max_validated"],
    }
    path = registry.models_dir(rc.data_dir) / "null_calibration" / f"{model_id_for(rc, inputs.data_sha256)}.json"
    registry.write_atomic(path, registry.canonical_json(jsonable(out)))
    return out


def run(rc: RunConfig, panel: pd.DataFrame | None = None) -> dict[str, Any]:
    """One full run; returns ``{model_id, model_dir, tier, reason_codes, manifest_sha256}``."""
    if rc.horizon not in config.HORIZONS:
        raise ValueError(f"horizon must be one of {config.HORIZONS}")
    if rc.null_calibration and (rc.open_lockbox or rc.train_production):
        raise ValueError("--null-calibration cannot be combined with --open-lockbox or --train-production")
    check_lockbox(rc)  # before any compute
    sha = git_sha()
    inputs = build_inputs(rc, panel)
    if rc.null_calibration:
        out = run_null_calibration(inputs, rc, sha)
        return {"null_calibration": out}

    mid = model_id_for(rc, inputs.data_sha256)
    mdir = registry.model_dir(mid, rc.data_dir)
    if (mdir / registry.MANIFEST).exists():  # never rewrite files a manifest binds
        raise ValueError(f"artefact {mid} already has a manifest; refusing to overwrite it")
    lockbox = None if rc.open_lockbox else recorded_lockbox(rc)  # before any compute
    folds = _folds(inputs, rc)
    oos, hashes, _ = walk_forward(inputs, folds, rc)
    oos = cross_fit(oos, folds, rc.horizon)
    lbx = None
    if rc.open_lockbox:
        lockbox, lbx = open_lockbox(inputs, oos, rc, sha)
    suffix = "+fast" if rc.fast else ""
    vj, trial_rows = summarise(oos, inputs, folds, hashes, rc, sha, suffix, lockbox)
    for row in trial_rows:
        registry.append_trial(row, dev=rc.dev, data_dir=rc.data_dir)

    gate = {"horizon": rc.horizon, "tier": vj["tier"], "reason_codes": vj["reason_codes"],
            "probability_display_passed": vj["probability_display_passed"], "gates": vj["gates"]}
    registry.write_atomic(mdir / "validation.json", registry.canonical_json(vj))
    registry.write_atomic(mdir / "validation.md", render_markdown(vj).encode("utf-8"))
    registry.write_atomic(mdir / "gate_result.json", registry.canonical_json(gate))
    manifest_sha = None
    if rc.train_production:
        preds = oos if lbx is None else pd.concat([oos, lbx.reindex(columns=oos.columns)])
        manifest_sha = train_production(inputs, preds, rc, mdir, gate, sha)
    return {"model_id": mid, "model_dir": str(mdir), "tier": vj["tier"], "reason_codes": vj["reason_codes"],
            "manifest_sha256": manifest_sha}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m research.train", description="Walk-forward training and validation")
    ap.add_argument("--horizon", type=int, choices=config.HORIZONS, required=True)
    ap.add_argument("--source", choices=("store", "local_csv"), default="store")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--fast", action="store_true", help="dev only: 1 seed, 50 rounds, last 2 folds")
    ap.add_argument("--open-lockbox", action="store_true")
    ap.add_argument("--confirm-config-sha", default=None)
    ap.add_argument("--null-calibration", type=int, default=0, metavar="N")
    ap.add_argument("--train-production", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    rc = RunConfig(
        horizon=args.horizon, source=args.source, data_dir=Path(args.data_dir) if args.data_dir else config.DATA_DIR,
        fast=args.fast, open_lockbox=args.open_lockbox, confirm_config_sha=args.confirm_config_sha,
        null_calibration=max(0, args.null_calibration), train_production=args.train_production,
    )
    try:
        out = run(rc)
    except (LockboxRefused, registry.ArtefactError) as exc:
        print(f"lockbox refused: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"train failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(jsonable(out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
