"""Descriptive risk metrics and historical return ranges (spec 4.5, 4.6, D11, D30).

Everything here is computed from one entity's forward-chained, split- and
bonus-adjusted ``px_idx`` (D35); dividends are excluded. Nothing is a forecast:
volatility, VaR and drawdowns describe the past, and the return range is the
stock's own historical distribution (no conformal method, ACI or coverage
figure, D11).

Session arithmetic counts rows of the entity panel (one row per session the
entity appears in, ``px_idx`` NaN on non-traded or suspect days). Daily returns
across a NaN close are NaN, so a skipped close drops both adjacent returns.

Public entry points: :func:`risk_block` (the whole ``contract.Risk``) and
:func:`return_range_block`; the pure helpers (:func:`hist_var_cvar`,
:func:`kupiec_pof`, :func:`christoffersen_ind`, :func:`dimson_beta`,
:func:`max_drawdown_pct`) are exposed for tests and reuse.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import lfilter
from scipy.special import xlogy
from scipy.stats import chi2

from .config import RANGES, RISK
from .contract import (
    Beta,
    Drawdown,
    DrawdownSeries,
    Fact,
    ReasonCode,
    ReturnRange,
    Risk,
    VarBacktest,
    VarRow,
)
from .formatting import make_fact, range_text

ANN = math.sqrt(RISK["annualisation_days"])
SESSIONS_PER_YEAR = RISK["annualisation_days"]
RANGE_METHOD: Literal["empirical_rolling_756d"] = "empirical_rolling_756d"
BETA_METHOD: Literal["dimson_lag1_daily_252"] = "dimson_lag1_daily_252"
EWMA_METHOD = f"ewma_{RISK['ewma_lambda']}"
BLUME_METHOD = f"blume_{RISK['blume_weights'][0]}"
EWMA_SEED_RETURNS = 30  # the EWMA variance starts at the mean square of the first 30 returns
MIN_EWMA_RETURNS = 63  # fewer valid returns -> EWMA volatility unavailable
MIN_WINDOW_SHARE = 0.8  # a realised-vol window needs this share of valid returns (as fv1)

VarMethod = Literal["historical_500d", "fhs_ewma"]


# ── Return series ───────────────────────────────────────────────────────────


def simple_returns(px: np.ndarray) -> np.ndarray:
    """r_t = px_t / px_{t-1} - 1 on consecutive rows; NaN wherever either close is NaN."""
    px = np.asarray(px, dtype=float)
    out = np.full(px.shape, np.nan)
    if px.size > 1:
        out[1:] = px[1:] / px[:-1] - 1.0
    return out


def _day_index(values: Any) -> pd.DatetimeIndex:
    """Dates truncated to the day (timezone-naive), as a DatetimeIndex."""
    return pd.DatetimeIndex(np.asarray(pd.to_datetime(values), dtype="datetime64[D]"))


def _last_date(days: pd.DatetimeIndex) -> date:
    return np.asarray(days, dtype="datetime64[D]")[-1].astype(object)


def _log_returns(px: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.log1p(simple_returns(px))


# ── Volatility ──────────────────────────────────────────────────────────────


def ewma_variance(r: np.ndarray, lam: float = RISK["ewma_lambda"]) -> np.ndarray:
    """RiskMetrics variance forecasts for a NaN-free return array.

    Returns ``n + 1`` values: element t is the forecast for r[t] made from
    r[:t] (zero mean), element n the forecast for the next session. The
    recursion is seeded with the mean square of the first 30 returns.
    """
    r = np.asarray(r, dtype=float)
    seed = float(np.mean(r[: min(EWMA_SEED_RETURNS, r.size)] ** 2)) if r.size else float("nan")
    # s2[t+1] = lam * s2[t] + (1 - lam) * r[t]^2, with s2[0] = seed.
    tail, _ = lfilter([1.0 - lam], [1.0, -lam], r**2, zi=[lam * seed])
    return np.concatenate([[seed], tail])


def realised_vol_pct(log_r: np.ndarray, window: int) -> float | None:
    """Annualised std (ddof 1) of the last ``window`` log returns, in %, or None."""
    if log_r.size < window:
        return None
    w = log_r[-window:]
    w = w[np.isfinite(w)]
    if w.size < max(2, math.ceil(MIN_WINDOW_SHARE * window)):
        return None
    return float(np.std(w, ddof=1) * ANN * 100.0)


def percentile_of(value: float, population: np.ndarray) -> float:
    """Mid-rank percentile (0-100) of ``value`` within ``population``: (rank - 0.5) / n for a member."""
    less = float(np.sum(population < value))
    equal = float(np.sum(population == value))
    return 100.0 * (less + 0.5 * equal) / population.size


def _fact(fid: str, value: float | None, as_of: date | None, *, method: str | None = None,
          reason: ReasonCode = "insufficient_history") -> Fact:
    """Catalogue fact from computed data; ``reason`` applies only when the value is missing."""
    missing = value is None or not math.isfinite(value)
    return make_fact(fid, value, source="computed", as_of=as_of, method=method,
                     reason=reason if missing else None)


# ── VaR, CVaR and backtests ─────────────────────────────────────────────────


def hist_var_cvar(returns: np.ndarray, level: float) -> tuple[float, float]:
    """Historical one-day VaR and CVaR as (negative) returns.

    VaR is the (1 - level) quantile with numpy linear interpolation; CVaR is the
    mean of the returns at or below it.
    """
    r = np.asarray(returns, dtype=float)
    var = float(np.quantile(r, 1.0 - level))
    return var, float(r[r <= var].mean())


def kupiec_pof(exceptions: int, n: int, p: float) -> tuple[float, float]:
    """Kupiec proportion-of-failures likelihood ratio and its chi2(1) p-value."""
    x = exceptions
    phat = x / n
    ll_null = xlogy(n - x, 1.0 - p) + xlogy(x, p)
    ll_alt = xlogy(n - x, 1.0 - phat) + xlogy(x, phat)
    lr = max(0.0, float(-2.0 * (ll_null - ll_alt)))
    return lr, float(chi2.sf(lr, 1))


def christoffersen_ind(hits: np.ndarray) -> tuple[float, float]:
    """Christoffersen (1998) independence LR on a 0/1 exception sequence, with p-value."""
    h = np.asarray(hits, dtype=int)
    prev, cur = h[:-1], h[1:]
    n00 = int(np.sum((prev == 0) & (cur == 0)))
    n01 = int(np.sum((prev == 0) & (cur == 1)))
    n10 = int(np.sum((prev == 1) & (cur == 0)))
    n11 = int(np.sum((prev == 1) & (cur == 1)))
    total = n00 + n01 + n10 + n11
    if total == 0 or n01 + n11 == 0:
        return 0.0, 1.0
    pi = (n01 + n11) / total
    pi0 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi1 = n11 / (n10 + n11) if n10 + n11 else 0.0
    ll_null = xlogy(n00 + n10, 1.0 - pi) + xlogy(n01 + n11, pi)
    ll_alt = xlogy(n00, 1.0 - pi0) + xlogy(n01, pi0) + xlogy(n10, 1.0 - pi1) + xlogy(n11, pi1)
    lr = max(0.0, float(-2.0 * (ll_null - ll_alt)))
    return lr, float(chi2.sf(lr, 1))


def _var_forecasts(r: np.ndarray, level: float, method: VarMethod) -> tuple[np.ndarray, float, float]:
    """One-step-ahead VaR for each of the last ``backtest`` returns, plus today's VaR and CVaR.

    ``r`` is NaN-free and holds at least window + backtest returns.
    """
    window, backtest = RISK["hist_window_days"], RISK["backtest_window_days"]
    q = 1.0 - level
    n = r.size
    if method == "historical_500d":
        windows = sliding_window_view(r[:-1], window)[-backtest:]  # row k ends just before r[n-backtest+k]
        forecasts = np.quantile(windows, q, axis=1)
        var, cvar = hist_var_cvar(r[-window:], level)
        return forecasts, var, cvar
    sigma = np.sqrt(ewma_variance(r))
    z = r / sigma[:n]
    z_windows = sliding_window_view(z[:-1], window)[-backtest:]
    forecasts = sigma[n - backtest:n] * np.quantile(z_windows, q, axis=1)
    zq, zcvar = hist_var_cvar(z[-window:], level)
    return forecasts, float(sigma[n] * zq), float(sigma[n] * zcvar)


def _is_green(level: float, exceptions: int, kupiec_p: float, christoffersen_p: float) -> bool:
    if christoffersen_p < RISK["christoffersen_p_min"]:
        return False
    if level >= 0.99:
        return exceptions <= RISK["var99_max_exceptions"]
    return kupiec_p >= RISK["kupiec_p_min"]


def var_block(
    r_simple: np.ndarray, as_of: date | None
) -> tuple[Literal["ok", "backtest_failed", "unavailable"], list[VarRow]]:
    """Historical-500d and FHS-EWMA VaR/CVaR with the 250-day backtest; green rows only (D30)."""
    r = r_simple[np.isfinite(r_simple)]
    backtest = RISK["backtest_window_days"]
    if r.size < RISK["hist_window_days"] + backtest:
        return "unavailable", []
    realised = r[-backtest:]
    rows: list[VarRow] = []
    for level in RISK["var_levels"]:
        for method in RISK["var_methods"]:
            forecasts, var, cvar = _var_forecasts(r, level, method)
            hits = (realised < forecasts).astype(int)
            exceptions = int(hits.sum())
            _, kp = kupiec_pof(exceptions, backtest, 1.0 - level)
            _, cp = christoffersen_ind(hits)
            if not _is_green(level, exceptions, kp, cp):
                continue
            base = f"risk.var_1d.{round(level * 100)}.{method}."
            rows.append(VarRow(
                level=level, method=method,
                var_pct=_fact(base + "var_pct", var * 100.0, as_of, method=method),
                cvar_pct=_fact(base + "cvar_pct", cvar * 100.0, as_of, method=method),
                backtest=VarBacktest(
                    window_days=backtest, exceptions=exceptions, expected=round(backtest * (1.0 - level), 4),
                    kupiec_p=round(kp, 4), christoffersen_p=round(cp, 4),
                ),
            ))
    return ("ok" if rows else "backtest_failed"), rows


# ── Beta ────────────────────────────────────────────────────────────────────


def dimson_beta(r: np.ndarray, m: np.ndarray, m_lag: np.ndarray) -> tuple[float, float]:
    """OLS of r on [1, m, m_lag]; returns (b0 + b1, its standard error from the OLS covariance)."""
    x = np.column_stack([np.ones_like(m), m, m_lag])
    coef, _, _, _ = np.linalg.lstsq(x, r, rcond=None)
    resid = r - x @ coef
    dof = r.size - x.shape[1]
    cov = (resid @ resid / dof) * np.linalg.inv(x.T @ x)
    var_sum = cov[1, 1] + cov[2, 2] + 2.0 * cov[1, 2]
    return float(coef[1] + coef[2]), float(math.sqrt(max(var_sum, 0.0)))


def _beta_inputs(dates: pd.DatetimeIndex, r_stock: np.ndarray,
                 index_series: pd.Series) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Align the last 252 stock sessions with same-day and previous-session index returns."""
    idx = index_series.astype(float).copy()
    idx.index = _day_index(idx.index)
    idx = idx.loc[~idx.index.duplicated(keep="last")].sort_index()
    m = idx / idx.shift(1) - 1.0  # NaN across a missing index close (no fill)
    frame = pd.DataFrame({"m": m, "m_lag": m.shift(1)})
    window = RISK["beta_window_days"]
    stock = pd.Series(r_stock[-window:], index=dates[-window:])
    joined = frame.reindex(stock.index).assign(r=stock).dropna()
    return joined["r"].to_numpy(), joined["m"].to_numpy(), joined["m_lag"].to_numpy()


