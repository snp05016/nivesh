"""Validation statistics for the Lab: CV splits, multiple testing, data-snooping tests,
calibration, conformal intervals and Sharpe inference.

Pure numpy/scipy and deterministic given ``seed``. Walk-forward folds, CSCV/PBO, HAC t,
circular block bootstrap, Brier/AUC/ECE and the deflated Sharpe ratio already live in
``research.validation`` and are reused, not reimplemented.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from itertools import combinations
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from scipy import stats

from research.validation.metrics import expected_max_sr

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]
Split = tuple[IntArray, IntArray]


# ── Purged cross-validation (Lopez de Prado 2018, AFML ch. 7 and 12) ────────


def _purged_train(n: int, test_blocks: Sequence[IntArray], h: int, embargo: int) -> IntArray:
    """Indices whose label window [i, i+h] misses every test block and its embargo tail."""
    keep = np.ones(n, dtype=bool)
    for b in test_blocks:
        keep[max(0, int(b[0]) - h): min(n, int(b[-1]) + embargo + 1)] = False
    return np.flatnonzero(keep).astype(np.int64)


def purged_kfold(n: int, k: int, label_horizon: int, embargo: int = 0) -> list[Split]:
    """K contiguous test blocks; training drops rows labelled into a block, plus an embargo after it.

    AFML ch. 7: row i's label spans [i, i+h], so a training row is purged when
    i is in [test_start - h, test_end]; the embargo also drops (test_end, test_end + embargo].
    """
    if not 2 <= k <= n:
        raise ValueError("need 2 <= k <= n")
    blocks = [b.astype(np.int64) for b in np.array_split(np.arange(n), k)]
    return [(_purged_train(n, [b], label_horizon, embargo), b) for b in blocks]


def cpcv_splits(
    n: int, n_groups: int, k_test: int, label_horizon: int, embargo: int = 0
) -> tuple[list[Split], int]:
    """Combinatorial purged CV (AFML ch. 12): every C(N, k) choice of k test groups.

    Each test group is purged/embargoed separately, so the train set can sit between
    test groups. Returns the splits and the number of backtest paths phi = k/N * C(N, k).
    """
    if not 1 <= k_test < n_groups <= n:
        raise ValueError("need 1 <= k_test < n_groups <= n")
    groups = [g.astype(np.int64) for g in np.array_split(np.arange(n), n_groups)]
    splits = []
    for combo in combinations(range(n_groups), k_test):
        test = [groups[g] for g in combo]
        splits.append((_purged_train(n, test, label_horizon, embargo), np.concatenate(test)))
    n_paths = k_test * math.comb(n_groups, k_test) // n_groups
    return splits, n_paths


# ── Multiple testing ────────────────────────────────────────────────────────


def _pvals(pvals: Any) -> FloatArray:
    p = np.asarray(pvals, dtype=np.float64).ravel()
    if not np.all((p >= 0) & (p <= 1)):
        raise ValueError("p-values must lie in [0, 1]")
    return p


def holm(pvals: Any, alpha: float = 0.05) -> tuple[FloatArray, BoolArray]:
    """Holm (1979) step-down FWER adjustment: max_{j<=i} (m - j + 1) p_(j)."""
    p = _pvals(pvals)
    m = len(p)
    order = np.argsort(p, kind="stable")
    adj_sorted = np.minimum(1.0, np.maximum.accumulate((m - np.arange(m)) * p[order]))
    adj = np.empty(m)
    adj[order] = adj_sorted
    return adj, adj <= alpha


def benjamini_hochberg(pvals: Any, q: float = 0.05) -> tuple[FloatArray, BoolArray]:
    """Benjamini and Hochberg (1995) step-up FDR adjustment: min_{j>=i} m p_(j) / j."""
    p = _pvals(pvals)
    m = len(p)
    order = np.argsort(p, kind="stable")
    raw = p[order] * m / np.arange(1, m + 1)
    adj_sorted = np.minimum(1.0, np.minimum.accumulate(raw[::-1])[::-1])
    adj = np.empty(m)
    adj[order] = adj_sorted
    return adj, adj <= q


def benjamini_yekutieli(pvals: Any, q: float = 0.05) -> tuple[FloatArray, BoolArray]:
    """Benjamini and Yekutieli (2001): BH scaled by c(m) = sum 1/i, valid under any dependence."""
    p = _pvals(pvals)
    c = float(np.sum(1.0 / np.arange(1, len(p) + 1)))
    adj, _ = benjamini_hochberg(np.minimum(1.0, p * c), q)
    adj = np.minimum(1.0, adj)
    return adj, adj <= q


# ── Stationary bootstrap (Politis and Romano 1994) ──────────────────────────


def stationary_bootstrap_indices(n: int, mean_block: float, reps: int, seed: int) -> IntArray:
    """(reps, n) resample indices: geometric block lengths with mean ``mean_block``, wrapping circularly."""
    if n < 1 or mean_block < 1:
        raise ValueError("need n >= 1 and mean_block >= 1")
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(reps, n))
    new = rng.random((reps, n)) < 1.0 / mean_block
    new[:, 0] = True
    t = np.arange(n)
    last = np.maximum.accumulate(np.where(new, t, 0), axis=1)  # position where the current block began
    return ((np.take_along_axis(starts, last, axis=1) + t - last) % n).astype(np.int64)


def stationary_bootstrap_ci(
    x: Any,
    stat: Callable[[FloatArray], FloatArray] | None = None,
    mean_block: float = 10.0,
    reps: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile CI of ``stat`` (default the mean) under the stationary bootstrap.

    ``stat`` receives a (reps, n) array and must reduce along axis 1.
    """
    a = np.asarray(x, dtype=np.float64).ravel()
    a = a[np.isfinite(a)]
    if len(a) < 2:
        return (math.nan, math.nan)
    draws = a[stationary_bootstrap_indices(len(a), mean_block, reps, seed)]
    vals = stat(draws) if stat is not None else draws.mean(axis=1)
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return (float(lo), float(hi))


