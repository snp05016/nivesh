"""Validation protocol tests (spec 5.3-5.8, 11.1; package ml-validation)."""

from __future__ import annotations

import copy
import json
import math
import re

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from research import config
from research.validation import metrics
from research.validation.costs import nse_delivery_2026_v1, portfolio_returns
from research.validation.folds import cscv_blocks, make_lockbox_fold, make_walkforward_folds
from research.validation.gates import evaluate_gates
from research.validation.report import render_markdown

SEED = config.BOOTSTRAP["seed"]
DEV = config.DATES["dev"]
SESSIONS = pd.bdate_range("2018-01-01", "2026-03-31")


# ── Folds ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("h", config.HORIZONS)
def test_folds_purge_lockbox_and_inner_gap(h: int) -> None:
    emb = config.EMBARGO
    folds = make_walkforward_folds(SESSIONS, DEV, h)
    assert folds
    lockbox_idx = int(SESSIONS.searchsorted(pd.DatetimeIndex([DEV["lockbox_start"]]))[0])
    for f in folds:
        ts = int(f.test_idx[0])
        assert int(f.train_idx.max()) + h + emb < ts  # outer purge
        assert int(f.test_idx.max()) + h <= lockbox_idx - emb  # no OOS label within 21 of the lockbox
        assert len(f.inner_val_idx) == config.INNER_VAL_SESSIONS
        np.testing.assert_array_equal(f.inner_val_idx, f.train_idx[-config.INNER_VAL_SESSIONS :])
        assert int(f.inner_train_idx.max()) + h + emb < int(f.inner_val_idx[0])  # inner gap
        assert SESSIONS[f.train_idx[0]] >= pd.Timestamp(DEV["train_start"])
    if h == 21:
        assert len(folds) == DEV["oos_refits"]
    # Every OOS label ends before the lockbox boundary, so the last quarter is truncated.
    assert folds[-1].test_end < pd.Timestamp(DEV["lockbox_start"])


def test_fold_hashes_identical_for_identical_inputs() -> None:
    a = make_walkforward_folds(SESSIONS, DEV, 21)
    b = make_walkforward_folds(list(SESSIONS), DEV, 21)
    assert [f.hash for f in a] == [f.hash for f in b]
    assert len({f.hash for f in a}) == len(a)
    assert a[0].hash != make_walkforward_folds(SESSIONS, DEV, 63)[0].hash


def test_lockbox_fold() -> None:
    f = make_lockbox_fold(SESSIONS, DEV, 21)
    assert f is not None and f.k == -1
    ls = int(SESSIONS.searchsorted(pd.DatetimeIndex([DEV["lockbox_start"]]))[0])
    assert int(f.test_idx[0]) == ls
    assert int(f.test_idx.max()) + 21 <= len(SESSIONS) - 1
    assert int(f.train_idx.max()) + 21 + config.EMBARGO < ls


def test_cscv_blocks() -> None:
    blocks = cscv_blocks(100)
    assert len(blocks) == 16
    np.testing.assert_array_equal(np.concatenate(blocks), np.arange(100))


# ── Metrics ─────────────────────────────────────────────────────────────────


def test_lrv_ma20_unit_weights() -> None:
    h, t = 21, 200_000
    e = np.random.default_rng(SEED).standard_normal(t + h - 1)
    x = np.convolve(e, np.ones(h), mode="valid")  # MA(20), unit weights
    true = float(h * h)  # 441
    assert abs(metrics.lrv_hansen_hodrick(x, h) / true - 1) < 0.05
    assert abs(metrics.lrv(x, h) / true - 1) < 0.05
    k = np.arange(1, h)
    big_l = 4 * h
    bartlett_expect = h + 2 * np.sum((1 - k / (big_l + 1)) * (h - k))  # 0.918 x true
    assert abs(bartlett_expect / true - 0.918) < 0.001
    assert abs(metrics.lrv_bartlett(x, big_l) / bartlett_expect - 1) < 0.03