def beta_block(dates: pd.DatetimeIndex, r_stock: np.ndarray, index_series: pd.Series | None,
               as_of: date | None) -> Beta:
    reason: ReasonCode = "insufficient_history"
    raw = se = None
    if index_series is None or index_series.dropna().empty:
        reason = "source_unavailable"
    else:
        r, m, m_lag = _beta_inputs(dates, r_stock, index_series)
        if r.size >= RISK["beta_min_pairs"]:
            raw, se = dimson_beta(r, m, m_lag)
    w_beta, w_one = RISK["blume_weights"]
    blume = None if raw is None else w_beta * raw + w_one

    return Beta(
        benchmark_id="NIFTY50_PR", method=BETA_METHOD,
        raw=_fact("risk.beta.raw", raw, as_of, method=BETA_METHOD, reason=reason),
        se=_fact("risk.beta.se", se, as_of, method=BETA_METHOD, reason=reason),
        blume_adjusted=_fact("risk.beta.blume_adjusted", blume, as_of, method=BLUME_METHOD, reason=reason),
    )


# ── Drawdowns ───────────────────────────────────────────────────────────────


def _underwater(px: np.ndarray) -> np.ndarray:
    """px / running max - 1 over the given path (NaN closes stay NaN and do not set peaks)."""
    s = pd.Series(np.asarray(px, dtype=float))
    return (s / s.cummax() - 1.0).to_numpy()


