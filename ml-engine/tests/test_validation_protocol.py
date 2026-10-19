"""Evaluation protocol guards (ML-06): purge/embargo, nested early stopping,
cross-fitted calibration, final holdout and the feature-failure cap."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from training.calibration import IsotonicCalibration, compute_calibration_report
from training.train_alpha158 import cross_fit_calibration
from training.validation import (
    WalkForwardConfig,
    generate_holdout_split,
    generate_splits,
    run_walk_forward,
)

_HORIZON = 20
_FOLDS = [(2019, 2020), (2020, 2021), (2021, 2022)]


def _leaky_panel(n_symbols: int = 3, seed: int = 0) -> pd.DataFrame:
    """Business days 2019-2023; label_t = 1[ret(t, t+20] > 0] and a feature
    that IS that future return (the worst possible leak)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-01-01", "2023-12-29")
    frames = []
    for s in range(n_symbols):
        close = 100.0 * np.exp(np.cumsum(0.01 * rng.standard_normal(len(dates))))
        fwd = pd.Series(close).shift(-_HORIZON) / close - 1.0
        frames.append(pd.DataFrame({
            "symbol": f"S{s}",
            "date": dates,
            "date_ordinal": np.array([d.toordinal() for d in dates], dtype=float),
            "leak": fwd,
            "direction_20d": np.where(fwd.isna(), np.nan, (fwd > 0).astype(float)),
        }))
    return pd.concat(frames, ignore_index=True)


def _trading_days(df: pd.DataFrame) -> np.ndarray:
    return np.unique(df["date"].to_numpy(dtype="datetime64[ns]"))  # sorted


def _trading_pos(days: np.ndarray, d: Any) -> int:
    d = np.datetime64(d, "ns")
    pos = int(np.searchsorted(days, d))
    assert days[pos] == d
    return pos


def _years(dates: np.ndarray) -> set[int]:
    return set((dates.astype("datetime64[Y]").astype(int) + 1970).tolist())


# (a) purge/embargo -----------------------------------------------------------

def test_no_training_label_window_reaches_validation():
    df = _leaky_panel()
    trading_days = _trading_days(df)
    config = WalkForwardConfig(folds=_FOLDS, min_train_samples=50, embargo_days=_HORIZON)

    splits = generate_splits(df, config, ["leak"])

    assert len(splits) == len(_FOLDS)
    for sp in splits:
        val_start = _trading_pos(trading_days, sp.val_dates.min())
        last_train = _trading_pos(trading_days, sp.train_dates.max())
        # The label of the last training row ends at last_train + 20 trading
        # days, which must be strictly before the first validation day.
        assert last_train + _HORIZON < val_start, sp.fold_id
        # ...and the embargo is no wider than needed.
        assert last_train + _HORIZON == val_start - 1, sp.fold_id


def test_without_embargo_training_labels_overlap_validation():
    """The pre-fix behaviour, kept as a check that the test above can fail."""
    df = _leaky_panel()
    trading_days = _trading_days(df)
    config = WalkForwardConfig(folds=_FOLDS, min_train_samples=50, embargo_days=0)

    sp = generate_splits(df, config, ["leak"])[0]

    last_train = _trading_pos(trading_days, sp.train_dates.max())
    assert last_train + _HORIZON >= _trading_pos(trading_days, sp.val_dates.min())


# (b) nested early stopping ---------------------------------------------------

class _RecordingModel:
    """Fake LightGBM-style model: records what fit() received."""

    calls: list[dict] = []

    def fit(self, X, y, eval_set=None):
        _RecordingModel.calls.append({"X": X, "eval_set": eval_set})

    def predict_proba(self, X):
        return np.column_stack([np.full(len(X), 0.5), np.full(len(X), 0.5)])


def test_early_stopping_never_sees_the_reported_fold():
    df = _leaky_panel()
    config = WalkForwardConfig(folds=_FOLDS, min_train_samples=50)
    splits = generate_splits(df, config, ["date_ordinal"])
    _RecordingModel.calls = []

    run_walk_forward(_RecordingModel, splits)

    assert len(_RecordingModel.calls) == len(splits)
    trading_days = _trading_days(df)
    for sp, call in zip(splits, _RecordingModel.calls):
        assert call["eval_set"] is not None
        X_eval, _ = call["eval_set"][0]
        eval_dates = {pd.Timestamp.fromordinal(int(o)) for o in X_eval[:, 0]}
        fit_dates = {pd.Timestamp.fromordinal(int(o)) for o in call["X"][:, 0]}
        train_dates = set(pd.to_datetime(sp.train_dates))
        val_dates = set(pd.to_datetime(sp.val_dates))

        assert X_eval.shape != sp.X_val.shape
        assert eval_dates <= train_dates and not eval_dates & val_dates
        assert not fit_dates & eval_dates
        # inner split is embargoed too
        gap = _trading_pos(trading_days, min(eval_dates)) - _trading_pos(trading_days, max(fit_dates))
        assert gap > config.embargo_days


def test_model_without_eval_set_is_fit_on_full_training_set():
    df = _leaky_panel()
    splits = generate_splits(df, WalkForwardConfig(folds=_FOLDS[:1], min_train_samples=50), ["leak"])
    seen = []

    class _Plain:
        def fit(self, X, y, **kwargs):
            seen.append((len(X), kwargs))

        def predict(self, X):
            return np.full(len(X), 0.5)

    run_walk_forward(_Plain, splits)

    assert seen == [(len(splits[0].y_train), {})]


# (c) cross-fitted calibration ------------------------------------------------