def test_lrv_falls_back_to_bartlett_when_hh_not_positive() -> None:
    x = np.tile([1.0, -1.0], 500)
    assert metrics.lrv_hansen_hodrick(x, 2) <= 0
    assert metrics.lrv(x, 2) == pytest.approx(metrics.lrv_bartlett(x, 8))
    assert metrics.lrv(x, 2) > 0


def _panel(n_dates: int, n_names: int, ic: float, seed: int) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.MultiIndex.from_product(
        [pd.bdate_range("2015-01-01", periods=n_dates), [f"E{i}" for i in range(n_names)]],
        names=["date", "entity_id"],
    )
    y = rng.standard_normal(len(idx))
    score = ic * y + math.sqrt(1 - ic * ic) * rng.standard_normal(len(idx))
    return pd.Series(score, index=idx), pd.Series(y, index=idx)


def test_rank_ic_equals_spearmanr() -> None:
    score, y = _panel(30, 60, 0.2, 1)
    score = score.round(1)  # ties
    y.iloc[::7] = np.nan
    dates = score.index.get_level_values(0).unique()
    y.loc[dates[3]] = np.nan  # a date with no labels
    score.loc[(dates[5], slice(None))] = score.loc[(dates[5], slice(None))].where(
        np.arange(60) < 30
    )  # 30 names left -> below the 40-name minimum
    ic = metrics.rank_ic_daily(score, y)
    assert len(ic) == 30
    assert ic.loc[[dates[3], dates[5]]].isna().all()
    for d in dates[[0, 1, 10, 29]]:
        s, t = score.loc[d], y.loc[d]
        m = s.notna() & t.notna()
        assert ic[d] == pytest.approx(stats.spearmanr(s[m], t[m])[0], abs=1e-12)


def test_t_star_is_nan_when_nonoverlap_t_undefined() -> None:
    x = np.random.default_rng(SEED).standard_normal(20) + 0.5  # < 2 obs per offset at h=21
    assert np.isnan(metrics.nonoverlap_t(x, 21)).all()
    assert math.isfinite(metrics.hac_t(x, 21))
    assert math.isnan(metrics.t_star(x, 21))


def test_block_bootstrap_coverage() -> None:
    rng = np.random.default_rng(SEED)
    trials, hits = 600, 0
    for i in range(trials):
        x = rng.standard_normal(400)
        lo, hi = metrics.block_bootstrap_ci(x, 3, reps=1000, seed=i)
        hits += lo <= 0.0 <= hi
    assert abs(hits / trials - 0.95) <= 0.02


def test_dsr_bailey_lopez_de_prado_2014_example() -> None:
    # Worked example: N = 100 trials, annualised V[SR] = 1/2, best annualised SR 2.5
    # from T = 1250 daily returns, skew -3, kurtosis 10 -> SR0 = 0.1132, DSR = 0.9004.
    sr, var = 2.5 / math.sqrt(250), 0.5 / 250
    assert metrics.expected_max_sr(var, 100) == pytest.approx(0.1132, abs=5e-4)
    assert metrics.dsr_from_moments(sr, var, 100, 1250, -3.0, 10.0) == pytest.approx(0.9004, abs=1e-3)


def test_dsr_from_monthly_series() -> None:
    rng = np.random.default_rng(3)
    good = 0.02 + 0.03 * rng.standard_normal(120)
    trial_srs = 0.05 * rng.standard_normal(9)
    d = metrics.dsr(good, trial_srs)
    assert 0.95 < d <= 1.0
    assert metrics.dsr(0.03 * rng.standard_normal(120), trial_srs) < 0.95
    assert math.isnan(metrics.dsr(good, [0.1]))


def test_pbo_on_noise_is_near_half() -> None:
    perf = np.random.default_rng(SEED).standard_normal((192, 20)) * 0.04
    assert 0.35 <= metrics.pbo_cscv(perf) <= 0.65