# ── Data-snooping tests: White RC, Hansen SPA, Romano-Wolf ─────────────────


def _boot_means(d: FloatArray, mean_block: float, reps: int, seed: int) -> FloatArray:
    """(reps, M) column means of stationary-bootstrap resamples, via resample counts (no (reps, T, M) cube)."""
    t = d.shape[0]
    idx = stationary_bootstrap_indices(t, mean_block, reps, seed)
    flat = (idx + (np.arange(reps) * t)[:, None]).ravel()
    counts = np.bincount(flat, minlength=reps * t).reshape(reps, t).astype(np.float64)
    return (counts @ d) / t


def _excess(excess_returns: Any) -> FloatArray:
    d = np.asarray(excess_returns, dtype=np.float64)
    if d.ndim == 1:
        d = d[:, None]
    if d.ndim != 2 or d.shape[0] < 2 or not np.isfinite(d).all():
        raise ValueError("excess_returns must be a finite (T>=2, M) array")
    return d


def white_reality_check(
    excess_returns: Any, reps: int = 2000, mean_block: float = 10.0, seed: int = 0
) -> float:
    """White (2000) Reality Check p-value for H0: no strategy beats the benchmark.

    V = max_k sqrt(T) dbar_k; bootstrap V* = max_k sqrt(T) (dbar*_k - dbar_k), the
    least-favourable recentring (every mean set to zero), so poor strategies inflate V*.
    """
    d = _excess(excess_returns)
    rt = math.sqrt(d.shape[0])
    dbar = d.mean(axis=0)
    v = rt * dbar.max()
    v_star = rt * (_boot_means(d, mean_block, reps, seed) - dbar).max(axis=1)
    return float(np.mean(v_star >= v))


