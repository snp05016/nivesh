"""Baselines B0-B8 (spec 4.3), evaluated on exactly the model's folds.

| ID | Score |
|---|---|
| B0 | seeded uniform noise |
| B1 | constant p = training base rate of ``top_h`` (probability metrics only) |
| B2 | p = 1, always top half (probability metrics only) |
| B3 | 20-session momentum log(px_t / px_{t-20}) on ``px_idx`` |
| B4 | 12-1 momentum (ranked ``mom_12_1``) |
| B5 | low volatility (minus ranked ``vol_252``) |
| B6 | ranked ``rev_21`` |
| B7 | equal-weight mean of the B4, B5 and B6 ranks |
| B8 | ridge on the 19 ranked features (NaN -> 0 for ridge only), alpha chosen on inner validation |

Ranked features are 2*pct - 1 within U_t, so negating one ranks the opposite
direction exactly. RankIC and the quintile portfolio depend only on per-date
order, so B3-B7 need no further scaling.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from .. import config
from ..features import FEATURES

RANKING_IDS = ("B0", "B3", "B4", "B5", "B6", "B7", "B8")  # produce scores for RankIC
PROBABILITY_IDS = ("B1", "B2")  # produce probabilities only
BASELINE_IDS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8")
MOMENTUM_SHORT_SESSIONS = 20


def momentum_20(panel: pd.DataFrame) -> pd.Series:
    """log(px_t / px_{t-20}) per (date, entity_id); NaN when either price is missing or suspect."""
    px = panel.pivot(index="date", columns="entity_id", values="px_idx").astype(float)
    px = px.where(px > 0)
    log_px = cast(pd.DataFrame, np.log(px))
    mom = (log_px - log_px.shift(MOMENTUM_SHORT_SESSIONS)).unstack()  # (entity_id, date), NaN kept
    return mom.reorder_levels(["date", "entity_id"]).rename("B3")


def rule_scores(ranked: pd.DataFrame, mom20: pd.Series) -> pd.DataFrame:
    """B3-B7 for the rows of ``ranked`` (ranked fv1 features indexed by date, entity_id)."""
    b4 = ranked["mom_12_1"]
    b5 = -ranked["vol_252"]
    b6 = ranked["rev_21"]
    return pd.DataFrame(
        {
            "B3": mom20.reindex(ranked.index),
            "B4": b4,
            "B5": b5,
            "B6": b6,
            "B7": pd.concat([b4, b5, b6], axis=1).mean(axis=1, skipna=True),
        },
        index=ranked.index,
    )


def random_scores(n: int, fold_k: int) -> np.ndarray:
    """B0: uniform noise seeded by the fold, so a fold subset reproduces the same draws."""
    return np.random.default_rng([config.BOOTSTRAP["seed"], fold_k + 1]).random(n)


def base_rate(top_train: Sequence[float] | np.ndarray | pd.Series) -> float:
    """B1: the training share of top-half outcomes."""
    a = np.asarray(top_train, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if len(a) else float("nan")


def _ridge_x(x: pd.DataFrame) -> np.ndarray:
    return x.loc[:, list(FEATURES)].to_numpy(dtype=float, na_value=np.nan).copy()


def fit_ridge(
    x_inner: pd.DataFrame,
    y_inner: np.ndarray,
    x_val: pd.DataFrame,
    y_val: np.ndarray,
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    alphas: Sequence[float] = config.RIDGE_ALPHAS,
) -> tuple[Ridge, float]:
    """B8: pick alpha by inner-validation L2, then refit on the full purged training window."""

    def design(x: pd.DataFrame) -> np.ndarray:
        return np.nan_to_num(_ridge_x(x), nan=0.0)

    xi, xv = design(x_inner), design(x_val)
    best_alpha, best_mse = float(alphas[0]), float("inf")
    for alpha in alphas:  # ties keep the first (smallest) alpha
        mse = float(np.mean((Ridge(alpha=alpha).fit(xi, y_inner).predict(xv) - y_val) ** 2))
        if mse < best_mse:
            best_alpha, best_mse = float(alpha), mse
    return Ridge(alpha=best_alpha).fit(design(x_train), y_train), best_alpha


def predict_ridge(model: Ridge, x: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict(np.nan_to_num(_ridge_x(x), nan=0.0)), dtype=float)