def max_drawdown_pct(px: np.ndarray) -> float | None:
    """Largest peak-to-trough fall within the path, in % (<= 0), or None without two valid closes."""
    if np.sum(np.isfinite(px)) < 2:
        return None
    return float(np.nanmin(_underwater(px)) * 100.0)


def drawdown_blocks(dates: pd.DatetimeIndex, px: np.ndarray,
                    as_of: date | None) -> tuple[Drawdown, DrawdownSeries]:
    """Windowed maximum drawdowns, plus current state and weekly series within the longest window.

    max_{N}y is the peak-to-trough fall inside the last N years (252 N sessions;
    unavailable with less history). The current drawdown, sessions since the
    peak and the weekly series use peaks inside the last 5 years (or the whole
    history when shorter), so ``current_pct >= max_5y_pct`` always holds and
    the values do not depend on how far back the data starts.
    """
    n = px.size

    def fact(fid: str, value: float | None) -> Fact:
        return _fact(fid, value, as_of)

    maxima: dict[int, float | None] = {}
    for years in RISK["drawdown_years"]:
        w = years * SESSIONS_PER_YEAR
        maxima[years] = max_drawdown_pct(px[-w:]) if n >= w else None

    lookback = max(RISK["drawdown_years"]) * SESSIONS_PER_YEAR
    path_px = px[-lookback:]
    under = _underwater(path_px)
    valid = np.flatnonzero(np.isfinite(under))
    current = days = None
    if valid.size >= 2:
        last = int(valid[-1])
        current = float(under[last] * 100.0)
        peak_pos = int(np.flatnonzero(path_px[: last + 1] == np.nanmax(path_px[: last + 1]))[-1])
        days = float(path_px.size - 1 - peak_pos)

    ulcer = None
    w1 = RISK["ulcer_years"] * SESSIONS_PER_YEAR
    if n >= w1:
        dd = _underwater(px[-w1:]) * 100.0
        dd = dd[np.isfinite(dd)]
        if dd.size >= 2:
            ulcer = float(math.sqrt(np.mean(dd**2)))

    drawdown = Drawdown(
        max_1y_pct=fact("risk.drawdown.max_1y_pct", maxima[1]),
        max_3y_pct=fact("risk.drawdown.max_3y_pct", maxima[3]),
        max_5y_pct=fact("risk.drawdown.max_5y_pct", maxima[5]),
        current_pct=fact("risk.drawdown.current_pct", current),
        days_since_peak=fact("risk.drawdown.days_since_peak", days),
        ulcer_1y=fact("risk.drawdown.ulcer_1y", ulcer),
    )

    points: list[tuple[date, float]] = []
    if valid.size >= 2:
        series = pd.Series(under * 100.0, index=dates[-lookback:]).dropna()
        weekly = series.groupby(pd.DatetimeIndex(series.index).to_period("W-FRI")).tail(1)
        weekly = weekly.iloc[-min(RISK["drawdown_series_weeks"], RISK["drawdown_series_max_points"]):]
        points = [(ts.date(), round(float(v), 2)) for ts, v in weekly.items()]
    return drawdown, DrawdownSeries(freq="W", unit="pct", points=points)


