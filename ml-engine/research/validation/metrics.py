"""Validation metrics (spec 5.4). numpy/scipy only; pure functions.

Conventions:
- Daily series are pandas Series indexed by session date; NaN entries (dates
  with fewer than ``min_names``) are dropped before any statistic.
- ``h`` is the label horizon in sessions; overlapping h-session labels make the
  daily series autocorrelated up to lag h-1, hence the HAC long-run variance.
- Bootstrap CIs are circular block bootstraps (block 2h daily, 3 monthly),
  2000 reps, seed 20261010, percentile intervals.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import stats

from .. import config
from .folds import cscv_blocks

FloatArray = npt.NDArray[np.float64]
EULER_GAMMA = 0.5772156649015329
_BOOT = config.BOOTSTRAP


def _clean(x: Any) -> FloatArray:
    a = np.asarray(x, dtype=np.float64).ravel()
    return a[np.isfinite(a)]


# ── RankIC ──────────────────────────────────────────────────────────────────


def rank_ic_daily(
    score: pd.Series, y: pd.Series, min_names: int = config.METRICS["min_names_per_date"]
) -> pd.Series:
    """Spearman(score, y) per date; NaN where fewer than ``min_names`` complete pairs.

    Both inputs are indexed by (date, entity_id); level 0 is the date. Ties take
    average ranks, so this equals ``scipy.stats.spearmanr`` date by date.
    """
    df = pd.DataFrame({"s": score, "y": y})
    dates = df.index.get_level_values(0).unique().sort_values()
    df = df.dropna()
    g = df.groupby(level=0, sort=True)
    ranks = g.rank(method="average")
    n = g["s"].transform("size")
    centre = (n + 1.0) / 2.0  # mean of average ranks is always (n+1)/2
    rs, ry = ranks["s"] - centre, ranks["y"] - centre
    level = df.index.get_level_values(0)
    num = (rs * ry).groupby(level).sum()
    den = np.sqrt((rs * rs).groupby(level).sum() * (ry * ry).groupby(level).sum())
    count = g.size()
    ic = (num / den).where((count >= min_names) & (den > 0))
    return ic.reindex(dates).rename("rank_ic")


# ── Long-run variance and HAC t ─────────────────────────────────────────────


def _autocov(x: FloatArray, max_lag: int) -> FloatArray:
    """gamma_0..gamma_max_lag of the demeaned series, divisor T."""
    t = len(x)
    d = x - x.mean()
    out = np.zeros(max_lag + 1)
    for k in range(min(max_lag, t - 1) + 1):
        out[k] = float(np.dot(d[k:], d[: t - k])) / t
    return out


def lrv_hansen_hodrick(x: Any, h: int) -> float:
    """Uniform kernel over lags 1..h-1: gamma_0 + 2 * sum gamma_k (may be <= 0)."""
    a = _clean(x)
    g = _autocov(a, max(0, h + config.HAC["max_lag_offset"]))
    return float(g[0] + 2.0 * g[1:].sum())


def lrv_bartlett(x: Any, lags: int) -> float:
    """Newey-West: gamma_0 + 2 * sum_{k=1..L} (1 - k/(L+1)) gamma_k (always >= 0)."""
    a = _clean(x)
    g = _autocov(a, lags)
    w = 1.0 - np.arange(1, lags + 1) / (lags + 1.0)
    return float(g[0] + 2.0 * np.dot(w, g[1:]))


def lrv(x: Any, h: int) -> float:
    """Hansen-Hodrick LRV to lag h-1, falling back to Bartlett at L = 4h when HH <= 0."""
    v = lrv_hansen_hodrick(x, h)
    if v > 0:
        return v
    return lrv_bartlett(x, config.HAC["fallback_lag_multiple"] * h)


def hac_t(x: Any, h: int) -> float:
    """mean / sqrt(LRV / T); NaN with fewer than 2 observations or a zero LRV."""
    a = _clean(x)
    if len(a) < 2:
        return math.nan
    v = lrv(a, h)
    if not v > 0:
        return math.nan
    return float(a.mean() / math.sqrt(v / len(a)))


def nonoverlap_t(x: Any, h: int) -> FloatArray:
    """Plain t of every h-th observation, for each of the h offsets (NaN when undefined)."""
    a = _clean(x)
    out = np.full(h, np.nan)
    for o in range(h):
        sub = a[o::h]
        if len(sub) >= 2:
            sd = sub.std(ddof=1)
            if sd > 0:
                out[o] = sub.mean() / (sd / math.sqrt(len(sub)))
    return out


def t_star(x: Any, h: int) -> float:
    """min(HAC t on the daily series, median over offsets of the non-overlapping t) (0.4, 5.4)."""
    nt = nonoverlap_t(x, h)
    med = float(np.nanmedian(nt)) if np.isfinite(nt).any() else math.nan
    ht = hac_t(x, h)
    if not (math.isfinite(ht) and math.isfinite(med)):
        return math.nan  # fail closed: t* is undefined unless both parts are
    return min(ht, med)


def icir_ann(x: Any, h: int) -> float:
    """mean/sd of non-overlapping IC x sqrt(252/h); the median over the h offsets."""
    a = _clean(x)
    vals = []
    for o in range(h):
        sub = a[o::h]
        if len(sub) >= 2 and sub.std(ddof=1) > 0:
            vals.append(sub.mean() / sub.std(ddof=1))
    if not vals:
        return math.nan
    return float(np.median(vals) * math.sqrt(252.0 / h))


def paired_ic_test(ic_model: pd.Series, ic_base: pd.Series, h: int) -> dict[str, float]:
    """HAC t of the daily IC difference on common dates: ``{delta_ic, t}``."""
    d = (ic_model - ic_base).dropna()
    return {"delta_ic": float(d.mean()) if len(d) else math.nan, "t": hac_t(d, h)}


def vs_best_baseline(
    ic_model: pd.Series,
    baseline_ics: Mapping[str, pd.Series],
    h: int,
    candidates: Sequence[str] = ("B3", "B4", "B5", "B6", "B7", "B8"),
) -> dict[str, Any]:
    """Paired test against the best of B3-B8 by mean IC, chosen after the fact (G2)."""
    means = {b: float(baseline_ics[b].mean()) for b in candidates if b in baseline_ics}
    means = {b: m for b, m in means.items() if math.isfinite(m)}
    if not means:
        return {"baseline": None, "delta_ic": math.nan, "t": math.nan}
    best = max(means, key=lambda b: means[b])
    return {"baseline": best, **paired_ic_test(ic_model, baseline_ics[best], h)}


# ── Bootstrap ───────────────────────────────────────────────────────────────


def block_bootstrap_indices(
    n: int, block: int, reps: int = _BOOT["reps"], seed: int = _BOOT["seed"]
) -> npt.NDArray[np.int64]:
    """(reps, n) circular-block resample indices into a series of length n."""
    block = max(1, min(block, n))
    n_blocks = -(-n // block)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(reps, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(reps, n_blocks * block)[:, :n]


def block_bootstrap_ci(
    x: Any,
    block: int,
    reps: int = _BOOT["reps"],
    seed: int = _BOOT["seed"],
    alpha: float = 0.05,
    stat: Callable[[FloatArray], FloatArray] | None = None,
) -> tuple[float, float]:
    """Percentile CI of ``stat`` (default the mean) under a circular block bootstrap.

    ``stat`` receives a (reps, n) array and must reduce along axis 1.
    """
    a = _clean(x)
    if len(a) < 2:
        return (math.nan, math.nan)
    draws = a[block_bootstrap_indices(len(a), block, reps, seed)]
    vals = stat(draws) if stat is not None else draws.mean(axis=1)
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return (float(lo), float(hi))


def daily_block(h: int) -> int:
    return config.BOOTSTRAP["daily_block_multiple"] * h


# ── Probability metrics ─────────────────────────────────────────────────────


def brier(p: Any, y: Any) -> float:
    p_, y_ = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    return float(np.mean((p_ - y_) ** 2))


def bss(p: Any, y: Any, base_rate: Any) -> float:
    """1 - Brier(p) / Brier(ex-ante base rate); ``base_rate`` is a scalar or per-row array."""
    y_ = np.asarray(y, dtype=float)
    ref = brier(np.broadcast_to(np.asarray(base_rate, dtype=float), y_.shape), y_)
    return float(1.0 - brier(p, y_) / ref) if ref > 0 else math.nan


def bss_ci(
    p: Any, y: Any, base_rate: Any, dates: Any, h: int,
    reps: int = _BOOT["reps"], seed: int = _BOOT["seed"],
) -> tuple[float, float]:
    """BSS CI from a circular block bootstrap over dates (block 2h)."""
    y_ = np.asarray(y, dtype=float)
    p_ = np.asarray(p, dtype=float)
    b_ = np.broadcast_to(np.asarray(base_rate, dtype=float), y_.shape)
    codes, _ = pd.factorize(pd.Index(dates), sort=True)
    n_dates = int(codes.max()) + 1 if len(codes) else 0
    if n_dates < 2:
        return (math.nan, math.nan)
    se = np.bincount(codes, weights=(p_ - y_) ** 2, minlength=n_dates)
    sr = np.bincount(codes, weights=(b_ - y_) ** 2, minlength=n_dates)
    idx = block_bootstrap_indices(n_dates, daily_block(h), reps, seed)
    with np.errstate(divide="ignore", invalid="ignore"):
        vals = 1.0 - se[idx].sum(axis=1) / sr[idx].sum(axis=1)
    lo, hi = np.nanquantile(vals, [0.025, 0.975])
    return (float(lo), float(hi))


def log_loss(p: Any, y: Any, eps: float = 1e-15) -> float:
    p_ = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    y_ = np.asarray(y, dtype=float)
    return float(-np.mean(y_ * np.log(p_) + (1 - y_) * np.log(1 - p_)))


def auc(score: Any, y: Any, weight: Any | None = None) -> float:
    """Tie-aware (half credit) Mann-Whitney AUC with optional row weights."""
    s = np.asarray(score, dtype=float)
    y_ = np.asarray(y, dtype=float)
    w = np.ones_like(s) if weight is None else np.asarray(weight, dtype=float)
    _, inv = np.unique(s, return_inverse=True)
    return _auc_grouped(inv, y_, w)


def _auc_grouped(inv: npt.NDArray[np.intp], y: FloatArray, w: FloatArray) -> float:
    m = int(inv.max()) + 1 if len(inv) else 0
    pos = np.bincount(inv, weights=w * y, minlength=m)
    neg = np.bincount(inv, weights=w * (1.0 - y), minlength=m)
    big_p, big_n = pos.sum(), neg.sum()
    if big_p <= 0 or big_n <= 0:
        return math.nan
    below = np.cumsum(neg) - neg
    return float(np.dot(pos, below + 0.5 * neg) / (big_p * big_n))


def auc_by_year(
    score: Any, y: Any, dates: Any, h: int,
    reps: int = _BOOT["reps"], seed: int = _BOOT["seed"],
) -> dict[str, dict[str, Any]]:
    """Per calendar year: ``{year: {auc, ci95, n}}``; the CI resamples dates in blocks of 2h."""
    s = np.asarray(score, dtype=float)
    y_ = np.asarray(y, dtype=float)
    d = pd.DatetimeIndex(dates)
    out: dict[str, dict[str, Any]] = {}
    years = d.to_series().dt.year.to_numpy()
    for year in sorted(set(years.tolist())):
        m = years == year
        sy, yy = s[m], y_[m]
        codes, _ = pd.factorize(d[m], sort=True)
        n_dates = int(codes.max()) + 1
        _, inv = np.unique(sy, return_inverse=True)
        point = _auc_grouped(inv, yy, np.ones_like(sy))
        vals = np.empty(reps)
        for r, row in enumerate(block_bootstrap_indices(n_dates, daily_block(h), reps, seed)):
            w = np.bincount(row, minlength=n_dates)[codes].astype(float)
            vals[r] = _auc_grouped(inv, yy, w)
        lo, hi = np.nanquantile(vals, [0.025, 0.975])
        out[str(year)] = {"auc": point, "ci95": [float(lo), float(hi)], "n": int(m.sum())}
    return out


def ece_bins(p: Any, y: Any, n_bins: int = config.METRICS["ece_bins"]) -> float:
    """Expected calibration error over equal-count bins of p (stable sort)."""
    p_ = np.asarray(p, dtype=float)
    y_ = np.asarray(y, dtype=float)
    if len(p_) == 0:
        return math.nan
    order = np.argsort(p_, kind="stable")
    total = 0.0
    for b in np.array_split(order, n_bins):
        if len(b):
            total += len(b) * abs(p_[b].mean() - y_[b].mean())
    return float(total / len(p_))


def hit_rate_directional(
    rank_pct: Any, top: Any, dates: Any, h: int, neutral: Any | None = None,
    reps: int = _BOOT["reps"], seed: int = _BOOT["seed"],
) -> dict[str, Any]:
    """Share of rows where (rank_pct > 0.5) matches the realised top half.

    Rows in a neutral bucket (``neutral`` True) or exactly at 0.5 are excluded.
    ``n_eff = n / h``; the CI block-bootstraps the daily hit-rate series.
    """
    r = np.asarray(rank_pct, dtype=float)
    t = np.asarray(top, dtype=float)
    keep = np.isfinite(r) & np.isfinite(t) & (r != 0.5)
    if neutral is not None:
        keep &= ~np.asarray(neutral, dtype=bool)
    hit = ((r[keep] > 0.5) == (t[keep] > 0.5)).astype(float)
    n = int(keep.sum())
    if n == 0:
        return {"value": math.nan, "ci95": [math.nan, math.nan], "n": 0, "n_eff": 0.0}
    daily = pd.Series(hit, index=pd.DatetimeIndex(dates)[keep]).groupby(level=0).mean()
    lo, hi = block_bootstrap_ci(np.asarray(daily, dtype=float), daily_block(h), reps, seed)
    return {"value": float(hit.mean()), "ci95": [lo, hi], "n": n, "n_eff": n / h}


# ── Deflated Sharpe ratio (Bailey and Lopez de Prado 2014) ─────────────────


def expected_max_sr(sr_var: float, n_trials: int) -> float:
    """SR0 = sqrt(V) * ((1 - g) * Phi^-1(1 - 1/N) + g * Phi^-1(1 - 1/(N e)))."""
    n = float(n_trials)
    return float(
        math.sqrt(sr_var)
        * ((1 - EULER_GAMMA) * stats.norm.ppf(1 - 1 / n) + EULER_GAMMA * stats.norm.ppf(1 - 1 / (n * math.e)))
    )


def dsr_from_moments(
    sr: float, sr_var: float, n_trials: int, t: int, skew: float, kurt: float
) -> float:
    """DSR = Phi((SR - SR0) sqrt(T-1) / sqrt(1 - g3 SR + (g4 - 1)/4 SR^2)); kurt is non-excess."""
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if t < 2 or not denom > 0:
        return math.nan
    sr0 = expected_max_sr(sr_var, n_trials)
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(t - 1) / math.sqrt(denom)))


def dsr(monthly_series: Any, trial_monthly_srs: Any) -> float:
    """DSR in monthly units (5.4): non-annualised SR, monthly skew and kurtosis, T = months.

    ``trial_monthly_srs`` are the monthly SRs of every trial for this horizon
    (TRIALS.jsonl). N is floored at ``MIN_DSR_TRIALS`` so a short ledger never
    understates multiplicity; V is the sample variance of the trial SRs.
    """
    x = _clean(monthly_series)
    trials = _clean(trial_monthly_srs)
    if len(x) < 3 or len(trials) < 2 or not x.std(ddof=1) > 0:
        return math.nan
    sr = float(x.mean() / x.std(ddof=1))
    n = max(len(trials), config.MIN_DSR_TRIALS)
    return dsr_from_moments(
        sr,
        float(trials.var(ddof=1)),
        n,
        len(x),
        float(stats.skew(x)),
        float(stats.kurtosis(x, fisher=False)),
    )


# ── PBO via CSCV (Bailey, Borwein, Lopez de Prado and Zhu 2017) ────────────


def pbo_cscv(perf: Any, s: int = config.METRICS["cscv_blocks"]) -> float:
    """Probability of backtest overfitting over all C(s, s/2) splits.

    ``perf`` is a (T, N) matrix of per-period returns, one column per trial. In
    every split the in-sample best trial (by Sharpe) gets its out-of-sample rank
    omega = rank / (N + 1); PBO is the share of splits with logit(omega) <= 0.
    """
    m = np.asarray(perf, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        raise ValueError("perf must be a (T, N>=2) matrix")
    blocks = cscv_blocks(m.shape[0], s)
    cnt = np.array([len(b) for b in blocks], dtype=float)
    s1 = np.stack([m[b].sum(axis=0) for b in blocks])
    s2 = np.stack([(m[b] ** 2).sum(axis=0) for b in blocks])
    combos = np.array(
        [[1.0 if j in c else 0.0 for j in range(s)] for c in itertools.combinations(range(s), s // 2)]
    )

    def sharpe(c: FloatArray) -> FloatArray:
        n = (c @ cnt)[:, None]
        mean = (c @ s1) / n
        var = ((c @ s2) - n * mean**2) / (n - 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            sr = mean / np.sqrt(var)
        return np.nan_to_num(sr, nan=-np.inf)

    sr_is, sr_oos = sharpe(combos), sharpe(1.0 - combos)
    best = np.argmax(sr_is, axis=1)
    best_oos = sr_oos[np.arange(len(best)), best]
    rank = (sr_oos < best_oos[:, None]).sum(axis=1) + 1
    omega = rank / (m.shape[1] + 1.0)
    logit = np.log(omega / (1.0 - omega))
    return float(np.mean(logit <= 0))
