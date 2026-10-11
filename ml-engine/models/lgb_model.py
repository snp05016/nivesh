"""
Standalone LightGBM ensemble model for stock ranking.

Wraps lightgbm.train (a Booster) with defaults tuned for Alpha158 features.
The objective comes from `params`: DEFAULT_PARAMS is a regressor, but the
deployed model is trained as a binary classifier (train_alpha158 passes
objective=binary), so predict() then returns P(up).  No Qlib, no DataHandlerLP.

Interface
---------
model = LGBEnsembleModel(num_leaves=64, learning_rate=0.03)
model.fit(X_train, y_train, X_val, y_val)       # [N, 158] → [N]
predictions = model.predict(X_test)              # → np.ndarray [N]
model.save("path.lgb") / LGBEnsembleModel.load("path.lgb")
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Union

import numpy as np

try:
    import lightgbm as lgb
except ImportError:
    lgb = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Default hyperparameters — tuned for Alpha158 on NSE stocks
# ---------------------------------------------------------------------------

DEFAULT_PARAMS: Dict[str, Any] = {
    "objective": "regression",
    "metric": "rmse",
    "boosting_type": "gbdt",
    "num_leaves": 64,
    "learning_rate": 0.03,
    "feature_fraction": 0.75,
    "bagging_fraction": 0.75,
    "bagging_freq": 5,
    "lambda_l1": 1e-3,
    "lambda_l2": 1e-3,
    "min_child_samples": 30,
    "min_split_gain": 1e-4,
    "verbose": -1,
    "seed": 42,
    "num_threads": os.cpu_count() or 4,
}


# ---------------------------------------------------------------------------
# Model class
# ---------------------------------------------------------------------------

class LGBEnsembleModel:
    """LightGBM booster for stock-ranking over Alpha158 features.

    Regression or binary classification, depending on params["objective"]
    (the deployed model is binary: see the module docstring).

    Parameters
    ----------
    num_boost_round : int
        Maximum boosting iterations (default 2000).
    early_stopping_rounds : int
        Stop if no validation improvement for N rounds (default 100).
    verbose_eval : int
        Print evaluation metric every N rounds.  Set to 0 or negative to
        silence (default -1 for silent).
    params : dict, optional
        LightGBM parameters merged on top of DEFAULT_PARAMS.
    """

    def __init__(
        self,
        num_boost_round: int = 2000,
        early_stopping_rounds: int = 100,
        verbose_eval: int = -1,
        params: Optional[Dict[str, Any]] = None,
    ):
        if lgb is None:
            raise ImportError(
                "lightgbm is required for LGBEnsembleModel. "
                "Install with: pip install lightgbm"
            )

        self.num_boost_round = num_boost_round
        self.early_stopping_rounds = early_stopping_rounds
        self.verbose_eval = verbose_eval

        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self._model: Optional[lgb.Booster] = None
        self._evals_result: Dict[str, Dict[str, list]] = {}
        self._feature_importances_: Optional[np.ndarray] = None
        self._fitted = False
        self._input_dim: Optional[int] = None

    # ------------------------------------------------------------------
    # fit
    # ------------------------------------------------------------------

    def fit(
        self,
        X_train: Union[np.ndarray, "np.ndarray"],
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> "LGBEnsembleModel":
        """Train the LightGBM model.

        Parameters
        ----------
        X_train : np.ndarray [N_train, 158]
            Alpha158 feature matrix.
        y_train : np.ndarray [N_train]
            Regression targets (future 2-day returns).
        X_val : np.ndarray, optional
            Validation feature matrix.
        y_val : np.ndarray, optional
            Validation targets.

        Returns
        -------
        self
        """
        X_train = np.asarray(X_train, dtype=np.float32)
        y_train = np.asarray(y_train, dtype=np.float32).ravel()

        self._input_dim = X_train.shape[1]

        dtrain = lgb.Dataset(X_train, label=y_train)

        valid_sets = [dtrain]
        valid_names = ["training"]

        if X_val is not None and y_val is not None:
            X_val = np.asarray(X_val, dtype=np.float32)
            y_val = np.asarray(y_val, dtype=np.float32).ravel()
            dvalid = lgb.Dataset(X_val, label=y_val, reference=dtrain)
            valid_sets.append(dvalid)
            valid_names.append("validation")

        callbacks = []
        if self.early_stopping_rounds > 0:
            callbacks.append(lgb.early_stopping(self.early_stopping_rounds))
        if self.verbose_eval > 0:
            callbacks.append(lgb.log_evaluation(self.verbose_eval))
        callbacks.append(lgb.record_evaluation(self._evals_result))

        self._model = lgb.train(
            params=self.params,
            train_set=dtrain,
            num_boost_round=self.num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        # Cache feature importances (gain-based)
        self._feature_importances_ = self._model.feature_importance(
            importance_type="gain"
        ).astype(np.float64)

        self._fitted = True
        return self

    # ------------------------------------------------------------------
    # predict
    # ------------------------------------------------------------------

    def predict(
        self,
        X: Union[np.ndarray, "np.ndarray"],
        raw_score: bool = True,
    ) -> np.ndarray:
        """Produce scalar return predictions for each sample.

        Parameters
        ----------
        X : np.ndarray [N, 158]
            Alpha158 feature matrix.
        raw_score : bool
            If True, return raw LightGBM scores (default).
            If False, clipping / transform can be applied here.

        Returns
        -------
        preds : np.ndarray [N]
            Expected return predictions.
        """
        self._check_fitted()

        X = np.asarray(X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        raw = self._model.predict(X)  # type: ignore[union-attr]
        return raw.astype(np.float64)

    # ------------------------------------------------------------------
    # feature importance
    # ------------------------------------------------------------------

    @property
    def feature_importance(self) -> Optional[np.ndarray]:
        """Gain-based feature importances for the 158 Alpha158 factors.

        Returns
        -------
        np.ndarray [158] or None if not fitted.
        """
        return self._feature_importances_

    def get_top_features(self, top_k: int = 20) -> list[tuple[int, float]]:
        """Return (feature_index, importance) for the top-k features."""
        if self._feature_importances_ is None:
            return []
        order = np.argsort(self._feature_importances_)[::-1]
        return [(int(i), float(self._feature_importances_[i])) for i in order[:top_k]]

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Save the trained model to a file."""
        self._check_fitted()
        self._model.save_model(path)  # type: ignore[union-attr]

    @classmethod
    def load(cls, path: str, **kwargs: Any) -> "LGBEnsembleModel":
        """Load a trained model from a file."""
        if lgb is None:
            raise ImportError("lightgbm is required.")
        obj = cls(**kwargs)
        obj._model = lgb.Booster(model_file=path)
        obj._feature_importances_ = obj._model.feature_importance(
            importance_type="gain"
        ).astype(np.float64)
        obj._fitted = True
        obj._input_dim = obj._model.num_feature()
        return obj

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _check_fitted(self) -> None:
        if not self._fitted or self._model is None:
            raise RuntimeError("Model not fitted. Call .fit() first.")

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def input_dim(self) -> Optional[int]:
        return self._input_dim

    @property
    def best_iteration(self) -> Optional[int]:
        if self._model is None:
            return None
        return self._model.best_iteration  # type: ignore[union-attr]

    @property
    def evals_result(self) -> Dict[str, Dict[str, list]]:
        return self._evals_result