def test_calibration_is_scored_on_data_disjoint_from_its_fit():
    rng = np.random.default_rng(0)
    probs = [rng.random(300) for _ in range(4)]
    trues = [rng.integers(0, 2, 300) for _ in range(4)]

    report, calibrated, final = cross_fit_calibration(probs, trues)
    flipped = [*trues[:-1], 1 - trues[-1]]
    report_flipped, calibrated_flipped, _ = cross_fit_calibration(probs, flipped)

    # Neither the calibrator applied to the reporting fold nor the method
    # choice may depend on that fold's labels.
    np.testing.assert_array_equal(calibrated[-1], calibrated_flipped[-1])
    assert report["best_method"] == report_flipped["best_method"]
    assert calibrated[0] is None and final is not None

    # In-sample isotonic is perfectly "calibrated" on noise (the old ECE 0.0);
    # the cross-fitted report is not.
    iso = IsotonicCalibration()
    iso.fit(probs[-1], trues[-1])
    assert compute_calibration_report(trues[-1], iso.predict_proba(probs[-1]))["ece"] == 0.0
    assert report["ece"] > 0.0


# (d) holdout -----------------------------------------------------------------

def test_holdout_year_is_in_no_fold():
    df = _leaky_panel()
    config = WalkForwardConfig(
        folds=[*_FOLDS, (2022, 2023)], min_train_samples=50, holdout_year=2023,
    )

    splits = generate_splits(df, config, ["leak"])

    assert [sp.val_year for sp in splits] == [2020, 2021, 2022]
    for sp in splits:
        years = _years(np.concatenate([sp.train_dates, sp.val_dates]))
        assert 2023 not in years

    holdout = generate_holdout_split(df, config, ["leak"])
    assert holdout is not None
    assert _years(holdout.val_dates) == {2023}
    trading_days = _trading_days(df)
    assert (
        _trading_pos(trading_days, holdout.train_dates.max()) + _HORIZON
        < _trading_pos(trading_days, holdout.val_dates.min())
    )


# (e) feature-failure cap -----------------------------------------------------

def _ohlcv(n: int = 200, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(0.01 * rng.standard_normal(n)))
    open_ = close * (1 + 0.003 * rng.standard_normal(n))
    return pd.DataFrame({
        "symbol": "AAA",
        "date": pd.bdate_range("2020-01-01", periods=n),
        "open": open_,
        "high": np.maximum(open_, close) * 1.005,
        "low": np.minimum(open_, close) * 0.995,
        "close": close,
        "volume": rng.integers(100_000, 1_000_000, n).astype(float),
    })


@pytest.mark.parametrize("fail_every, raises", [(20, True), (1000, False)])
def test_feature_failures_above_cap_abort(monkeypatch, fail_every, raises):
    from training import feature_pipeline

    real = feature_pipeline.FeatureComputer.compute_all
    calls = {"n": 0}

    def flaky(self, df):
        calls["n"] += 1
        if calls["n"] % fail_every == 0:
            raise ValueError("synthetic failure")
        return real(self, df)

    monkeypatch.setattr(feature_pipeline.FeatureComputer, "compute_all", flaky)

    if raises:  # 5% of rows fail > MAX_DROP_RATE (2%)
        with pytest.raises(RuntimeError, match="FeatureComputer failed"):
            feature_pipeline.build_feature_matrix(_ohlcv())
    else:
        assert not feature_pipeline.build_feature_matrix(_ohlcv()).empty


# End to end: the training script wires the protocol together ----------------

def test_train_alpha158_end_to_end(tmp_path, monkeypatch):
    import json

    from training import model_registry, train_alpha158
    from training.dataset_builder import generate_sample_csv

    csv = tmp_path / "ohlcv.csv"
    generate_sample_csv(str(csv), n_symbols=3, n_days=1400, seed=3)  # 2019-01 .. 2024-05
    monkeypatch.setattr(model_registry, "REGISTRY_DIR", tmp_path / "registry")

    train_alpha158.main([
        "--data-path", str(csv), "--min-train-samples", "100",
        "--folds", "2019:2020,2020:2021,2021:2022,2022:2023",
    ])

    (artifact,) = (tmp_path / "registry" / "candidate").iterdir()
    meta = json.loads((artifact / "metadata.json").read_text())
    calib = json.loads((artifact / "calibration_report.json").read_text())
    oof = pd.read_csv(artifact / "oof_predictions.csv")

    assert meta["embargo_days"] == 20 and meta["holdout_year"] == 2024
    assert "survivorship" in meta["universe"]
    assert calib["protocol"].startswith("cross-fitted") and calib["holdout"]["year"] == 2024
    assert set(oof["split"]) == {"oof", "holdout"}
    assert (pd.to_datetime(oof.loc[oof["split"] == "oof", "date"]).dt.year < 2024).all()
    assert oof.loc[oof["fold"] == oof["fold"].max(), "p_up"].notna().all()
    assert {"fwd_ret_20d", "momentum_20d", "train_base_rate", "p_raw", "y"} <= set(oof.columns)
    # per-row predictions stay out of the metrics JSON
    assert "y_prob" not in json.loads((artifact / "validation_metrics.json").read_text())[0]
    # ML-05/07: the gate reads the trainer's own output; 3 symbols are far too few rows
    assert len(meta["data_sha256"]) == 64
    gate = model_registry.evaluate_deployment_guardrails(artifact.name)
    assert gate["passed"] is False and gate["checks"]
    assert not any("missing columns" in r for r in gate["reasons"])
