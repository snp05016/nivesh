"""Contract of the shipped booster (ML-17): feature count, objective and
output range on diverse synthetic inputs.

A class-balance / degenerate-output check belongs to ML-01, which owns the
deployed model's semantics; it is deliberately not asserted here.
"""

from __future__ import annotations

# LightGBM's OpenMP runtime must load first (see test_inference_semantics).
import lightgbm  # noqa: F401
import numpy as np
import polars as pl

from config import FEATURE_LIST, LIGHTGBM_MODEL_PATH
from models.model_loader import ModelLoader
from pipeline.feature_computer import FeatureComputer


def _random_walk(seed: int, n: int = 120) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    drift = rng.uniform(-0.004, 0.004)
    vol = rng.uniform(0.005, 0.03)
    close = 100.0 * np.exp(np.cumsum(drift + vol * rng.standard_normal(n)))
    open_ = close * (1 + 0.003 * rng.standard_normal(n))
    high = np.maximum(open_, close) * (1 + 0.005 * rng.random(n))
    low = np.minimum(open_, close) * (1 - 0.005 * rng.random(n))
    return pl.DataFrame({
        "date": [f"d{i:03d}" for i in range(n)],
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.integers(100_000, 1_000_000, n).astype(float),
        "vwap": (high + low + close) / 3.0,
    })


def test_shipped_booster_contract():
    booster = ModelLoader.load_lightgbm(LIGHTGBM_MODEL_PATH)
    assert booster.num_feature() == len(FEATURE_LIST) == 158
    assert booster.dump_model()["objective"].startswith("binary")

    computer = FeatureComputer(feature_list=FEATURE_LIST)
    X = np.vstack([
        computer.compute_all(_random_walk(seed)).to_numpy() for seed in range(200)
    ])
    p = booster.predict(X)

    assert p.shape == (200,)
    assert np.isfinite(p).all()
    assert ((p >= 0.0) & (p <= 1.0)).all()