# ── Historical return ranges (4.5) ──────────────────────────────────────────


def rolling_returns(px: np.ndarray, h: int, window: int) -> np.ndarray:
    """R_s = px_s / px_{s-h} - 1 for every s in the last ``window`` rows (NaN-free)."""
    px = np.asarray(px, dtype=float)
    n = px.size
    s = np.arange(max(h, n - window), n)
    out = px[s] / px[s - h] - 1.0
    return out[np.isfinite(out)]


def return_range_block(px_idx: pd.Series | np.ndarray, h: int, as_of: date | None = None) -> ReturnRange:
    """The stock's own 10th-90th percentile range of rolling h-session returns (4.5, D11).

    Uses the last 756 sessions (window_sessions = min(756, sessions available));
    with fewer than 252 sessions both ends are unavailable (insufficient_history).
    ``as_of`` defaults to the last index date when ``px_idx`` is date-indexed.
    """
    if as_of is None and isinstance(px_idx, pd.Series) and isinstance(px_idx.index, pd.DatetimeIndex) \
            and len(px_idx):
        as_of = _last_date(_day_index(px_idx.index))
    px = np.asarray(px_idx, dtype=float)
    window = min(RANGES["window_sessions"], px.size)
    low = high = None
    if px.size >= RANGES["min_sessions"]:
        rets = rolling_returns(px, h, window)
        if rets.size:
            low = float(np.percentile(rets, RANGES["low_quantile"] * 100.0) * 100.0)
            high = float(np.percentile(rets, RANGES["high_quantile"] * 100.0) * 100.0)
    low_f = _fact(f"risk.range.{h}.low_pct", low, as_of, method=RANGE_METHOD)
    high_f = _fact(f"risk.range.{h}.high_pct", high, as_of, method=RANGE_METHOD)
    return ReturnRange(
        horizon_days=h,  # type: ignore[arg-type]  # 21 or 63 (validated by the contract)
        low_pct=low_f, high_pct=high_f, window_sessions=window,
        text=range_text(h, window, low_f, high_f), method=RANGE_METHOD,
    )


