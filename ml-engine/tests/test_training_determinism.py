"""ML-19: same data and DEFAULT_PARAMS give a byte-identical booster."""

import hashlib

import numpy as np

from models.lgb_model import DEFAULT_PARAMS, LGBEnsembleModel


def _train_hash(X: np.ndarray, y: np.ndarray) -> str:
    model = LGBEnsembleModel(
        num_boost_round=20,
        params={"objective": "binary", "metric": "binary_logloss"},
    )
    model.fit(X, y)
    text = model._model.model_to_string()  # type: ignore[union-attr]
    return hashlib.sha256(text.encode()).hexdigest()


def test_default_params_are_reproducible():
    assert DEFAULT_PARAMS["deterministic"] is True
    assert DEFAULT_PARAMS["force_row_wise"] is True
    assert isinstance(DEFAULT_PARAMS["num_threads"], int)


def test_training_twice_gives_identical_model():
    rng = np.random.default_rng(42)
    X = rng.normal(size=(2000, 158)).astype(np.float32)
    y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(scale=0.5, size=2000) > 0).astype(np.float32)
    assert _train_hash(X, y) == _train_hash(X, y)
