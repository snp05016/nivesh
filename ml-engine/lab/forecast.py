"""Calibrated distributional return forecasts, with a walk-forward evaluation that may say "no skill".

Replaces "direction=UP, confidence=0.67" with quantiles, P(return > 0) and conformal intervals.

Target. For a bar date t and horizon h the label is the forward LOG return from the NEXT close:
``y_t = log px_idx[t+1+h] - log px_idx[t+1]`` (``raw``), or that minus the same-date
cross-sectional mean (``rel``). It is realised at the close of t+1+h, so a forecast made at the
close of t may only use labels of dates s <= t-h-1.

Models (each gives quantiles at ``QS`` and P(y > 0)):

- ``climatology``: the stock's own expanding empirical quantiles of past h-returns.
- ``ewma_vol``: zero mean, RiskMetrics EWMA vol (lambda 0.94) x sqrt(h), quantiles from the pooled
  expanding distribution of standardised past labels (filtered historical simulation).
- ``lgbm_quantile``: one LightGBM quantile model per level on a compact FDL feature set, expanding
  window, refit every 63 sessions, train end = refit date - h - 1 - 5 (purge + embargo);
  predicted quantiles are sorted to remove crossing; P(up) is read off the interpolated CDF.

Conformal. Each central 80%/90% interval is widened (never narrowed) by the split-conformal
quantile of the CQR scores max(lo - y, y - hi) of the last ``CAL_BLOCK`` sessions whose labels
are already realised (Romano, Patterson and Candes 2019).

    python -m lab.forecast --source local_csv --out ../docs/platform/experiments/forecast-dev-2026-10-19.json
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
import warnings
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from research.validation.metrics import bss, block_bootstrap_ci, brier, daily_block, hac_t, rank_ic_daily

from .featurelang import compile_program, panel_schema
from .loaders import DEV_WARNINGS
from .stats import conformal_coverage, interval_score, reliability_diagram, split_conformal_interval, weighted_quantile_loss

QS = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
MED = 3
INTERVALS = {0.8: (1, 5), 0.9: (0, 6)}  # level -> (lo, hi) indices into QS
MODELS = ("climatology", "ewma_vol", "lgbm_quantile")
LAMBDA = 0.94
REFIT = 63
EMBARGO = 5
CAL_BLOCK = 63
MIN_HIST = 60  # labels a stock needs before climatology speaks
MIN_POOL = 250  # pooled standardised residuals before ewma_vol speaks
MIN_TRAIN = 500
EWMA_WARMUP = 30
LGBM_PARAMS = dict(
    n_estimators=100, learning_rate=0.05, num_leaves=8, min_child_samples=200, subsample=0.8,
    subsample_freq=1, colsample_bytree=0.8, random_state=0, verbose=-1, deterministic=True, force_col_wise=True,
)
FEATURE_PROGRAM = """
r1 = log(px_idx / lag(px_idx, 1))
ret_5 = log(px_idx / lag(px_idx, 5))
ret_20 = log(px_idx / lag(px_idx, 20))
ret_60 = log(px_idx / lag(px_idx, 60))
vol_20 = std(r1, 20)
vol_60 = std(r1, 60)
volume_z = zscore(log(volume + 1), 60)
dist_52w_high = log(px_idx / max(px_idx, 252))
rk_ret_5 = rank(ret_5)
rk_ret_20 = rank(ret_20)
rk_ret_60 = rank(ret_60)
rk_vol_20 = rank(vol_20)
rk_dist_52w = rank(dist_52w_high)
"""
FEATURES = ["ret_5", "ret_20", "ret_60", "vol_20", "vol_60", "volume_z", "dist_52w_high",
            "rk_ret_5", "rk_ret_20", "rk_ret_60", "rk_vol_20", "rk_dist_52w"]
HISTORICAL_CLAIM = "LightGBM directional hit rate ~ 52.66% vs momentum ~ 52%"


# ── engine ──────────────────────────────────────────────────────────────────


def _entity(panel: pd.DataFrame) -> str:
    return "entity_id" if "entity_id" in panel.columns else "symbol"


def _climatology(Y: np.ndarray, h: int, i0: int, i1: int) -> tuple[np.ndarray, np.ndarray]:
    T, N = Y.shape
    Q, P = np.full((T, N, len(QS)), np.nan), np.full((T, N), np.nan)
    for t in range(i0, i1 + 1):
        hist = Y[: max(0, t - h)]
        n = np.isfinite(hist).sum(0)
        ok = n >= MIN_HIST
        if ok.any():
            Q[t, ok] = np.nanquantile(hist[:, ok], QS, axis=0).T
            P[t, ok] = (hist[:, ok] > 0).sum(0) / n[ok]
    return Q, P


def _riskmetrics(r: np.ndarray) -> np.ndarray:
    """sigma_t known at the close of t (includes r_t); NaN for the first EWMA_WARMUP returns."""
    T, N = r.shape
    s2, cnt, out = np.full(N, np.nan), np.zeros(N), np.full((T, N), np.nan)
    for t in range(T):
        ok = np.isfinite(r[t])
        new = ok & np.isnan(s2)
        s2[new] = r[t, new] ** 2
        upd = ok & ~new
        s2[upd] = LAMBDA * s2[upd] + (1 - LAMBDA) * r[t, upd] ** 2
        cnt[ok] += 1
        out[t] = np.where(cnt >= EWMA_WARMUP, np.sqrt(s2), np.nan)
    return out


def _ewma(r: np.ndarray, Y: np.ndarray, h: int, i0: int, i1: int) -> tuple[np.ndarray, np.ndarray]:
    T, N = Y.shape
    S = _riskmetrics(r) * math.sqrt(h)
    S[S <= 0] = np.nan
    Z = Y / S
    Q, P = np.full((T, N, len(QS)), np.nan), np.full((T, N), np.nan)
    for t in range(i0, i1 + 1):
        z = Z[: max(0, t - h)]
        z = z[np.isfinite(z)]
        if len(z) >= MIN_POOL:
            Q[t] = S[t][:, None] * np.quantile(z, QS)[None, :]
            P[t] = np.where(np.isfinite(S[t]), float(np.mean(z > 0)), np.nan)
    return Q, P


def _p_up(Q: np.ndarray) -> np.ndarray:
    """P(y > 0) from the piecewise-linear CDF through the quantiles (tails clamped half-way to 0/1)."""
    P = np.full(Q.shape[:2], np.nan)
    ok = np.isfinite(Q).all(-1)
    lo, hi = QS[0] / 2, 1 - (1 - QS[-1]) / 2
    P[ok] = [1 - np.interp(0.0, q, QS, left=lo, right=hi) for q in Q[ok]]
    return P


def _features(p: pd.DataFrame, ent: str, dates: pd.Index, ents: pd.Index) -> np.ndarray:
    f = compile_program(FEATURE_PROGRAM, panel_schema()).run(p, entity=ent).set_index(["date", ent])
    return np.stack([f[c].unstack().reindex(index=dates, columns=ents).to_numpy(float) for c in FEATURES], axis=-1)


def _lgbm(X: np.ndarray, Y: np.ndarray, present: np.ndarray, h: int, i0: int, i1: int) -> tuple[np.ndarray, np.ndarray]:
    T, N, F = X.shape
    Q = np.full((T, N, len(QS)), np.nan)
    for b0 in range(i0, i1 + 1, REFIT):
        b1, te = min(b0 + REFIT, i1 + 1), b0 - h - 1 - EMBARGO  # te: last training date (inclusive)
        if te < 0:
            continue
        xtr, ytr = X[: te + 1].reshape(-1, F), Y[: te + 1].ravel()
        m = np.isfinite(ytr) & np.isfinite(xtr[:, 0])
        if m.sum() < MIN_TRAIN:
            continue
        xte = X[b0:b1].reshape(-1, F)
        ok = present[b0:b1].ravel() & np.isfinite(xte[:, 0])
        if not ok.any():
            continue
        jobs = 1 if m.sum() < 50_000 else 4  # threads only pay off on big folds; results are deterministic either way
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # sklearn's feature-name notice for plain arrays
            pred = np.column_stack([
                lgb.LGBMRegressor(objective="quantile", alpha=q, n_jobs=jobs, **LGBM_PARAMS).fit(xtr[m], ytr[m]).predict(xte[ok])
                for q in QS
            ])
        out = np.full((len(ok), len(QS)), np.nan)
        out[ok] = np.sort(pred, axis=1)
        Q[b0:b1] = out.reshape(b1 - b0, N, len(QS))
    return Q, _p_up(Q)


def _conformal(Q: np.ndarray, Y: np.ndarray, h: int, e0: int, i1: int) -> dict[float, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """level -> (lo, hi, widening per date); widening uses only labels realised by t."""
    out = {}
    for level, (a, b) in INTERVALS.items():
        score = np.maximum(Q[..., a] - Y, Y - Q[..., b])
        adj = np.full(len(Y), np.nan)
        for t in range(e0, i1 + 1):
            s = score[max(0, t - h - CAL_BLOCK): max(0, t - h)]
            s = s[np.isfinite(s)]
            if len(s) >= 20:
                adj[t] = split_conformal_interval(np.maximum(s, 0.0), round(1 - level, 2))
        out[level] = (Q[..., a] - adj[:, None], Q[..., b] + adj[:, None], adj)
    return out


def _run(panel: pd.DataFrame, h: int, start: Any, end: Any, target: str, models: tuple[str, ...]) -> dict[str, Any]:
    """Every model's forecasts for dates in [start, end], plus the CAL_BLOCK + h + 1 sessions before (calibration)."""
    if target not in ("raw", "rel"):
        raise ValueError("target must be 'raw' or 'rel'")
    if not set(models) <= set(MODELS):
        raise ValueError(f"models must be drawn from {MODELS}")
    ent = _entity(panel)
    p = panel.loc[(panel["px_idx"] > 0) & (panel["volume"].fillna(0) > 0), ["date", ent, "px_idx", "volume"]].copy()
    p["date"] = pd.to_datetime(p["date"])
    px = p.pivot(index="date", columns=ent, values="px_idx").sort_index().sort_index(axis=1)
    dates, ents = px.index, px.columns
    L = np.log(px.to_numpy(float))
    T, N = L.shape
    present = np.isfinite(L)
    e0 = int(dates.searchsorted(pd.Timestamp(start)))
    i1 = int(dates.searchsorted(pd.Timestamp(end), side="right")) - 1
    if i1 < e0:
        raise ValueError("no sessions between start and end")
    i0 = max(0, e0 - CAL_BLOCK - h - 1)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = np.vstack([np.full((1, N), np.nan), np.diff(L, axis=0)])
        Y = np.full((T, N), np.nan)
        if T > h + 1:
            Y[: T - h - 1] = L[h + 1:] - L[1: T - h]
        mom = np.full((T, N), np.nan)
        mom[h:] = L[h:] - L[:-h]
        mvol = pd.Series(np.nanmean(r, axis=1)).rolling(20).std().to_numpy()
        if target == "rel":
            Y, r, mom = (a - np.nanmean(a, axis=1, keepdims=True) for a in (Y, r, mom))
        Q, P = {}, {}
        for m in models:
            if m == "climatology":
                Q[m], P[m] = _climatology(Y, h, i0, i1)
            elif m == "ewma_vol":
                Q[m], P[m] = _ewma(r, Y, h, i0, i1)
            else:
                Q[m], P[m] = _lgbm(_features(p, ent, dates, ents), Y, present, h, i0, i1)
            Q[m][~present] = np.nan
            P[m][~present] = np.nan
        conf = {m: _conformal(Q[m], Y, h, e0, i1) for m in models}
        pos = np.cumsum((Y > 0).sum(1))
        cnt = np.cumsum(np.isfinite(Y).sum(1))
        base = np.full(T, np.nan)  # ex-ante base rate: share of realised labels > 0 known at t
        base[h + 1:] = (pos / np.maximum(cnt, 1))[: T - h - 1]
    return {"p": p, "ent": ent, "dates": dates, "ents": ents, "Y": Y, "present": present, "Q": Q, "P": P,
            "conf": conf, "base": base, "mom": mom, "mvol": mvol, "e0": e0, "i1": i1, "h": h}


