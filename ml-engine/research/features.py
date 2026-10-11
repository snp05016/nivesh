"""Point-in-time features fv1 (spec 4.2).

Every price feature reads only ``px_idx`` (the forward-chained split/bonus
index, 3.3) on or before t, never a back-adjusted close, so a feature at t is
unchanged when later rows are deleted or rescaled (11.1 no-look-ahead test).
Liquidity features read ``turnover_inr``. Windows count trading sessions of the
panel calendar; a window with less than 80% non-NaN values gives NaN, and NaN
is never zero-filled (LightGBM handles it).

Internally the panel is pivoted to session x entity matrices; every rolling
statistic is a prefix computation down each entity column.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from . import config
from .config import FEATURE_VERSION

__all__ = [
    "DISPLAY_ORIENTATION",
    "FEATURES",
    "FEATURE_VERSION",
    "cached_raw",
    "compute_raw",
    "rank",
    "universe_pct",
    "universe_wide",
]

FEATURES: dict[str, str] = {
    "mom_12_1": "momentum",
    "mom_6_1": "momentum",
    "mom_3_1": "momentum",
    "mom_12_1_vs": "momentum",
    "dist_52wh": "momentum",
    "rev_5": "reversal",
    "rev_21": "reversal",
    "vol_21": "risk",
    "vol_63": "risk",
    "vol_252": "risk",
    "beta_252": "risk",
    "idio_vol_63": "risk",
    "max_ret_21": "risk",
    "downside_vol_63": "risk",
    "log_adv_63": "liquidity",
    "amihud_63": "liquidity",
    "turnover_ratio_21_126": "liquidity",
    "ma50_ma200": "trend",
    "rsi_14": "trend",
}

# +1: a higher raw value reads as "more" of the family label (4.8); -1 flips it
# so the percentile follows the displayed number (higher liquidity, recent rise).
DISPLAY_ORIENTATION: dict[str, int] = {
    f: (-1 if f in ("amihud_63", "rev_5", "rev_21") else 1) for f in FEATURES
}

ANNUALISE = math.sqrt(config.RISK["annualisation_days"])
RSI_PERIOD = 14
_COVERAGE = config.FEATURE_RULES["min_window_coverage"]


def _min_obs(window: int) -> int:
    """Smallest count meeting the 80% coverage rule (round() guards 0.8*w float error)."""
    return math.ceil(round(_COVERAGE * window, 9))


def _roll(frame: pd.DataFrame, window: int, stat: str) -> pd.DataFrame:
    """``frame.rolling(window).<stat>()`` with the 80% coverage rule as min_periods."""
    return cast(pd.DataFrame, getattr(frame.rolling(window, min_periods=_min_obs(window)), stat)())


def _ufunc(fn: Callable[[np.ndarray], np.ndarray], frame: pd.DataFrame) -> pd.DataFrame:
    """Apply a numpy function cell-wise, keeping the frame's labels."""
    return pd.DataFrame(fn(frame.to_numpy(dtype=float)), index=frame.index, columns=frame.columns)


def universe_wide(membership: pd.DataFrame, dates: pd.Index, entities: pd.Index) -> pd.DataFrame:
    """Boolean session x entity matrix of U_t; a missing membership row means not in U_t."""
    mem = membership.loc[membership["in_universe"].astype(bool), ["date", "entity_id"]]
    flag = pd.Series(True, index=pd.MultiIndex.from_frame(mem)).unstack("entity_id")
    return flag.reindex(index=dates, columns=entities).notna()


def _market_return(r: pd.DataFrame, in_u: pd.DataFrame) -> pd.Series:
    """m_t: equal-weight mean of r over U_t.

    math.fsum is exactly rounded, so m_t does not depend on summation order or on
    which other (all-NaN) entity columns the matrix happens to hold.
    """
    vals = r.to_numpy()
    mask = in_u.to_numpy() & ~np.isnan(vals)
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        row = vals[i, mask[i]]
        if row.size:
            out[i] = math.fsum(row.tolist()) / row.size
    return pd.Series(out, index=r.index)


def _masked(values: pd.DataFrame, valid: pd.DataFrame) -> pd.DataFrame:
    return values.where(valid)