def _studentised(d: FloatArray, reps: int, mean_block: float, seed: int) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Means, bootstrap means and omega_k = bootstrap sd of sqrt(T) dbar*_k (Hansen 2005 sec. 2.4)."""
    dbar = d.mean(axis=0)
    boot = _boot_means(d, mean_block, reps, seed)
    omega = math.sqrt(d.shape[0]) * boot.std(axis=0, ddof=1)
    omega = np.where(omega > 0, omega, np.inf)  # a constant column can never be "best"
    return dbar, boot, omega


def hansen_spa(
    excess_returns: Any, reps: int = 2000, mean_block: float = 10.0, seed: int = 0
) -> float:
    """Hansen (2005) consistent SPA p-value (studentised, g_c recentring).

    Strategies with sqrt(T) dbar_k / omega_k < -sqrt(2 log log T) keep their negative
    mean in the bootstrap, so clearly poor strategies stop diluting the test.
    """
    d = _excess(excess_returns)
    t = d.shape[0]
    rt = math.sqrt(t)
    dbar, boot, omega = _studentised(d, reps, mean_block, seed)
    t_spa = max(0.0, float(np.max(rt * dbar / omega)))
    thresh = -math.sqrt(2.0 * math.log(math.log(t))) if t > math.e else -np.inf
    mu_c = np.where(rt * dbar / omega >= thresh, dbar, 0.0)
    t_star = np.maximum(0.0, (rt * (boot - mu_c) / omega).max(axis=1))
    return float(np.mean(t_star >= t_spa))


def romano_wolf_stepdown(
    excess_returns: Any, reps: int = 2000, mean_block: float = 10.0, seed: int = 0
) -> FloatArray:
    """Romano and Wolf (2005) step-down adjusted p-values, one per strategy (H0_k: mean <= 0).

    Studentised statistics are taken in descending order; step j compares t_(j) with the
    bootstrap max over the strategies not yet rejected; p-values are made monotone.
    Controls FWER while using the dependence between strategies.
    """
    d = _excess(excess_returns)
    rt = math.sqrt(d.shape[0])
    dbar, boot, omega = _studentised(d, reps, mean_block, seed)
    t_obs = rt * dbar / omega
    t_null = rt * (boot - dbar) / omega
    order = np.argsort(-t_obs, kind="stable")
    # tail_max[:, j] = max over the j-th..last strategies in descending-t order
    tail_max = np.maximum.accumulate(t_null[:, order][:, ::-1], axis=1)[:, ::-1]
    p_sorted = np.maximum.accumulate(np.mean(tail_max >= t_obs[order], axis=0))
    out = np.empty(len(order))
    out[order] = p_sorted
    return out


# ── Calibration ─────────────────────────────────────────────────────────────


def wilson_interval(k: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson (1927) score interval for a binomial proportion k/n."""
    if n <= 0:
        return (math.nan, math.nan)
    z = float(stats.norm.ppf(1 - alpha / 2))
    ph = k / n
    den = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / den
    half = z / den * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def reliability_diagram(
    p: Any,
    y: Any,
    n_bins: int = 10,
    strategy: Literal["quantile", "uniform"] = "quantile",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Reliability bins with Wilson CIs, ECE and MCE (Naeini, Cooper and Hauskrecht 2015).

    ``quantile`` uses equal-count bins of sorted p (same as ``metrics.ece_bins``);
    ``uniform`` uses equal-width bins on [0, 1]. Empty bins are dropped.
    Returns ``{bins: [{lo, hi, n, mean_p, freq, ci_lo, ci_hi}], ece, mce}``.
    """
    p_ = np.asarray(p, dtype=np.float64).ravel()
    y_ = np.asarray(y, dtype=np.float64).ravel()
    if p_.shape != y_.shape or len(p_) == 0:
        raise ValueError("p and y must be non-empty and the same length")
    if strategy == "quantile":
        members = np.array_split(np.argsort(p_, kind="stable"), n_bins)
        edges = [(float(p_[m].min()), float(p_[m].max())) if len(m) else (math.nan, math.nan) for m in members]
    elif strategy == "uniform":
        e = np.linspace(0.0, 1.0, n_bins + 1)
        which = np.clip(np.searchsorted(e, p_, side="right") - 1, 0, n_bins - 1)
        members = [np.flatnonzero(which == b) for b in range(n_bins)]
        edges = [(float(e[b]), float(e[b + 1])) for b in range(n_bins)]
    else:
        raise ValueError(f"unknown strategy {strategy!r}")
    bins = []
    ece, mce = 0.0, 0.0
    for m, (lo, hi) in zip(members, edges):
        if len(m) == 0:
            continue
        mean_p, freq = float(p_[m].mean()), float(y_[m].mean())
        ci_lo, ci_hi = wilson_interval(float(y_[m].sum()), len(m), alpha)
        gap = abs(freq - mean_p)
        ece += len(m) * gap
        mce = max(mce, gap)
        bins.append({"lo": lo, "hi": hi, "n": int(len(m)), "mean_p": mean_p, "freq": freq, "ci_lo": ci_lo, "ci_hi": ci_hi})
    return {"bins": bins, "ece": ece / len(p_), "mce": mce}


# ── Conformal intervals and proper scoring of intervals/quantiles ───────────


def split_conformal_interval(residuals_calib: Any, alpha: float) -> float:
    """Split-conformal half-width (Vovk et al. 2005; Lei et al. 2018).

    The ceil((n+1)(1-alpha))-th smallest |residual|; infinite when that rank exceeds n,
    which is what guarantees finite-sample coverage >= 1 - alpha on exchangeable data.
    """
    r = np.sort(np.abs(np.asarray(residuals_calib, dtype=np.float64).ravel()))
    n = len(r)
    k = math.ceil((n + 1) * (1 - alpha))
    return math.inf if k > n else float(r[k - 1])


def conformal_coverage(y: Any, lo: Any, hi: Any) -> float:
    """Share of y inside [lo, hi]."""
    y_ = np.asarray(y, dtype=np.float64)
    return float(np.mean((y_ >= np.asarray(lo)) & (y_ <= np.asarray(hi))))


def weighted_quantile_loss(y: Any, q_preds: Mapping[float, Any]) -> float:
    """Pinball loss rho_tau(y - q) = max(tau (y - q), (tau - 1)(y - q)), averaged over rows and quantiles.

    (Koenker and Bassett 1978; equally weighted across the quantile levels given.)
    """
    y_ = np.asarray(y, dtype=np.float64)
    losses = []
    for tau, q in q_preds.items():
        if not 0 < tau < 1:
            raise ValueError("quantile levels must be in (0, 1)")
        u = y_ - np.asarray(q, dtype=np.float64)
        losses.append(np.mean(np.maximum(tau * u, (tau - 1) * u)))
    return float(np.mean(losses))


def interval_score(y: Any, lo: Any, hi: Any, alpha: float) -> float:
    """Gneiting and Raftery (2007) interval score for a central (1 - alpha) interval (lower is better)."""
    y_ = np.asarray(y, dtype=np.float64)
    l_, h_ = np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64)
    s = (h_ - l_) + (2 / alpha) * (l_ - y_) * (y_ < l_) + (2 / alpha) * (y_ - h_) * (y_ > h_)
    return float(np.mean(s))


# ── Sharpe ratio inference ──────────────────────────────────────────────────


def _sr_denom(sr: float, skew: float, kurt: float) -> float:
    return 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr


def sharpe_ci(returns: Any, periods_per_year: int = 252, alpha: float = 0.05) -> dict[str, float]:
    """Annualised Sharpe with a normal CI from the Mertens (2002) standard error.

    Per-period SE = sqrt((1 - g3 SR + (g4 - 1)/4 SR^2) / (T - 1)), which reduces to
    Lo (2002)'s iid sqrt((1 + SR^2/2) / T) for normal returns; kurt is non-excess.
    Annualisation by sqrt(periods_per_year) assumes iid returns.
    """
    x = np.asarray(returns, dtype=np.float64).ravel()
    x = x[np.isfinite(x)]
    nan = {"sr": math.nan, "se": math.nan, "lo": math.nan, "hi": math.nan}
    if len(x) < 3 or not x.std(ddof=1) > 0:
        return nan
    sr = float(x.mean() / x.std(ddof=1))
    var = _sr_denom(sr, float(stats.skew(x)), float(stats.kurtosis(x, fisher=False)))
    if not var > 0:
        return nan
    ann = math.sqrt(periods_per_year)
    se = math.sqrt(var / (len(x) - 1)) * ann
    z = float(stats.norm.ppf(1 - alpha / 2))
    return {"sr": sr * ann, "se": se, "lo": sr * ann - z * se, "hi": sr * ann + z * se}


def probabilistic_sharpe(sr: float, sr_benchmark: float, n: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """PSR = Phi((SR - SR*) sqrt(n - 1) / sqrt(1 - g3 SR + (g4 - 1)/4 SR^2)) (Bailey and Lopez de Prado 2012).

    Per-period (not annualised) SRs; kurt is non-excess. ``metrics.dsr_from_moments`` is
    this with SR* = the expected maximum SR over the trials.
    """
    var = _sr_denom(sr, skew, kurt)
    if n < 2 or not var > 0:
        return math.nan
    return float(stats.norm.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(var)))


def min_backtest_length(n_trials: int, target_sr: float) -> float:
    """MinBTL in years (Bailey, Borwein, Lopez de Prado and Zhu 2014): (E[max_N] / SR)^2.

    E[max_N] is the expected maximum of N standard normals (``metrics.expected_max_sr``
    with unit variance); ``target_sr`` is annualised. One trial needs no deflation: 0.
    """
    if target_sr <= 0:
        raise ValueError("target_sr must be positive")
    if n_trials < 2:
        return 0.0
    return float((expected_max_sr(1.0, n_trials) / target_sr) ** 2)