# ── evaluation ──────────────────────────────────────────────────────────────


def _pinball_rows(y: np.ndarray, q: np.ndarray) -> np.ndarray:
    u = y[:, None] - q
    tau = np.asarray(QS)[None, :]
    return np.maximum(tau * u, (tau - 1) * u).mean(1)


def _skill_test(loss_model: pd.Series, loss_clim: pd.Series, h: int) -> dict[str, Any]:
    """Per-date loss differential (climatology - model): HAC t and block-bootstrap CI of its mean."""
    d = (loss_clim - loss_model).dropna().to_numpy()
    lo, hi = block_bootstrap_ci(d, daily_block(h))
    t = hac_t(d, h)
    return {"mean_loss_diff": float(d.mean()) if len(d) else math.nan, "hac_t": t, "ci95": [lo, hi],
            "significant": bool(len(d) >= 20 and lo > 0 and t > 1.96), "n_dates": int(len(d))}


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer, int)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return round(float(x), 6) if math.isfinite(x) else None
    return x


def _provenance(panel: pd.DataFrame) -> dict[str, Any]:
    dev = "source" in panel.columns and bool((panel["source"] == "local_csv").any())
    return {"source": "local_csv" if dev else str(panel["source"].iloc[0]) if "source" in panel.columns and len(panel) else "unknown",
            "warnings": list(DEV_WARNINGS) if dev else [], "rows": int(len(panel)),
            "first": str(pd.Timestamp(panel["date"].min()).date()), "last": str(pd.Timestamp(panel["date"].max()).date())}