def test_pbo_low_for_a_dominant_trial() -> None:
    perf = np.random.default_rng(4).standard_normal((192, 10)) * 0.04
    perf[:, 3] += 0.05
    assert metrics.pbo_cscv(perf) < 0.05


def _auc_ref(y: np.ndarray, s: np.ndarray) -> float:
    """Independent AUC: Mann-Whitney U / (n1 * n0), ties counted as 0.5."""
    pos, neg = s[y == 1], s[y == 0]
    return float(stats.mannwhitneyu(pos, neg)[0]) / (len(pos) * len(neg))


def test_auc_matches_mannwhitney_and_probability_metrics() -> None:
    rng = np.random.default_rng(5)
    y = rng.integers(0, 2, 500)
    s = np.round(y * 0.3 + rng.standard_normal(500), 1)
    assert metrics.auc(s, y) == pytest.approx(_auc_ref(y, s), abs=1e-12)
    assert metrics.brier([0.5, 0.5], [0, 1]) == pytest.approx(0.25)
    assert metrics.bss([0.5, 0.5], [0, 1], 0.5) == pytest.approx(0.0)
    assert metrics.ece_bins([0.2] * 5 + [0.8] * 5, [0, 0, 0, 0, 1, 1, 1, 1, 1, 0], 2) == pytest.approx(0.0)


def test_date_bootstrapped_probability_metrics() -> None:
    rng = np.random.default_rng(6)
    dates = np.repeat(pd.bdate_range("2022-06-01", periods=300), 50)
    y = rng.integers(0, 2, len(dates)).astype(float)
    s = y * 0.2 + rng.standard_normal(len(dates))
    by_year = metrics.auc_by_year(s, y, dates, 21, reps=200)
    assert set(by_year) == {"2022", "2023"}
    m = pd.Series(dates).dt.year.to_numpy() == 2023
    assert by_year["2023"]["auc"] == pytest.approx(_auc_ref(y[m], s[m]), abs=1e-12)
    lo, hi = by_year["2023"]["ci95"]
    assert lo < by_year["2023"]["auc"] < hi and by_year["2023"]["n"] == int(m.sum())
    p = np.where(s > 0.1, 0.6, 0.4)
    lo, hi = metrics.bss_ci(p, y, 0.5, dates, 21, reps=200)
    assert lo < metrics.bss(p, y, 0.5) < hi
    hr = metrics.hit_rate_directional((stats.rankdata(s) - 0.5) / len(s), y, dates, 21, reps=200)
    assert hr["n"] == len(s) and hr["n_eff"] == len(s) / 21
    assert hr["ci95"][0] < hr["value"] < hr["ci95"][1]


# ── Costs ───────────────────────────────────────────────────────────────────


def test_round_trip_one_lakh_zero_slippage() -> None:
    # STT 200 + stamp 15 + exchange 5.94 + SEBI 0.20 + GST 1.1052 + DP 15.93
    hand = 200.0 + 15.0 + 5.94 + 0.20 + 0.18 * (5.94 + 0.20) + 15.93
    got = nse_delivery_2026_v1.round_trip_inr(100_000.0)
    assert abs(got - hand) < 1.0
    assert abs(got - 239.0) < 1.0
    assert nse_delivery_2026_v1.slippage_bp(600) == 4
    assert nse_delivery_2026_v1.slippage_bp(100) == 18  # 100 is not above 100
    assert nse_delivery_2026_v1.slippage_bp(float("nan")) == 40


def _two_stock_path() -> tuple[pd.DataFrame, ...]:
    days = pd.bdate_range("2024-01-01", "2024-04-05")
    px = pd.DataFrame(100.0, index=days, columns=["A", "B"])
    px.loc["2024-02-02":, "A"] = 110.0
    px.loc["2024-03-20":, "A"] = 121.0
    px.loc["2024-02-15":, "B"] = 95.0
    px.loc["2024-03-15":, "B"] = np.nan  # B delists at 95: held as cash until the next rebalance
    scores = pd.DataFrame({"A": 2.0, "B": 1.0}, index=days)
    member = pd.DataFrame(True, index=days, columns=["A", "B"])
    adv = pd.DataFrame(1000.0, index=days, columns=["A", "B"])  # > 500 crore -> 4 bp
    return scores, px, member, adv