def _beta_dimson(r: pd.DataFrame, m: pd.Series, window: int) -> pd.DataFrame:
    """Rolling OLS r_t = a + b0*m_t + b1*m_{t-1}; returns b0 + b1 (Dimson, one lag)."""
    m0 = pd.DataFrame(np.repeat(m.to_numpy()[:, None], r.shape[1], axis=1), index=r.index, columns=r.columns)
    m1 = m0.shift(1)
    valid = r.notna() & m0.notna() & m1.notna()
    y, x0, x1 = _masked(r, valid), _masked(m0, valid), _masked(m1, valid)

    def s(frame: pd.DataFrame) -> pd.DataFrame:
        return _roll(frame, window, "sum")

    n = _roll(valid.astype(float).where(valid), window, "count")
    sy, s0, s1 = s(y), s(x0), s(x1)
    c00 = s(x0 * x0) - s0 * s0 / n
    c11 = s(x1 * x1) - s1 * s1 / n
    c01 = s(x0 * x1) - s0 * s1 / n
    c0y = s(x0 * y) - s0 * sy / n
    c1y = s(x1 * y) - s1 * sy / n
    det = c00 * c11 - c01 * c01
    beta = ((c11 * c0y - c01 * c1y) + (c00 * c1y - c01 * c0y)) / det
    return cast(pd.DataFrame, beta.where((n >= _min_obs(window)) & (det > 0)))


def _idio_vol(r: pd.DataFrame, m: pd.Series, window: int) -> pd.DataFrame:
    """Annualised sample std (ddof=1) of the residuals of rolling OLS r = a + b*m."""
    x_full = pd.DataFrame(np.repeat(m.to_numpy()[:, None], r.shape[1], axis=1), index=r.index, columns=r.columns)
    valid = r.notna() & x_full.notna()
    y, x = _masked(r, valid), _masked(x_full, valid)

    def s(frame: pd.DataFrame) -> pd.DataFrame:
        return _roll(frame, window, "sum")

    n = _roll(valid.astype(float).where(valid), window, "count")
    sy, sx = s(y), s(x)
    sxx = s(x * x) - sx * sx / n
    syy = s(y * y) - sy * sy / n
    sxy = s(x * y) - sx * sy / n
    ssr = (syy - sxy * sxy / sxx).clip(lower=0.0)
    vol = _ufunc(np.sqrt, ssr / (n - 1)) * ANNUALISE
    return cast(pd.DataFrame, vol.where((n >= _min_obs(window)) & (sxx > 0)))


def _rsi_wilder(px: pd.DataFrame, period: int = RSI_PERIOD) -> pd.DataFrame:
    """Wilder RSI on each column's sequence of valid px (NaN days are skipped, MATH-23).

    The first average is the simple mean of the first ``period`` changes, then
    avg = (avg*(period-1) + x)/period. NaN until ``period + 1`` observations;
    100 when the average loss is zero.
    """
    vals = px.to_numpy(dtype=float)
    n_rows, n_cols = vals.shape
    out = np.full_like(vals, np.nan)
    last = np.full(n_cols, np.nan)
    n_changes = np.zeros(n_cols, dtype=np.int64)
    sum_g = np.zeros(n_cols)
    sum_l = np.zeros(n_cols)
    avg_g = np.full(n_cols, np.nan)
    avg_l = np.full(n_cols, np.nan)
    for i in range(n_rows):
        p = vals[i]
        valid = ~np.isnan(p)
        step = valid & ~np.isnan(last)
        d = np.where(step, p - last, 0.0)
        gain, loss = np.maximum(d, 0.0), np.maximum(-d, 0.0)
        n_changes += step
        seed = step & (n_changes <= period)
        sum_g[seed] += gain[seed]
        sum_l[seed] += loss[seed]
        first = step & (n_changes == period)
        avg_g[first] = sum_g[first] / period
        avg_l[first] = sum_l[first] / period
        smooth = step & (n_changes > period)
        avg_g[smooth] = (avg_g[smooth] * (period - 1) + gain[smooth]) / period
        avg_l[smooth] = (avg_l[smooth] * (period - 1) + loss[smooth]) / period
        last[valid] = p[valid]
        ready = valid & (n_changes >= period)
        with np.errstate(divide="ignore", invalid="ignore"):
            rsi = np.where(avg_l > 0, 100.0 - 100.0 / (1.0 + avg_g / avg_l), 100.0)
        out[i, ready] = rsi[ready]
    return pd.DataFrame(out, index=px.index, columns=px.columns)


