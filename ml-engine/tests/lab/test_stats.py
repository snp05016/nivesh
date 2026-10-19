import math

import numpy as np
import pytest
from lab import stats as S
from research.validation.metrics import ece_bins

# ── purged CV ──


@pytest.mark.parametrize("n,k,h,emb", [(100, 5, 5, 3), (97, 4, 0, 0), (60, 6, 10, 2)])
def test_purged_kfold_never_leaks(n, k, h, emb):
    folds = S.purged_kfold(n, k, h, emb)
    assert np.array_equal(np.sort(np.concatenate([te for _, te in folds])), np.arange(n))
    for tr, te in folds:
        lo, hi = te[0] - h, te[-1] + emb
        assert not np.any((tr >= lo) & (tr <= hi))
        # nothing outside the purge zone is dropped
        assert set(tr) == set(range(n)) - set(range(max(0, lo), min(n, hi + 1)))


def test_cpcv_path_count_and_purge():
    n, N, k, h, emb = 120, 6, 2, 4, 2
    splits, phi = S.cpcv_splits(n, N, k, h, emb)
    assert len(splits) == math.comb(N, k) == 15
    assert phi == k * math.comb(N, k) // N == math.comb(N - 1, k - 1) == 5
    groups = np.array_split(np.arange(n), N)
    appearances = [sum(np.isin(g, te).all() for _, te in splits) for g in groups]
    assert appearances == [phi] * N  # each group is tested on exactly phi paths
    for tr, te in splits:
        for g in groups:
            if np.isin(g, te).all():
                assert not np.any((tr >= g[0] - h) & (tr <= g[-1] + emb))
        assert len(np.intersect1d(tr, te)) == 0


# ── multiple testing ──


def test_holm_bh_by_hand_values():
    p = [0.01, 0.04, 0.03, 0.005]
    adj, rej = S.holm(p, 0.05)
    np.testing.assert_allclose(adj, [0.03, 0.06, 0.06, 0.02])
    assert rej.tolist() == [True, False, False, True]
    adj, rej = S.benjamini_hochberg(p, 0.05)
    np.testing.assert_allclose(adj, [0.02, 0.04, 0.04, 0.02])
    assert rej.all()
    c = 1 + 1 / 2 + 1 / 3 + 1 / 4
    adj, rej = S.benjamini_yekutieli(p, 0.05)
    np.testing.assert_allclose(adj, np.array([0.02, 0.04, 0.04, 0.02]) * c)
    assert rej.tolist() == [True, False, False, True]


def test_bh_classic_1995_example():
    # Benjamini & Hochberg (1995) sec. 4: 15 p-values, BH rejects 4, Holm rejects 3.
    p = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
         0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000]
    assert S.benjamini_hochberg(p, 0.05)[1].sum() == 4
    assert S.holm(p, 0.05)[1].sum() == 3
    assert S.benjamini_yekutieli(p, 0.05)[1].sum() <= 4


# ── stationary bootstrap ──


def test_stationary_bootstrap_block_length_and_determinism():
    n, L = 20_000, 8.0
    idx = S.stationary_bootstrap_indices(n, L, reps=5, seed=1)
    assert idx.shape == (5, n) and idx.min() >= 0 and idx.max() < n
    breaks = (idx[:, 1:] != (idx[:, :-1] + 1) % n).sum(axis=1)
    mean_len = n / (breaks + 1)
    assert np.all(np.abs(mean_len - L) / L < 0.05)
    assert np.array_equal(idx, S.stationary_bootstrap_indices(n, L, 5, 1))


def test_stationary_bootstrap_ci_brackets_mean():
    x = np.random.default_rng(2).normal(0.5, 1.0, 400)
    lo, hi = S.stationary_bootstrap_ci(x, mean_block=5, reps=1000, seed=3)
    assert lo < x.mean() < hi
    assert 0.1 < hi - lo < 0.4  # iid se ~ 0.05 -> width ~ 0.2


# ── reality check / SPA / Romano-Wolf ──


def _noise(T=500, M=50, seed=2):
    return np.random.default_rng(seed).normal(0.0, 0.01, (T, M))


def test_reality_check_noise_vs_drift():
    d = _noise()
    assert S.white_reality_check(d, reps=1000, mean_block=5, seed=0) > 0.05
    d[:, 0] += 0.003  # t ~ 6.7
    assert S.white_reality_check(d, reps=1000, mean_block=5, seed=0) < 0.05


def test_reality_check_size_under_null():
    # ~uniform p under the null: rejection rate near 5% over independent noise panels
    p = np.array([S.white_reality_check(_noise(300, 20, s), reps=300, mean_block=5, seed=s) for s in range(40)])
    assert (p < 0.05).mean() <= 0.15
    assert 0.3 < p.mean() < 0.7