def _eval_rows(run: dict[str, Any], models: tuple[str, ...]) -> np.ndarray:
    """Mask of (date, entity) cells in [start, end] with a realised label and every model's forecast."""
    T = len(run["dates"])
    M = np.isfinite(run["Y"]) & (np.arange(T) >= run["e0"])[:, None] & (np.arange(T) <= run["i1"])[:, None]
    for m in models:
        M &= np.isfinite(run["Q"][m]).all(-1)
        for lo, hi, _ in run["conf"][m].values():
            M &= np.isfinite(lo) & np.isfinite(hi)
    return M


def evaluate(panel: pd.DataFrame, h: int, start: Any, end: Any, target: str = "raw",
             models: tuple[str, ...] = MODELS) -> dict[str, Any]:
    """Walk-forward evaluation over [start, end]; JSON-serialisable. Climatology is always included."""
    t0 = time.time()
    models = ("climatology", *[m for m in models if m != "climatology"])
    run = _run(panel, h, start, end, target, models)
    M = _eval_rows(run, models)
    ti, ni = np.nonzero(M)
    y = run["Y"][M]
    dates = run["dates"][ti]
    mi = pd.MultiIndex.from_arrays([dates, run["ents"][ni]])
    yu = (y > 0).astype(float)
    n_ent = len(run["ents"])
    min_names = min(20, max(5, n_ent // 2))
    mv = run["mvol"][ti]
    thresh = float(np.nanmedian(np.unique(mv))) if len(mv) else math.nan
    regimes = {"high_vol": mv > thresh, "low_vol": mv <= thresh}

    def hit(sign_pred: np.ndarray, rows: np.ndarray | slice = slice(None)) -> dict[str, Any]:
        s, yy, dd = sign_pred[rows], y[rows], dates[rows]
        keep = (s != 0) & (yy != 0) & np.isfinite(s)
        h_ = (np.sign(s[keep]) == np.sign(yy[keep])).astype(float)
        daily = pd.Series(h_, index=dd[keep]).groupby(level=0).mean().to_numpy()
        lo, hi = block_bootstrap_ci(daily, daily_block(h))
        return {"hit_rate": float(h_.mean()) if len(h_) else math.nan, "ci95": [lo, hi], "n": int(keep.sum())}

    loss_by_date, out_models = {}, {}
    for m in models:
        q = run["Q"][m][M]
        rows = _pinball_rows(y, q)
        loss_by_date[m] = pd.Series(rows).groupby(ti).mean()
        p = run["P"][m][M]
        rel = reliability_diagram(p, yu, n_bins=10)
        ic = rank_ic_daily(pd.Series(q[:, MED], index=mi), pd.Series(y, index=mi), min_names=min_names).dropna()
        ic_lo, ic_hi = block_bootstrap_ci(ic.to_numpy(), daily_block(h))
        cov, isc = {}, {}
        for level, (a, b) in INTERVALS.items():
            lo_c, hi_c, adj = run["conf"][m][level]
            al = round(1 - level, 2)
            cov[str(level)] = {"raw": conformal_coverage(y, q[:, a], q[:, b]), "conformal": conformal_coverage(y, lo_c[M], hi_c[M]),
                               "mean_widening": float(np.nanmean(adj[run["e0"]: run["i1"] + 1]))}
            isc[str(level)] = {"raw": interval_score(y, q[:, a], q[:, b], al), "conformal": interval_score(y, lo_c[M], hi_c[M], al)}
        reg = {}
        for name, rmask in regimes.items():
            lo80, hi80, _ = run["conf"][m][0.8]
            reg[name] = {"pinball": float(rows[rmask].mean()) if rmask.any() else math.nan,
                         "coverage_80_raw": conformal_coverage(y[rmask], q[rmask, 1], q[rmask, 5]) if rmask.any() else math.nan,
                         "coverage_80_conformal": conformal_coverage(y[rmask], lo80[M][rmask], hi80[M][rmask]) if rmask.any() else math.nan,
                         "interval_score_80_raw": interval_score(y[rmask], q[rmask, 1], q[rmask, 5], 0.2) if rmask.any() else math.nan,
                         "median_hit": hit(q[:, MED], rmask)["hit_rate"]}
        out_models[m] = {
            "pinball": {"mean": weighted_quantile_loss(y, {tau: q[:, k] for k, tau in enumerate(QS)})},
            "coverage": cov, "interval_score": isc,
            "p_up": {"brier": brier(p, yu), "bss_vs_ex_ante_base_rate": bss(p, yu, run["base"][ti]),
                     "ece": rel["ece"], "mce": rel["mce"], "reliability": rel["bins"]},
            "rank_ic_median": {"mean": float(ic.mean()) if len(ic) else math.nan, "hac_t": hac_t(ic.to_numpy(), h),
                               "ci95": [ic_lo, ic_hi], "n_dates": int(len(ic))},
            "direction": hit(q[:, MED]), "regimes": reg,
        }
    clim_loss = out_models["climatology"]["pinball"]["mean"]
    for m in models:
        out_models[m]["pinball"]["skill_vs_climatology"] = 1 - out_models[m]["pinball"]["mean"] / clim_loss
        out_models[m]["pinball"]["test"] = _skill_test(loss_by_date[m], loss_by_date["climatology"], h)
        for name, rmask in regimes.items():
            r = out_models[m]["regimes"][name]
            r["skill_vs_climatology"] = 1 - r["pinball"] / out_models["climatology"]["regimes"][name]["pinball"]
    br = float(yu.mean()) if len(yu) else math.nan
    res = {
        "h": h, "target": target, "start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(end).date()),
        "units": "log return from the next close over h sessions" + (" minus the cross-sectional mean" if target == "rel" else ""),
        "n_rows": int(M.sum()), "n_dates": int(len(np.unique(ti))), "n_entities": n_ent,
        "base_rate_up": br, "always_majority_hit_rate": max(br, 1 - br) if len(yu) else math.nan,
        "momentum_sign_hit": hit(run["mom"][M]),
        "regime_threshold_market_vol_20d": thresh,
        "models": out_models,
        "config": {"quantiles": QS, "ewma_lambda": LAMBDA, "refit_sessions": REFIT, "purge_sessions": h + 1,
                   "embargo_sessions": EMBARGO, "conformal_block_sessions": CAL_BLOCK, "lgbm": LGBM_PARAMS,
                   "features": FEATURES, "skill_significance": "block-bootstrap 95% CI of the per-date pinball-loss "
                   "difference excludes 0 and HAC t > 1.96"},
        "provenance": _provenance(panel), "runtime_s": time.time() - t0,
    }
    return _jsonable(res)


# ── single-stock forecast ───────────────────────────────────────────────────


def forecast_for(panel: pd.DataFrame, symbol: str, asof: Any, h: int, model: str = "lgbm_quantile",
                 target: str = "raw", eval_sessions: int = 252) -> dict[str, Any]:
    """Latest forecast for ``symbol`` using only rows dated <= asof, with its own out-of-sample track record."""
    asof = pd.Timestamp(asof)
    p = panel.loc[pd.to_datetime(panel["date"]) <= asof]
    ent = _entity(p)
    col = "symbol" if "symbol" in p.columns else ent
    ids = p.loc[p[col] == symbol, ent].unique()
    if len(ids) == 0:
        raise KeyError(f"{symbol!r} has no rows on or before {asof.date()}")
    dates = np.sort(pd.to_datetime(p["date"]).unique())
    start = dates[max(0, len(dates) - 1 - eval_sessions)]
    models = tuple(dict.fromkeys(("climatology", model)))
    run = _run(p, h, start, dates[-1], target, models)
    j = run["ents"].get_loc(ids[-1])
    seen = np.flatnonzero(run["present"][: run["i1"] + 1, j])
    t = int(seen[-1])
    q = run["Q"][model][t, j]
    lo80, hi80, adj80 = run["conf"][model][0.8]
    lo90, hi90, _ = run["conf"][model][0.9]
    # Track record on the evaluation window: rows whose labels were realised by asof.
    M = _eval_rows(run, models)
    ti = np.nonzero(M)[0]
    y = run["Y"][M]
    loss = {m: pd.Series(_pinball_rows(y, run["Q"][m][M])).groupby(ti).mean() for m in models}
    test = _skill_test(loss[model], loss["climatology"], h)
    skill = 1 - loss[model].mean() / loss["climatology"].mean() if len(y) else math.nan
    ni = np.nonzero(M)[1]
    mi = pd.MultiIndex.from_arrays([run["dates"][ti], run["ents"][ni]])
    ic = rank_ic_daily(pd.Series(run["Q"][model][M][:, MED], index=mi), pd.Series(y, index=mi),
                       min_names=min(20, max(5, len(run["ents"]) // 2))).dropna().to_numpy()
    ic_t = hac_t(ic, h)
    direction = {"rank_ic_median": float(ic.mean()) if len(ic) else math.nan, "hac_t": ic_t,
                 "significant": bool(math.isfinite(ic_t) and ic_t > 1.96)}
    i1 = run["i1"]
    cal = slice(max(0, i1 - h - CAL_BLOCK), max(0, i1 - h))
    Qc, Yc = run["Q"][model][cal], run["Y"][cal]
    ok = np.isfinite(Yc) & np.isfinite(Qc).all(-1)
    sufficient = bool(model != "climatology" and test["significant"] and np.isfinite(q).all())
    if model == "climatology":
        note = "This is the stock's own history of h-session returns (climatology); it makes no claim of predictive skill."
    elif sufficient:
        note = (f"{model} beat climatology out of sample over the last {test['n_dates']} evaluated sessions "
                f"(pinball skill {skill:.1%}, HAC t {test['hac_t']:.1f}), measured across the whole universe, not this stock alone.")
        if not direction["significant"]:
            note += (" The edge is in the spread of outcomes, not the direction: the median's cross-sectional rank IC is not "
                     "significant, so do not read the median or p_up as a call.")
    else:
        note = (f"Out-of-sample skill of {model} vs climatology over the last {test['n_dates']} evaluated sessions is "
                f"not significantly above zero (skill {skill:.1%}): this forecast is no better than the stock's own "
                "history. Read the interval, not the median.")
    prov = _provenance(panel)
    res = {
        "symbol": symbol, "asof": str(asof.date()), "forecast_date": str(run["dates"][t].date()), "h": h, "target": target,
        "units": "log return from the next close over h sessions" + (" minus the cross-sectional mean" if target == "rel" else ""),
        "model": model, "quantiles": {str(k): v for k, v in zip(QS, q)}, "p_up": run["P"][model][t, j],
        "expected_return": q[MED], "interval_80": [lo80[t, j], hi80[t, j]], "interval_90": [lo90[t, j], hi90[t, j]],
        "calibration": {"coverage_80_recent": conformal_coverage(Yc[ok], Qc[ok][:, 1], Qc[ok][:, 5]) if ok.any() else math.nan,
                        "n": int(ok.sum()), "conformal_widening_80": adj80[t], "block_sessions": CAL_BLOCK},
        "skill_vs_climatology": {"pinball_skill": skill, **test}, "direction_evidence": direction,
        "data_quality": {"last_price_date": str(run["dates"][t].date()), "stale_sessions": int(i1 - t),
                         "history_sessions": int(len(seen)), "warnings": prov["warnings"]},
        "evidence_sufficient": sufficient, "note": note,
    }
    return _jsonable(res)


# ── reproducible dev run ────────────────────────────────────────────────────


def main() -> None:
    from research.marketdata import store

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["store", "local_csv"], default="store")
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default="2026-05-31")
    ap.add_argument("--horizons", default="5,20")
    ap.add_argument("--targets", default="raw,rel")
    ap.add_argument("--examples", default="RELIANCE,HDFCBANK,INFY")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    panel = store.load_panel(source=a.source)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out: dict[str, Any] = {"code_revision": rev, "command": "python -m lab.forecast " + " ".join(
        f"--{k} {v}" for k, v in vars(a).items()), "dataset": _provenance(panel), "historical_claim": HISTORICAL_CLAIM, "runs": []}
    for h in (int(x) for x in a.horizons.split(",")):
        for tgt in a.targets.split(","):
            r = evaluate(panel, h, a.start, a.end, target=tgt)
            out["runs"].append(r)
            for m, v in r["models"].items():
                print(f"h={h:>2} {tgt:3s} {m:14s} pin={v['pinball']['mean']:.5f} skill={v['pinball']['skill_vs_climatology']:+.4f} "
                      f"sig={v['pinball']['test']['significant']} cov80={v['coverage']['0.8']['raw']:.3f}->"
                      f"{v['coverage']['0.8']['conformal']:.3f} IC={v['rank_ic_median']['mean']} "
                      f"hit={v['direction']['hit_rate']:.4f} bss={v['p_up']['bss_vs_ex_ante_base_rate']}")
            print(f"   base_up={r['base_rate_up']:.4f} mom_hit={r['momentum_sign_hit']['hit_rate']:.4f} t={r['runtime_s']:.0f}s")
    last = pd.Timestamp(panel["date"].max())
    out["examples"] = [forecast_for(panel, s, last, 5) for s in a.examples.split(",") if (panel.get("symbol") == s).any()]
    out["runtime_s"] = time.time() - t0
    with open(a.out, "w") as fh:
        json.dump(_jsonable(out), fh, indent=1)


if __name__ == "__main__":
    main()
