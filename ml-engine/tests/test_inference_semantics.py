"""Inference contract: the booster output is P(up), and no direction is served
without a model that passed the promotion gate."""

# LightGBM's OpenMP runtime must load before torch's (pulled in by the models
# package); in the reverse order Booster() segfaults on macOS.
import lightgbm  # noqa: F401
import numpy as np
import polars as pl
import pytest

from config import FEATURE_LIST, LIGHTGBM_MODEL_PATH
from models.model_loader import ModelLoader
from pipeline.feature_computer import FeatureComputer
from pipeline.inference import InferenceEngine

_ROW = pl.DataFrame({f: [0.0] for f in FEATURE_LIST})
_GATED = {"lgb_objective": "binary", "model_validated": True, "base_rate": 0.58, "neutral_band": 0.02}


class _StubBooster:
    """Returns the same P(up) for every row."""

    def __init__(self, p_up: float) -> None:
        self.p_up = p_up

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.full(len(X), self.p_up)


def _ohlcv(drift: float, seed: int, n: int = 120) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))
    open_ = close * (1 + 0.003 * rng.standard_normal(n))
    high = np.maximum(open_, close) * (1 + 0.005 * rng.random(n))
    low = np.minimum(open_, close) * (1 - 0.005 * rng.random(n))
    return pl.DataFrame({
        "date": [f"d{i}" for i in range(n)],
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.integers(100_000, 1_000_000, n).astype(float),
        "vwap": (high + low + close) / 3.0,
    })


def test_shipped_booster_without_passed_gate_serves_no_edge():
    booster = ModelLoader.load_lightgbm(LIGHTGBM_MODEL_PATH)
    objective = booster.dump_model()["objective"]
    assert objective.startswith("binary")
    engine = InferenceEngine(lightgbm_model=booster, lgb_objective=objective)
    computer = FeatureComputer(feature_list=FEATURE_LIST)

    results = [
        engine.predict(computer.compute_all(_ohlcv(drift, seed)))
        for drift in (-0.004, 0.0, 0.004)  # down, flat and up trends
        for seed in range(70)
    ]

    assert len(results) == 210
    assert {r["signal_state"] for r in results} == {"no_edge"}
    assert {r["expected_direction"] for r in results} == {0}
    assert {r["confidence_score"] for r in results} == {0.0}
    assert all(0.0 < r["p_up"] < 1.0 and r["raw_score"] == r["p_up"] for r in results)


def test_validated_direction_is_relative_to_base_rate_and_confidence_tracks_edge():
    probs = (0.30, 0.40, 0.58, 0.70, 0.80)
    out = {p: InferenceEngine(lightgbm_model=_StubBooster(p), **_GATED).predict(_ROW) for p in probs}

    assert [out[p]["expected_direction"] for p in probs] == [-1, -1, 0, 1, 1]
    assert all(r["signal_state"] == "ok" and r["base_rate"] == 0.58 for r in out.values())
    by_edge = sorted(probs, key=lambda p: abs(p - 0.58))
    confidences = [out[p]["confidence_score"] for p in by_edge]
    assert confidences == sorted(confidences)
    assert out[0.58]["confidence_score"] == 0.5


@pytest.mark.parametrize("objective", ["regression", None])
def test_booster_that_is_not_a_binary_classifier_is_rejected(objective):
    with pytest.raises(ValueError):
        InferenceEngine(lightgbm_model=_StubBooster(0.6), lgb_objective=objective)


@pytest.mark.parametrize("base_rate,band", [(None, 0.02), (58.0, 0.02), (0.58, None)])
def test_gated_model_needs_a_probability_scale_base_rate_and_band(base_rate, band):
    with pytest.raises(ValueError):
        InferenceEngine(
            lightgbm_model=_StubBooster(0.6),
            lgb_objective="binary",
            model_validated=True,
            base_rate=base_rate,
            neutral_band=band,
        )


def test_no_model_probability_means_no_edge():
    r = InferenceEngine().predict(_ROW, model_type="lightgbm")
    assert (r["signal_state"], r["expected_direction"], r["confidence_score"], r["p_up"]) == (
        "no_edge", 0, 0.0, None,
    )


@pytest.mark.parametrize("model_type", ["tra", "ensemble"])
def test_model_types_without_a_served_model_are_rejected(model_type):
    with pytest.raises(ValueError):
        InferenceEngine(lightgbm_model=_StubBooster(0.9), **_GATED).predict(_ROW, model_type=model_type)


def test_manifest_absent_or_unreadable_loads_as_empty(tmp_path, monkeypatch):
    import main

    path = tmp_path / "MANIFEST.json"
    monkeypatch.setattr(main, "MANIFEST_PATH", path)
    assert main._load_manifest() == {}
    path.write_text("{not json")
    assert main._load_manifest() == {}
    path.write_text("[1, 2]")
    assert main._load_manifest() == {}
    path.write_text('{"gate": {"passed": true}, "base_rate": 0.58, "neutral_band": 0.02}')
    assert main._load_manifest()["gate"]["passed"] is True