def test_spa_more_powerful_with_many_poor_strategies():
    rng = np.random.default_rng(11)
    T = 500
    good = rng.normal(0.0012, 0.01, (T, 1))
    poor = rng.normal(-0.004, 0.03, (T, 50))
    d = np.hstack([good, poor])
    rc = S.white_reality_check(d, reps=1000, mean_block=5, seed=0)
    spa = S.hansen_spa(d, reps=1000, mean_block=5, seed=0)
    assert spa <= rc
    assert spa < 0.05 < rc


def test_romano_wolf_flags_only_the_real_one():
    d = _noise()
    d[:, 3] += 0.003
    p = S.romano_wolf_stepdown(d, reps=1000, mean_block=5, seed=0)
    assert p.shape == (50,)
    assert p[3] < 0.01
    assert np.delete(p, 3).min() > 0.05
    assert p[3] == p.min()


# ── calibration ──


def test_reliability_calibrated_vs_miscalibrated():
    rng = np.random.default_rng(5)
    p = rng.uniform(0, 1, 50_000)
    y = (rng.uniform(0, 1, p.size) < p).astype(float)
    for strat in ("quantile", "uniform"):
        r = S.reliability_diagram(p, y, 10, strat)
        assert r["ece"] < 0.03 and r["mce"] < 0.05
        assert sum(b["n"] for b in r["bins"]) == p.size
        assert all(b["ci_lo"] <= b["freq"] <= b["ci_hi"] for b in r["bins"])
    assert S.reliability_diagram(p, y, 10)["ece"] == pytest.approx(ece_bins(p, y, 10))
    y_bad = (rng.uniform(0, 1, p.size) < p**2).astype(float)
    assert S.reliability_diagram(p, y_bad, 10)["ece"] > 0.1


def test_wilson_known_value():
    lo, hi = S.wilson_interval(5, 10)  # textbook: (0.2366, 0.7634)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)


# ── conformal and scoring ──


def test_split_conformal_coverage_iid():
    rng = np.random.default_rng(7)
    for alpha in (0.1, 0.2):
        w = S.split_conformal_interval(rng.standard_t(5, 2000), alpha)
        y = rng.standard_t(5, 20_000)
        assert abs(S.conformal_coverage(y, -w, w) - (1 - alpha)) < 0.02


def test_split_conformal_finite_sample_rank():
    r = np.arange(1, 10, dtype=float)  # n=9, alpha=0.1 -> rank ceil(9) = 9
    assert S.split_conformal_interval(r, 0.1) == 9.0
    assert S.split_conformal_interval(r[:8], 0.1) == math.inf  # rank 9 > n=8


def test_pinball_and_interval_score_by_hand():
    y = np.array([1.0, 3.0])
    # tau=0.1, q=2: u=-1 -> 0.9 ; u=1 -> 0.1 ; tau=0.9, q=2: 0.1 ; 0.9 -> means 0.5, 0.5
    assert S.weighted_quantile_loss(y, {0.1: [2, 2], 0.9: [2, 2]}) == pytest.approx(0.5)
    assert S.weighted_quantile_loss(y, {0.5: y}) == 0.0
    # width 2; y=4 above hi=3 by 1 -> + 2/0.1 * 1 = 20
    assert S.interval_score([2.0, 4.0], [1, 1], [3, 3], 0.1) == pytest.approx((2 + 22) / 2)


# ── Sharpe ──


def test_psr_monotone_and_anchor():
    srs = np.linspace(-0.2, 0.4, 13)
    psr = [S.probabilistic_sharpe(s, 0.1, 250, -0.5, 5.0) for s in srs]
    assert np.all(np.diff(psr) > 0)
    assert S.probabilistic_sharpe(0.1, 0.1, 250) == pytest.approx(0.5)
    # fatter tails / negative skew widen the SE -> PSR closer to 0.5
    assert S.probabilistic_sharpe(0.2, 0.1, 250, -1.0, 8.0) < S.probabilistic_sharpe(0.2, 0.1, 250)


def test_sharpe_ci_matches_lo_for_normal_and_covers():
    rng = np.random.default_rng(9)
    x = rng.normal(0.001, 0.01, 2520)
    r = S.sharpe_ci(x, 252)
    sr = x.mean() / x.std(ddof=1)
    lo_se = math.sqrt((1 + sr**2 / 2) / len(x)) * math.sqrt(252)
    assert r["se"] == pytest.approx(lo_se, rel=0.05)
    assert r["lo"] < 0.1 * math.sqrt(252) < r["hi"]


def test_min_backtest_length():
    # Bailey et al. (2014): ~45 independent trials already need ~5 years for SR 1.
    assert S.min_backtest_length(45, 1.0) == pytest.approx(5.0, abs=0.05)
    assert S.min_backtest_length(1, 1.0) == 0.0
    assert S.min_backtest_length(100, 1.0) > S.min_backtest_length(10, 1.0)
    assert S.min_backtest_length(45, 2.0) == pytest.approx(S.min_backtest_length(45, 1.0) / 4)