# ── Assembly ────────────────────────────────────────────────────────────────


def risk_block(
    entity_panel: pd.DataFrame,
    index_series: pd.Series | None,
    universe_vol_pct: Sequence[float] | np.ndarray | pd.Series | None,
) -> Risk:
    """The ``contract.Risk`` block for one entity.

    Args:
        entity_panel: the entity's panel rows (spec 3.3) up to and including
            as-of; needs ``date`` and ``px_idx``. Sorted here by date.
        index_series: Nifty 50 price-index closes indexed by date (``load_index``),
            or None when unavailable (beta is then unavailable).
        universe_vol_pct: 252-session annualised volatility in % (the same
            quantity as ``vol_252d_ann_pct``) of every universe member on the
            as-of date; ``vol_pctl`` places this stock against it. None or empty
            gives an unavailable percentile.
    """
    panel = entity_panel.sort_values("date")
    dates = _day_index(panel["date"])
    px = panel["px_idx"].to_numpy(dtype=float)
    as_of: date | None = _last_date(dates) if len(dates) else None
    r_simple = simple_returns(px)
    log_r = _log_returns(px)

    valid_log = log_r[np.isfinite(log_r)]
    vol_ewma = (float(math.sqrt(ewma_variance(valid_log)[-1]) * ANN * 100.0)
                if valid_log.size >= MIN_EWMA_RETURNS else None)
    short_w, long_w = RISK["vol_windows"]
    vol_63 = realised_vol_pct(log_r, short_w)
    vol_252 = realised_vol_pct(log_r, long_w)

    pctl: float | None = None
    pctl_reason: ReasonCode = "source_unavailable"
    universe = np.asarray([] if universe_vol_pct is None else universe_vol_pct, dtype=float)
    universe = universe[np.isfinite(universe)]
    if vol_252 is None:
        pctl_reason = "insufficient_history"
    elif universe.size:
        pctl = percentile_of(vol_252, universe)

    var_status, var_rows = var_block(r_simple, as_of)
    drawdown, series = drawdown_blocks(dates, px, as_of)

    return Risk(
        vol_ewma_ann_pct=_fact("risk.vol_ewma_ann_pct", vol_ewma, as_of, method=EWMA_METHOD),
        vol_63d_ann_pct=_fact("risk.vol_63d_ann_pct", vol_63, as_of),
        vol_252d_ann_pct=_fact("risk.vol_252d_ann_pct", vol_252, as_of),
        vol_pctl=_fact("risk.vol_pctl", pctl, as_of, reason=pctl_reason),
        beta=beta_block(dates, r_simple, index_series, as_of),
        var_status=var_status,
        var_1d=var_rows,
        drawdown=drawdown,
        drawdown_series=series,
        return_ranges=[return_range_block(px, h, as_of) for h in (21, 63)],
    )