def compute_raw(panel: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    """Raw fv1 features for every panel row (in or out of the universe).

    ``panel`` follows 3.3 (one row per date, entity_id; ``px_idx`` NaN on
    non-traded or suspect days); ``membership`` is ``universe.membership``
    output (date, entity_id, in_universe). U_t only enters through the
    equal-weight market return m_t used by beta_252 and idio_vol_63.

    Returns float64 columns in ``FEATURES`` order, indexed (date, entity_id),
    sorted by date then entity_id.
    """
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()), name="date")
    entities = pd.Index(sorted(panel["entity_id"].unique()), name="entity_id")

    def wide(col: str) -> pd.DataFrame:
        return (
            panel.pivot(index="date", columns="entity_id", values=col)
            .reindex(index=dates, columns=entities)
            .astype(float)
        )

    px = wide("px_idx")
    px = px.where(px > 0)
    turnover = wide("turnover_inr")
    turnover = turnover.where(turnover > 0)
    in_u = universe_wide(membership, dates, entities)

    log_px = _ufunc(np.log, px)
    r = log_px - log_px.shift(1)  # NaN on and after a skipped (non-traded/suspect) day
    m = _market_return(r, in_u)

    feats: dict[str, pd.DataFrame] = {}
    for name, back in (("mom_12_1", 252), ("mom_6_1", 126), ("mom_3_1", 63)):
        feats[name] = log_px.shift(21) - log_px.shift(back)
    for w in (21, 63, 252):
        feats[f"vol_{w}"] = _roll(r, w, "std") * ANNUALISE
    feats["mom_12_1_vs"] = feats["mom_12_1"] / feats["vol_252"]
    feats["dist_52wh"] = px / _roll(px, 252, "max") - 1.0
    feats["rev_5"] = -(log_px - log_px.shift(5))
    feats["rev_21"] = -(log_px - log_px.shift(21))
    feats["beta_252"] = _beta_dimson(r, m, 252)
    feats["idio_vol_63"] = _idio_vol(r, m, 63)
    feats["max_ret_21"] = _roll(r, 21, "max")
    feats["downside_vol_63"] = _ufunc(np.sqrt, _roll(r.clip(upper=0.0) ** 2, 63, "mean")) * ANNUALISE
    feats["log_adv_63"] = _ufunc(np.log, _roll(turnover, 63, "median"))
    illiq = _roll(_ufunc(np.expm1, r).abs() / turnover, 63, "mean")
    feats["amihud_63"] = _ufunc(np.log, 1e9 * illiq.where(illiq > 0))
    feats["turnover_ratio_21_126"] = _roll(turnover, 21, "median") / _roll(turnover, 126, "median") - 1.0
    feats["ma50_ma200"] = _roll(px, 50, "mean") / _roll(px, 200, "mean") - 1.0
    feats["rsi_14"] = _rsi_wilder(px)

    # Gather the panel's own (date, entity_id) cells from each matrix.
    keys = panel.loc[:, ["date", "entity_id"]].sort_values(by=["date", "entity_id"])
    ri = dates.get_indexer(keys["date"])
    ci = entities.get_indexer(keys["entity_id"])
    out = pd.DataFrame(
        {name: feats[name].to_numpy(dtype=float)[ri, ci] for name in FEATURES},
        index=pd.MultiIndex.from_frame(keys.reset_index(drop=True)),
    )
    # inf only arises from degenerate inputs (e.g. a zero vol_252); it is not a value.
    return out.replace([np.inf, -np.inf], np.nan)


def universe_pct(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Mid-rank percentile in (0, 1) of each value against the non-NaN reference.

    (count below + 0.5 * count equal) / n, which equals (rank - 0.5)/n with
    average ties for a value that is itself in the reference, and places an
    off-universe value against the universe distribution. NaN stays NaN.
    """
    ref = np.sort(reference[~np.isnan(reference)])
    values = np.asarray(values, dtype=float)
    out = np.full(values.shape, np.nan)
    if ref.size == 0:
        return out
    ok = ~np.isnan(values)
    lo = np.searchsorted(ref, values[ok], side="left")
    hi = np.searchsorted(ref, values[ok], side="right")
    out[ok] = (lo + 0.5 * (hi - lo)) / ref.size
    return out


def rank(raw: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    """Per-date cross-sectional ranks scaled to (-1, 1): 2 * pct - 1 within U_t.

    Each date uses only that date's universe values; off-universe rows are
    placed against the universe distribution. NaN stays NaN.
    """
    mem = membership.loc[membership["in_universe"].astype(bool), ["date", "entity_id"]]
    in_u = raw.index.isin(pd.MultiIndex.from_frame(mem))
    values = raw.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)
    codes = raw.index.get_level_values("date")
    for _, pos in pd.Series(np.arange(len(raw)), index=codes).groupby(level=0, sort=False):
        idx = pos.to_numpy()
        ref_rows = idx[in_u[idx]]
        for j in range(values.shape[1]):
            out[idx, j] = universe_pct(values[idx, j], values[ref_rows, j])
    return pd.DataFrame(2.0 * out - 1.0, index=raw.index, columns=raw.columns)


def cached_raw(
    panel: pd.DataFrame,
    membership: pd.DataFrame,
    data_sha256: str,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """compute_raw behind the ``features/{data_sha8}_fv1.parquet`` cache (3.7, 2.5).

    ``data_sha256`` is ``marketdata.data_sha256(panel)``; membership is a pure
    function of the same data, so the data hash and FEATURE_VERSION key the cache.
    """
    path = Path(data_dir or config.DATA_DIR) / "features" / f"{data_sha256[:8]}_{FEATURE_VERSION}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    raw = compute_raw(panel, membership)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    raw.to_parquet(tmp)
    os.replace(tmp, path)
    return raw