def test_two_stock_daily_path_matches_hand_computation() -> None:
    scores, px, member, adv = _two_stock_path()
    out = portfolio_returns(scores, px, member, adv, 21, 1.0, top_fraction=1.0)
    assert list(out.columns) == ["gross", "net", "turnover", "active"]
    assert list(out.index) == [pd.Timestamp("2024-02-01"), pd.Timestamp("2024-03-01")]

    buy = nse_delivery_2026_v1.buy_rate + 0.0004
    sell = nse_delivery_2026_v1.sell_rate + 0.0004
    # Feb: buy 50/50 from cash; A +10%, B -5%.
    cost1 = 0.5 * buy + 0.5 * buy
    gross1 = 0.5 * 1.10 + 0.5 * 0.95 - 1
    net1 = (1 - cost1) * (1 + gross1) - 1
    # Mar 1: drifted weights 0.55/1.025 and 0.475/1.025, back to 50/50.
    d = 0.55 / 1.025 - 0.5
    cost2 = d * sell + d * buy
    gross2 = 0.5 * 1.10 + 0.5 * 1.0 - 1  # A +10%, B frozen at its last price
    net2 = (1 - cost2) * (1 + gross2) - 1
    expected = pd.DataFrame(
        {"gross": [gross1, gross2], "net": [net1, net2], "turnover": [1.0, 2 * d],
         "active": [net1 - gross1, net2 - gross2]},  # both names held: benchmark = gross
        index=out.index,
    )
    pd.testing.assert_frame_equal(out, expected, atol=1e-12, rtol=0)

    out2x = portfolio_returns(scores, px, member, adv, 21, 2.0, top_fraction=1.0)
    assert (out2x["net"] < out["net"]).all()


def test_h63_three_tranches_ramp() -> None:
    days = pd.bdate_range("2024-01-01", "2024-08-30")
    px = pd.DataFrame(100.0, index=days, columns=["A", "B"])
    scores = pd.DataFrame({"A": 2.0, "B": 1.0}, index=days)
    member = pd.DataFrame(True, index=days, columns=["A", "B"])
    out = portfolio_returns(scores, px, member, member * 1000.0, 63, 1.0, top_fraction=0.5)
    # Executions Feb..Aug; the first two months (two tranches still in cash) are dropped.
    assert out.index[0] == pd.Timestamp("2024-04-01")
    assert out["turnover"].iloc[0] == pytest.approx(1 / 3, abs=1e-3)  # earlier tranches paid costs
    assert (out["turnover"].iloc[1:] == 0).all()
    assert (out["gross"].abs() < 1e-15).all()


# ── Gates ───────────────────────────────────────────────────────────────────


