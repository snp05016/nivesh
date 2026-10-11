"""Forward-return labels on px_idx (spec 4.1, D4, D35).

One rule shared with live outcome scoring (8.4): the exit is the last valid
``px_idx`` on or before session t+h of the panel calendar, flagged
``stale_exit`` when that row is more than 5 sessions before t+h (delisted,
suspended or untraded). Labels read no dividend data and there is no lagged
label (D32).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .config import HORIZONS
from .features import universe_wide

__all__ = ["make_labels"]

STALE_EXIT_SESSIONS: int = config.LABELS["stale_exit_sessions"]


def make_labels(
    panel: pd.DataFrame,
    membership: pd.DataFrame,
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    """Labels for every (t, entity) with the entity in U_t, indexed (date, entity_id).

    Columns per horizon h: ``ret_h`` simple return, ``xs_h`` log return minus
    the U_t median, ``top_h`` 1.0/0.0 for R above the U_t median, ``rank_h``
    centred uniform rank (rank - 0.5)/N_t - 0.5, ``label_end_h`` the date of
    session t+h, ``stale_exit_h``. All are NaN (``stale_exit_h`` is NA) when
    px_t is missing or suspect, or when session t+h is past the panel end.
    Cross-sectional statistics use the U_t names with a valid label.
    """
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()), name="date")
    entities = pd.Index(sorted(panel["entity_id"].unique()), name="entity_id")
    px = (
        panel.pivot(index="date", columns="entity_id", values="px_idx")
        .reindex(index=dates, columns=entities)
        .astype(float)
    )
    px = px.where(px > 0)
    if "quality_flags" in panel.columns:
        flags = panel.pivot(index="date", columns="entity_id", values="quality_flags").reindex(
            index=dates, columns=entities
        )
        suspect = flags.fillna("").astype(str).apply(lambda col: col.str.contains("suspect", regex=False))
        px = px.where(~suspect)
    present = (
        panel.assign(_row=1.0).pivot(index="date", columns="entity_id", values="_row")
        .reindex(index=dates, columns=entities).notna().to_numpy()
    )
    in_u = universe_wide(membership, dates, entities).to_numpy() & present

    valid = px.notna()
    row = np.arange(len(dates), dtype=float)
    last_idx = pd.DataFrame(np.where(valid, row[:, None], np.nan), index=dates, columns=entities).ffill()
    last_px = px.ffill()
    start = px.to_numpy()

    out: dict[str, np.ndarray] = {}
    n_dates, n_ent = px.shape
    for h in horizons:
        exit_px = last_px.shift(-h).to_numpy()
        exit_idx = last_idx.shift(-h).to_numpy()
        ok = in_u & ~np.isnan(start) & ~np.isnan(exit_px)
        ret = np.where(ok, exit_px / start - 1.0, np.nan)
        y = np.log1p(ret)
        xs = np.full_like(ret, np.nan)
        top = np.full_like(ret, np.nan)
        rnk = np.full_like(ret, np.nan)
        for i in range(n_dates):
            sel = ok[i]
            n = int(sel.sum())
            if n == 0:
                continue
            yi, ri = y[i, sel], ret[i, sel]
            xs[i, sel] = yi - np.median(yi)
            top[i, sel] = (ri > np.median(ri)).astype(float)
            rnk[i, sel] = (pd.Series(yi).rank(method="average").to_numpy() - 0.5) / n - 0.5
        end_pos = np.arange(n_dates) + h
        label_end = np.where(end_pos < n_dates, dates.to_numpy()[np.minimum(end_pos, n_dates - 1)],
                             np.datetime64("NaT"))
        stale = (end_pos[:, None] - exit_idx) > STALE_EXIT_SESSIONS
        out[f"ret_{h}"] = ret
        out[f"xs_{h}"] = xs
        out[f"top_{h}"] = top
        out[f"rank_{h}"] = rnk
        out[f"label_end_{h}"] = np.where(ok, np.broadcast_to(label_end[:, None], (n_dates, n_ent)),
                                         np.datetime64("NaT"))
        out[f"stale_exit_{h}"] = stale
        out[f"ok_{h}"] = ok

    ri, ci = np.nonzero(in_u)
    index = pd.MultiIndex.from_arrays([dates[ri], entities[ci]], names=["date", "entity_id"])
    frame = pd.DataFrame(index=index)
    for h in horizons:
        for key in ("ret", "xs", "top", "rank"):
            frame[f"{key}_{h}"] = out[f"{key}_{h}"][ri, ci].astype(float)
        frame[f"label_end_{h}"] = pd.to_datetime(out[f"label_end_{h}"][ri, ci])
        stale_col = pd.array(out[f"stale_exit_{h}"][ri, ci], dtype="boolean")
        stale_col[~out[f"ok_{h}"][ri, ci]] = pd.NA
        frame[f"stale_exit_{h}"] = stale_col
    return frame.sort_index()
