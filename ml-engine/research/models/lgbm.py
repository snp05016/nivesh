"""Procedure ``rg-lgbm-v1`` (spec 4.3, D6, D8).

- LightGBM L2 regression on the centred rank label ``rank_h`` with the frozen
  ``config.LGBM_PARAMS``.
- Date-offset seeds: the k-th seed (``config.LGBM_SEEDS[k]``) trains only on
  sessions with ``session_index % 5 == k``, so each booster sees every fifth
  date and the five boosters overlap less in their h-session labels.
- Early stopping on inner-validation L2 (patience 100, at most 1500 rounds),
  then a refit on the full purged training window at the best iteration.
- score = mean over seeds; ``rank_pct`` = mid-rank percentile within U_t;
  ``bucket`` = min(5, floor(5 * rank_pct) + 1).

Training is deterministic (``deterministic``, ``force_row_wise``, fixed seeds and
thread count) and in-process: no subprocess retraining.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from .. import config
from ..features import FEATURES, universe_pct

N_OFFSETS = 5  # session_index % 5 == k


@dataclass(frozen=True)
class TrainedSeed:
    seed: int
    offset: int
    best_iteration: int
    booster: lgb.Booster


def _x(frame: pd.DataFrame) -> np.ndarray:
    return frame.loc[:, list(FEATURES)].to_numpy(dtype=float, na_value=np.nan)


def _params(seed: int, params: Mapping[str, Any]) -> dict[str, Any]:
    return {**params, "seed": seed}


def train_procedure(
    x_inner: pd.DataFrame,
    y_inner: np.ndarray,
    sess_inner: np.ndarray,
    x_val: pd.DataFrame,
    y_val: np.ndarray,
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    sess_train: np.ndarray,
    *,
    seeds: Sequence[int] = config.LGBM_SEEDS,
    max_rounds: int = config.LGBM_MAX_ROUNDS,
    patience: int = config.LGBM_PATIENCE,
    params: Mapping[str, Any] = config.LGBM_PARAMS,
) -> list[TrainedSeed]:
    """One booster per seed: early stopping on (inner-train, inner-val), refit on the full window.

    ``sess_*`` are integer session indices of the rows. ``x_*`` frames carry the
    ranked fv1 columns (NaN allowed); ``y_*`` is ``rank_h``.
    """
    if len(x_val) == 0:
        raise ValueError("inner validation is empty: the training window is too short")
    xi, xv, xt = _x(x_inner), _x(x_val), _x(x_train)
    names = list(FEATURES)
    out: list[TrainedSeed] = []
    for k, seed in enumerate(seeds):
        p = _params(seed, params)
        mi = (np.asarray(sess_inner) % N_OFFSETS) == k
        mt = (np.asarray(sess_train) % N_OFFSETS) == k
        if not mi.any() or not mt.any():
            raise ValueError(f"seed offset {k} has no training rows")
        d_inner = lgb.Dataset(xi[mi], label=np.asarray(y_inner)[mi], feature_name=names)
        d_val = lgb.Dataset(xv, label=np.asarray(y_val), reference=d_inner, feature_name=names)
        stopper = lgb.train(
            p, d_inner, num_boost_round=max_rounds, valid_sets=[d_val],
            callbacks=[lgb.early_stopping(patience, first_metric_only=True, verbose=False)],
        )
        best = int(stopper.best_iteration) or max_rounds
        d_full = lgb.Dataset(xt[mt], label=np.asarray(y_train)[mt], feature_name=names)
        booster = lgb.train(p, d_full, num_boost_round=best)
        out.append(TrainedSeed(seed=int(seed), offset=k, best_iteration=best, booster=booster))
    return out


def predict(boosters: Sequence[lgb.Booster], x: pd.DataFrame) -> np.ndarray:
    """score = mean of the boosters' predictions."""
    if not boosters:
        raise ValueError("no boosters")
    xs = _x(x)
    preds = [np.asarray(b.predict(xs), dtype=float) for b in boosters]
    return np.mean(np.vstack(preds), axis=0)


def rank_pct(score: pd.Series, in_universe: pd.Series | None = None) -> pd.Series:
    """Mid-rank percentile in (0, 1) of each score within that date's U_t.

    ``score`` is indexed (date, entity_id); ``in_universe`` (same index, bool)
    defaults to all rows. Off-universe rows are placed against the universe
    distribution (same rule as the feature ranks, 4.2). NaN stays NaN.
    """
    values = score.to_numpy(dtype=float)
    member = np.ones(len(score), dtype=bool) if in_universe is None else in_universe.to_numpy(dtype=bool)
    out = np.full(len(score), np.nan)
    dates = score.index.get_level_values(0)
    for _, pos in pd.Series(np.arange(len(score)), index=dates).groupby(level=0, sort=False):
        idx = pos.to_numpy()
        out[idx] = universe_pct(values[idx], values[idx[member[idx]]])
    return pd.Series(out, index=score.index, name="rank_pct")


def bucket(rank_pct_values: Any) -> np.ndarray:
    """min(5, floor(5 * rank_pct) + 1) as float (NaN where rank_pct is NaN)."""
    r = np.asarray(rank_pct_values, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.where(np.isfinite(r), np.minimum(5.0, np.floor(5.0 * r) + 1.0), np.nan)