def _strong() -> dict:
    return {
        "procedure_id": "rg-lgbm-v1", "horizon": 21, "universe_quality": "pit",
        "data_checks": {"drop_share": 0.0041, "fold_hashes_identical": True, "manifest_verifies": True},
        "rank_ic": {"mean": 0.0613, "hac_t": 4.27, "nonoverlap_t_median": 3.61,
                    "nonoverlap_t_range": [2.93, 4.12], "ci95": [0.0371, 0.0842], "icir_ann": 1.13,
                    "positive_period_share": 0.789, "by_year": {"2021": {"mean": 0.0517, "hac_t": 2.13}}},
        "baselines": {"B4": {"mean_ic": 0.0112, "hac_t": 0.71}, "B6": {"mean_ic": 0.0298, "hac_t": 1.94}},
        "vs_best_baseline": {"baseline": "B6", "delta_ic": 0.0315, "t": 2.61},
        "hit_rate_directional": {"value": 0.5231, "ci95": [0.5112, 0.5347], "n": 41230, "n_eff": 1963.3},
        "portfolio": {"net_monthly_pct": 0.912, "gross_monthly_pct": 1.204, "net_monthly_pct_2x_slippage": 0.733,
                      "turnover_monthly_pct": 48.7, "sharpe_net_ann": 0.87, "dsr": 0.971,
                      "b4_net_monthly_pct": 0.213, "cost_model": "nse_delivery_2026_v1"},
        "probability": {"brier": 0.2471, "bss": 0.0117, "bss_ci95": [0.0043, 0.0191],
                        "bss_ci95_lockbox": [0.0021, 0.0233], "log_loss": 0.6871,
                        "auc_by_year": {"2023": {"auc": 0.561, "ci95": [0.531, 0.589], "n": 9800},
                                        "2024": {"auc": 0.557, "ci95": [0.527, 0.586], "n": 4900}},
                        "ece_lockbox": 0.0187, "n_eff_lockbox": 2380.5},
        "overfitting": {"n_trials": 9, "pbo": 0.112},
        "lockbox": {"rank_ic_mean": 0.0443, "hac_t": 2.07, "net_monthly_pct": 0.517},
        "slices": {
            "vol_tercile": {"low": {"mean_ic": 0.0412}, "mid": {"mean_ic": 0.0583}, "high": {"mean_ic": 0.0761}},
            "covid_2020_02_06": {"mean_ic": 0.0234, "hac_t": 0.83, "n_dates": 86},
        },
    }


def _noise_summary(seed: int) -> dict:
    """A summary computed by the real metrics from a pure-noise panel."""
    h = 21
    score, y = _panel(400, 60, 0.0, seed)
    base, _ = _panel(400, 60, 0.0, seed + 1)
    ic = metrics.rank_ic_daily(score, y)
    ic_b = metrics.rank_ic_daily(base, y)
    rng = np.random.default_rng(seed)
    monthly = 0.03 * rng.standard_normal(120)
    trials = rng.standard_normal((192, 9)) * 0.03
    s = _strong()
    s["rank_ic"].update({"mean": float(ic.mean()), "hac_t": metrics.hac_t(ic, h),
                         "nonoverlap_t_median": float(np.nanmedian(metrics.nonoverlap_t(ic, h))),
                         "positive_period_share": float(np.mean(np.asarray(ic.resample("QE").mean()) > 0))})
    s["vs_best_baseline"] = metrics.vs_best_baseline(ic, {"B6": ic_b}, h)
    s["portfolio"].update({"net_monthly_pct": float(monthly.mean() * 100),
                           "dsr": metrics.dsr(monthly, trials.mean(0) / trials.std(0, ddof=1))})
    s["overfitting"]["pbo"] = metrics.pbo_cscv(trials)
    return s


def test_noise_gives_no_reliable_edge() -> None:
    res = evaluate_gates(_noise_summary(11), universe_quality="pit", horizon=21)
    assert res["tier"] == "no_reliable_edge"
    assert "gate_failed:G1" in res["reason_codes"]
    assert res["probability_display_passed"] is False


def test_planted_signal_passes_g1() -> None:
    score, y = _panel(600, 200, 0.10, 12)
    ic = metrics.rank_ic_daily(score, y)
    assert 0.07 < ic.mean() < 0.13
    assert metrics.t_star(ic, 21) >= 3.0
    s = _strong()
    s["rank_ic"].update({"hac_t": metrics.hac_t(ic, 21),
                         "nonoverlap_t_median": float(np.nanmedian(metrics.nonoverlap_t(ic, 21)))})
    res = evaluate_gates(s, universe_quality="pit", horizon=21)
    assert all(r["passed"] for r in res["gates"] if r["id"] == "G1")


