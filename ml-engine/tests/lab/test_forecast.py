"""Distributional forecasts: honest skill on synthetic panels, no leakage, conformal recalibration."""
import json

import numpy as np
import pandas as pd

from lab import forecast as fc

N_ENT, N_DAYS = 30, 560
DATES = pd.bdate_range("2019-01-01", periods=N_DAYS)
TEST_START, TEST_END = DATES[330], DATES[-1]


def _panel(returns: np.ndarray, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    px = 100 * np.exp(np.cumsum(returns, axis=0))
    syms = [f"S{i:02d}" for i in range(returns.shape[1])]
    return pd.DataFrame({
        "date": np.repeat(DATES, len(syms)), "symbol": np.tile(syms, len(DATES)),
        "px_idx": px.ravel(), "volume": np.exp(rng.normal(13, 0.3, px.size)),
    })


def _iid(seed=0):
    rng = np.random.default_rng(seed)
    return _panel(rng.normal(0, 1, (N_DAYS, N_ENT)) * rng.uniform(0.01, 0.02, N_ENT), seed)


def _vol_clusters(seed=0):
    rng = np.random.default_rng(seed)
    lv = np.zeros(N_DAYS)  # common log-vol, AR(1) phi 0.98: calm and stormy spells
    for t in range(1, N_DAYS):
        lv[t] = 0.98 * lv[t - 1] + 0.12 * rng.normal()
    return _panel(0.012 * np.exp(lv)[:, None] * rng.normal(0, 1, (N_DAYS, N_ENT)), seed)


def _planted_mean(seed=0):
    rng = np.random.default_rng(seed)
    mu = np.zeros((N_DAYS, N_ENT))  # persistent per-stock drift, visible in trailing returns
    mu[0] = rng.normal(0, 0.003, N_ENT)
    for t in range(1, N_DAYS):
        mu[t] = 0.99 * mu[t - 1] + 0.003 * np.sqrt(1 - 0.99**2) * rng.normal(size=N_ENT)
    return _panel(mu + 0.01 * rng.normal(0, 1, (N_DAYS, N_ENT)), seed)


def test_iid_noise_no_skill_and_evidence_insufficient():
    p = _iid()
    r = fc.evaluate(p, 5, TEST_START, TEST_END)
    json.dumps(r, allow_nan=False)  # strictly JSON-serialisable
    for m in ("ewma_vol", "lgbm_quantile"):
        pin = r["models"][m]["pinball"]
        assert pin["skill_vs_climatology"] < 0.02, (m, pin)
        assert not pin["test"]["significant"], (m, pin)
    f = fc.forecast_for(p, "S03", DATES[-1], 5)
    assert f["evidence_sufficient"] is False
    assert "no better than the stock's own history" in f["note"]
    q = list(f["quantiles"].values())
    assert q == sorted(q) and f["interval_90"][0] <= f["interval_80"][0] <= f["expected_return"] <= f["interval_80"][1] <= f["interval_90"][1]
    assert 0 <= f["p_up"] <= 1 and f["calibration"]["n"] > 0


def test_vol_clustering_ewma_beats_climatology_on_intervals():
    r = fc.evaluate(_vol_clusters(), 5, TEST_START, TEST_END, models=("climatology", "ewma_vol"))
    c, e = r["models"]["climatology"], r["models"]["ewma_vol"]
    assert e["interval_score"]["0.8"]["raw"] < c["interval_score"]["0.8"]["raw"]
    assert e["interval_score"]["0.9"]["raw"] < c["interval_score"]["0.9"]["raw"]
    assert e["pinball"]["skill_vs_climatology"] > 0
    hi_c, hi_e = c["regimes"]["high_vol"]["coverage_80_raw"], e["regimes"]["high_vol"]["coverage_80_raw"]
    assert abs(hi_e - 0.8) < abs(hi_c - 0.8)


def test_planted_mean_lgbm_finds_it():
    r = fc.evaluate(_planted_mean(), 5, TEST_START, TEST_END, models=("climatology", "lgbm_quantile"))
    g = r["models"]["lgbm_quantile"]
    assert g["rank_ic_median"]["mean"] > 0.1 and g["rank_ic_median"]["ci95"][0] > 0
    assert g["pinball"]["skill_vs_climatology"] > 0
    assert g["direction"]["hit_rate"] > r["always_majority_hit_rate"]


def test_no_leakage_forecasts_at_T_ignore_later_data():
    p = _planted_mean(seed=3)
    T = DATES[420]
    full = fc._run(p, 5, TEST_START, DATES[-1], "raw", fc.MODELS)
    cut = fc._run(p[p["date"] <= T], 5, TEST_START, T, "raw", fc.MODELS)
    i = full["dates"].get_loc(T)
    assert cut["dates"][-1] == T
    for m in fc.MODELS:
        np.testing.assert_array_equal(full["Q"][m][: i + 1], cut["Q"][m][: i + 1])
        np.testing.assert_array_equal(full["P"][m][: i + 1], cut["P"][m][: i + 1])
        for level in fc.INTERVALS:
            for k in range(3):
                np.testing.assert_array_equal(full["conf"][m][level][k][: i + 1], cut["conf"][m][level][k][: i + 1])
        assert np.isfinite(full["Q"][m][i]).all()
    a = fc.forecast_for(p, "S05", T, 5, model="ewma_vol")
    b = fc.forecast_for(p[p["date"] <= T], "S05", T, 5, model="ewma_vol")
    assert a == b


def test_conformal_widening_moves_coverage_to_nominal():
    rng = np.random.default_rng(7)
    r = rng.normal(0, 0.01, (N_DAYS, N_ENT))
    r[300:] *= 2.5  # volatility jumps: expanding climatology is now far too narrow
    res = fc.evaluate(_panel(r, 7), 5, TEST_START, TEST_END, models=("climatology",))
    for level in ("0.8", "0.9"):
        cov = res["models"]["climatology"]["coverage"][level]
        nominal = float(level)
        assert cov["raw"] < nominal - 0.1
        assert cov["conformal"] > cov["raw"]
        assert abs(cov["conformal"] - nominal) < abs(cov["raw"] - nominal)
