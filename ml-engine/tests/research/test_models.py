"""Baselines, the LightGBM procedure and the cohort calibrator (spec 4.3, 4.4, 11.1; package ml-models-registry)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from research import config
from research.features import FEATURES
from research.models import baselines, lgbm
from research.models.calibration import CohortCalibrator, fit_rows

FEATS = list(FEATURES)


# ── calibrator ──────────────────────────────────────────────────────────────


def _planted_oos(start: str = "2019-01-01", end: str = "2023-12-29", n: int = 60, seed: int = 7) -> pd.DataFrame:
    """OOS rows with P(top) = 0.3, 0.4, 0.5, 0.6, 0.7 by bucket; label_end 21 sessions after the as-of."""
    days = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    idx = pd.MultiIndex.from_product([days, [f"E{i:02d}" for i in range(n)]], names=["date", "entity_id"])
    bucket = rng.integers(1, 6, size=len(idx)).astype(float)
    top = (rng.random(len(idx)) < 0.2 + 0.1 * bucket).astype(float)
    end_pos = np.minimum(np.arange(len(days)) + 21, len(days) - 1)
    label_end = np.repeat(days[end_pos], n)
    return pd.DataFrame({"bucket": bucket, "top": top, "label_end": label_end}, index=idx)


def test_calibrator_fit_precedes_test_quarter_and_is_monotone() -> None:
    oos = _planted_oos()
    test_start = pd.Timestamp("2023-01-02")
    # Poison every row whose label has not ended by the test start: inverted outcomes.
    late = pd.DatetimeIndex(oos["label_end"]) >= test_start
    oos.loc[late, "top"] = (oos.loc[late, "bucket"] <= 2).astype(float)

    rows = fit_rows(oos, test_start)
    ts = np.datetime64("2023-01-02")
    as_of = rows.index.get_level_values(0).to_numpy(dtype="datetime64[ns]")
    assert rows["label_end"].to_numpy(dtype="datetime64[ns]").max() < ts
    assert as_of.min() >= np.datetime64("2020-01-02") and as_of.max() < ts  # prior 36 months only

    cal = CohortCalibrator.fit(oos, test_start, 21)
    assert cal.available
    freqs = [b["frequency"] for b in cal.buckets]
    assert all(a < b for a, b in zip(freqs, freqs[1:])), freqs
    assert freqs[0] == pytest.approx(0.3, abs=0.02) and freqs[-1] == pytest.approx(0.7, abs=0.02)
    assert cal.period is not None and pd.Timestamp(cal.period.split(" to ")[1]) < test_start
    assert sum(b["n"] for b in cal.buckets) == len(rows)
    by = {b["bucket"]: b for b in cal.buckets}
    assert by[1]["neutral"] is False and by[5]["neutral"] is False
    for b in cal.buckets:
        assert b["ci_low"] <= b["frequency"] <= b["ci_high"]
        assert b["neutral"] is (b["ci_low"] <= 0.5 <= b["ci_high"])
        assert b["ci_high"] - b["ci_low"] < 0.06
    assert late.sum() > 1000  # the poisoned rows exist but were excluded


def test_calibrator_needs_24_months_and_round_trips() -> None:
    oos = _planted_oos(start="2021-06-01", end="2023-06-30")
    assert not CohortCalibrator.fit(oos, pd.Timestamp("2023-01-02"), 21).available  # ~19 months
    cal = CohortCalibrator.fit(oos, pd.Timestamp("2023-07-03"), 21)
    assert cal.available
    data = json.loads(json.dumps(cal.to_json()))
    assert set(data) == {"buckets", "period", "base_rate"}
    assert set(data["buckets"][0]) == {"bucket", "frequency", "ci_low", "ci_high", "n", "neutral"}
    back = CohortCalibrator.from_json(data)
    assert back == cal
    np.testing.assert_allclose(back.p_array([1, 5, np.nan])[:2], [cal.buckets[0]["frequency"], cal.buckets[4]["frequency"]])
    assert np.isnan(back.p_array([np.nan])[0])
    cohort = back.cohort_for(4)
    assert cohort is not None and cohort["bucket"] == 4 and cohort["cases"] == cal.buckets[3]["n"]
    assert back.p(9) is None
    empty = CohortCalibrator.from_json({"buckets": [], "period": None, "base_rate": None})
    assert not empty.available and empty.p(3) is None and empty.cohort_for(3) is None


def test_calibrator_is_deterministic() -> None:
    oos = _planted_oos()
    a = CohortCalibrator.fit(oos, pd.Timestamp("2023-01-02"), 21).to_json()
    b = CohortCalibrator.fit(oos, pd.Timestamp("2023-01-02"), 21).to_json()
    assert json.dumps(a) == json.dumps(b)


# ── rank_pct and bucket ─────────────────────────────────────────────────────


def test_bucket_edges() -> None:
    got = lgbm.bucket([0.0, 0.199, 0.2, 0.5, 0.799, 0.8, 0.999, 1.0, np.nan])
    np.testing.assert_array_equal(got[:-1], [1, 1, 2, 3, 4, 5, 5, 5])
    assert np.isnan(got[-1])


def test_rank_pct_within_universe() -> None:
    idx = pd.MultiIndex.from_tuples(
        [("2024-01-01", e) for e in "ABCDE"] + [("2024-01-02", e) for e in "AB"], names=["date", "entity_id"]
    )
    score = pd.Series([1.0, 2.0, 3.0, 4.0, 10.0, 5.0, 6.0], index=idx)
    member = pd.Series([True, True, True, True, False, True, True], index=idx)
    r = lgbm.rank_pct(score, member)
    np.testing.assert_allclose(r.iloc[:4], [0.125, 0.375, 0.625, 0.875])
    assert r.iloc[4] == 1.0  # off-universe, above every member
    np.testing.assert_allclose(r.iloc[5:], [0.25, 0.75])


# ── LightGBM procedure ──────────────────────────────────────────────────────


def _planted_design(n_dates: int = 400, n: int = 60, seed: int = 3) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, size=(n_dates * n, len(FEATS)))
    x[rng.random(x.shape) < 0.05] = np.nan
    y = 0.3 * np.nan_to_num(x[:, 0]) + 0.1 * rng.standard_normal(len(x))
    sess = np.repeat(np.arange(n_dates), n)
    return pd.DataFrame(x, columns=FEATS), y, sess


def test_train_procedure_is_deterministic_and_learns() -> None:
    x, y, sess = _planted_design()
    inner, val = sess < 250, (sess >= 280) & (sess < 340)
    full = sess < 340
    test = sess >= 360
    kw = {"seeds": (11, 23), "max_rounds": 120, "patience": 20}

    def fit() -> list[lgbm.TrainedSeed]:
        return lgbm.train_procedure(
            x.loc[inner], y[inner], sess[inner], x.loc[val], y[val], x.loc[full], y[full], sess[full], **kw
        )

    a, b = fit(), fit()
    assert [t.seed for t in a] == [11, 23] and [t.offset for t in a] == [0, 1]
    assert all(1 <= t.best_iteration <= 120 for t in a)
    pa = lgbm.predict([t.booster for t in a], x.loc[test])
    pb = lgbm.predict([t.booster for t in b], x.loc[test])
    np.testing.assert_array_equal(pa, pb)
    assert a[0].booster.model_to_string() == b[0].booster.model_to_string()
    assert np.corrcoef(pa, y[test])[0, 1] > 0.5
    single = [t.booster.predict(x.loc[test].to_numpy()) for t in a]
    np.testing.assert_allclose(pa, np.mean(single, axis=0))
    assert a[0].booster.num_trees() == a[0].best_iteration  # refit at the best iteration


def test_train_procedure_needs_inner_validation() -> None:
    x, y, sess = _planted_design(n_dates=20)
    none = sess < 0
    with pytest.raises(ValueError, match="inner validation"):
        lgbm.train_procedure(x, y, sess, x.loc[none], y[none], x, y, sess, seeds=(11,), max_rounds=5)


# ── baselines ───────────────────────────────────────────────────────────────


def test_rule_baselines_and_random() -> None:
    idx = pd.MultiIndex.from_tuples([("2024-01-01", e) for e in "ABC"], names=["date", "entity_id"])
    ranked = pd.DataFrame(0.0, index=idx, columns=FEATS)
    ranked["mom_12_1"] = [0.5, -0.5, np.nan]
    ranked["vol_252"] = [0.2, 0.4, -0.6]
    ranked["rev_21"] = [-0.1, 0.3, 0.9]
    mom20 = pd.Series([0.01, 0.02, 0.03], index=idx)
    r = baselines.rule_scores(ranked, mom20)
    np.testing.assert_allclose(r["B5"], [-0.2, -0.4, 0.6])
    np.testing.assert_allclose(r["B7"], [(0.5 - 0.2 - 0.1) / 3, (-0.5 - 0.4 + 0.3) / 3, (0.6 + 0.9) / 2])
    np.testing.assert_allclose(r["B3"], mom20)
    np.testing.assert_array_equal(baselines.random_scores(5, 3), baselines.random_scores(5, 3))
    assert not np.array_equal(baselines.random_scores(5, 3), baselines.random_scores(5, 4))
    assert baselines.base_rate([1.0, 0.0, np.nan, 1.0]) == pytest.approx(2 / 3)


def test_momentum_20_on_px_idx() -> None:
    days = pd.bdate_range("2024-01-01", periods=30)
    panel = pd.DataFrame({"date": days, "entity_id": "A", "px_idx": np.exp(0.01 * np.arange(30))})
    m = baselines.momentum_20(panel)
    assert np.isnan(m.loc[(days[19], "A")])
    assert m.loc[(days[25], "A")] == pytest.approx(0.20)


def test_ridge_alpha_chosen_on_inner_validation() -> None:
    x, y, sess = _planted_design(n_dates=60, n=40)
    inner, val, full = sess < 30, (sess >= 40) & (sess < 50), sess < 50
    model, alpha = baselines.fit_ridge(x.loc[inner], y[inner], x.loc[val], y[val], x.loc[full], y[full])
    assert alpha in config.RIDGE_ALPHAS
    pred = baselines.predict_ridge(model, x.loc[sess >= 55])
    assert np.isfinite(pred).all()
    assert np.corrcoef(pred, y[sess >= 55])[0, 1] > 0.5