def test_strong_pit_gives_validated_edge() -> None:
    res = evaluate_gates(_strong(), universe_quality="pit", horizon=21)
    assert res["tier"] == "validated_edge"
    assert res["reason_codes"] == []
    assert res["probability_display_passed"] is True
    assert res["horizon"] == 21
    assert {r["id"] for r in res["gates"]} == {"G0", "G1", "G2", "G3", "G4", "G5", "G6", "P"}


def test_survivorship_forces_no_reliable_edge() -> None:
    res = evaluate_gates(_strong(), universe_quality="survivorship_biased", horizon=21)
    assert res["tier"] == "no_reliable_edge"
    assert res["reason_codes"] == ["survivorship_biased_universe"]
    assert res["probability_display_passed"] is False


def test_weak_evidence_and_fail_closed() -> None:
    s = _strong()
    s["rank_ic"]["nonoverlap_t_median"] = 2.4
    res = evaluate_gates(s, universe_quality="pit", horizon=21)
    assert res["tier"] == "weak_evidence"
    assert res["reason_codes"] == ["gate_failed:G1"]
    assert res["probability_display_passed"] is False
    del s["overfitting"]  # missing input fails the gate
    res = evaluate_gates(s, universe_quality="pit", horizon=21)
    assert res["tier"] == "no_reliable_edge"
    assert "gate_failed:G5" in res["reason_codes"]


def test_h63_probability_gate_fails_on_n_eff() -> None:
    s = _strong()
    s["probability"]["n_eff_lockbox"] = 1590.0
    res = evaluate_gates(s, universe_quality="pit", horizon=63)
    assert res["tier"] == "validated_edge"
    assert res["probability_display_passed"] is False


# ── Report ──────────────────────────────────────────────────────────────────


def _validation_json() -> dict:
    s = _strong()
    s["rank_ic"]["nonoverlap_t_median"] = 2.4  # one failing gate row
    s.update({"config_sha256": "c" * 64, "git_sha": "f5dbb22", "data_sha256": "d" * 64,
              "oos_period": "2021-01-01 to 2024-05-31", "lockbox_period": "2024-07-01 to 2026-03-20",
              "lockbox_opened_at": None, "lockbox_spent": True, "n_dates": 812, "avg_universe_n": 49.0})
    s["note"] = "line one\\nline two"  # a literal backslash-n in a string field
    return {**s, **evaluate_gates(s, universe_quality="pit", horizon=21)}


def _json_numbers(node: object) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for v in node.values():
            out |= _json_numbers(v)
    elif isinstance(node, list):
        for v in node:
            out |= _json_numbers(v)
    elif isinstance(node, float):
        out.add(format(node, ".6g"))
    elif isinstance(node, int) and not isinstance(node, bool):
        out.add(str(node))
    return out


def test_report_passed_only_for_passed_gates() -> None:
    vj = _validation_json()
    md = render_markdown(vj)
    n_passed = sum(1 for g in vj["gates"] if g["passed"] is True)
    assert 0 < n_passed < len(vj["gates"])
    assert md.count("PASSED") == n_passed
    assert md.count("FAILED") == len(vj["gates"]) - n_passed
    vj2 = copy.deepcopy(vj)
    vj2["gates"][0]["passed"] = "true"  # only the boolean true counts
    assert render_markdown(vj2).count("PASSED") == n_passed - 1


def test_report_has_no_literal_backslash_n_and_only_json_numbers() -> None:
    vj = _validation_json()
    md = render_markdown(vj)
    assert "\\n" not in md
    assert "line one line two" in md
    allowed = _json_numbers(vj)
    raw = json.dumps(vj)
    for token in re.findall(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?", md):
        if "." in token or "e" in token:
            assert token in allowed, token
        else:
            assert token in raw, token  # integers and label digits (years, G1, ci95)


def test_report_fails_without_stress_window() -> None:
    vj = _validation_json()
    del vj["slices"]["covid_2020_02_06"]
    with pytest.raises(ValueError, match="covid_2020_02_06"):
        render_markdown(vj)
