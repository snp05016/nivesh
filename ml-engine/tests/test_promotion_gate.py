"""ML-05: the promotion gate rejects models with no skill and fails closed."""

from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

import training.model_registry as mr
from training.promotion_gate import REQUIRED_COLUMNS, evaluate_gate

BASE = 0.55
N_FOLDS, N_DATES, N_SYMBOLS = 4, 100, 30  # 3000 rows per fold and in the holdout


def _frame(p_fn, seed: int = 0) -> pd.DataFrame:
    """4 folds x 3000 rows + a 3000-row holdout; p_fn(rng, n) -> (p, y).

    p is both the served raw booster output (p_raw, which the gate scores)
    and the report-only calibrated p_up.
    """
    rng = np.random.default_rng(seed)
    frames = []
    for k in range(N_FOLDS + 1):
        n = N_DATES * N_SYMBOLS
        p, y = p_fn(rng, n)
        dates = pd.bdate_range(f"{2021 + k}-01-04", periods=N_DATES)
        frames.append(pd.DataFrame({
            "date": np.repeat(dates, N_SYMBOLS),
            "symbol": np.tile([f"S{i}" for i in range(N_SYMBOLS)], N_DATES),
            "fold": k,
            "split": "holdout" if k == N_FOLDS else "oof",
            "p_raw": p,
            "p_up": p,
            "y": y,
            "train_base_rate": BASE,
            "fwd_ret_20d": np.where(y == 1, 0.05, -0.05) + rng.normal(0, 0.02, n),
            "momentum_20d": rng.normal(0, 0.05, n),
        }))
    return pd.concat(frames, ignore_index=True)


def _uninformed(p_of):
    def fn(rng, n):
        return p_of(rng, n), (rng.random(n) < BASE).astype(int)
    return fn


def _informative(rng, n):
    p = rng.uniform(0.3, 0.8, n)
    return p, (rng.random(n) < p).astype(int)


def test_constant_base_rate_fails_on_brier_skill():
    res = evaluate_gate(_frame(_uninformed(lambda rng, n: np.full(n, BASE))))
    assert not res["passed"]
    assert not res["checks"]["bss_pooled"]["passed"]
    assert not res["checks"]["bss_fold_0"]["passed"]


def test_always_up_fails_on_class_share_and_brier_skill():
    res = evaluate_gate(_frame(_uninformed(lambda rng, n: np.full(n, 0.9))))
    assert not res["passed"]
    assert not res["checks"]["class_share"]["passed"]
    assert res["checks"]["bss_pooled"]["value"] < 0


def test_candidate_like_noise_around_base_rate_fails():
    res = evaluate_gate(_frame(_uninformed(lambda rng, n: BASE + rng.normal(0, 0.02, n))))
    assert not res["passed"]
    assert not res["checks"]["bss_pooled"]["passed"]
    assert not res["checks"]["auc_pooled"]["passed"]


def test_informative_model_passes():
    res = evaluate_gate(_frame(_informative))
    assert res["passed"], res["reasons"]
    assert res["reasons"] == []
    assert res["base_rate"] == BASE
    assert res["neutral_band"] == 0.02
    for check in res["checks"].values():
        assert set(check) == {"value", "ci_low", "threshold", "passed"}
    json.dumps(res)  # stored in gate_result.json and MANIFEST.json


def test_gate_scores_served_raw_probability_not_calibrated():
    # Calibration spreads an always-up booster around the base rate; the
    # booster output (what ml-engine serves) is still > base + band everywhere.
    df = _frame(_informative)
    df["p_raw"] = 0.9
    res = evaluate_gate(df)
    assert not res["passed"]
    assert not res["checks"]["class_share"]["passed"]
    assert not res["checks"]["bss_holdout"]["passed"]
    assert "p_up" not in REQUIRED_COLUMNS


def test_nan_raw_probability_fails_closed():
    df = _frame(_informative)
    df.loc[0, "p_raw"] = np.nan
    res = evaluate_gate(df)
    assert not res["passed"]
    assert "NaN" in res["reasons"][0]


@pytest.mark.parametrize("column", REQUIRED_COLUMNS)
def test_missing_column_fails_closed(column):
    res = evaluate_gate(_frame(_informative).drop(columns=[column]))
    assert not res["passed"]
    assert "missing columns" in res["reasons"][0]


def test_too_few_rows_per_fold_fails_closed():
    df = _frame(_informative)
    res = evaluate_gate(df[~((df["fold"] == 1) & (df["date"] > df.loc[df["fold"] == 1, "date"].min()))])
    assert not res["passed"]
    assert not res["checks"]["n_fold_1"]["passed"]


def _artifact(tmp_path, monkeypatch, oof: pd.DataFrame | None):
    monkeypatch.setattr(mr, "REGISTRY_DIR", tmp_path / "registry")
    monkeypatch.setattr(mr, "_PRODUCTION_MODEL_PATH", tmp_path / "models" / "lgb_model.txt")
    monkeypatch.setattr(mr, "_PRODUCTION_MANIFEST_PATH", tmp_path / "models" / "MANIFEST.json")
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    booster = lgb.train({"objective": "binary", "verbose": -1},
                        lgb.Dataset(X, (X[:, 0] > 0).astype(int)), num_boost_round=3)
    return mr.save_model_artifact(booster, ["a", "b", "c"], {}, [], {},
                                  model_version="v1", oof_predictions=oof)


def test_guardrails_without_oof_file_fail(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path, monkeypatch, None)
    res = mr.evaluate_deployment_guardrails("v1", status="candidate")
    assert not res["passed"]
    assert res["reasons_for_rejection"] == ["no out-of-fold predictions"]
    assert json.loads((artifact / "gate_result.json").read_text())["passed"] is False


def test_deploy_with_failing_gate_raises_and_copies_nothing(tmp_path, monkeypatch):
    _artifact(tmp_path, monkeypatch, _frame(_uninformed(lambda rng, n: np.full(n, BASE))))
    with pytest.raises(mr.GateFailedError):
        mr.deploy_to_production("v1")
    assert not (tmp_path / "models" / "lgb_model.txt").exists()
    assert not (tmp_path / "models" / "MANIFEST.json").exists()
