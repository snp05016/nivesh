"""Point-in-time universe NSE_LIQ200 (spec 3.6, D1).

Recomputed on the last session of month m from data on or before that session;
the result applies to every session of month m+1. Eligibility, counted per
entity_id: series EQ (the panel is EQ only), at least 252 sessions since the
entity first appeared, median raw close over the last 21 sessions >= 20 INR, and
volume > 0 on at least 95% of the last 126 sessions. Eligible entities are ranked
by 126-session median ``turnover_inr`` (1 = most traded). Existing members ranked
240 or better are kept in rank order up to 200; the best-ranked non-members fill
the rest, so the universe has exactly 200 names whenever 200 are eligible.

Dev mode (``local_csv``) is survivorship-biased: every symbol is in the universe.
"""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import pandas as pd

from research import config

UniverseQuality = Literal["pit", "survivorship_biased"]


def select_members(ranks: pd.Series, previous: set[str], size: int, buffer: int) -> list[str]:
    """Fixed-size buffer rule. ``ranks``: entity_id -> rank among eligible entities."""
    order = ranks.sort_values(kind="stable")
    keep = [str(e) for e, r in order.items() if e in previous and r <= buffer][:size]
    fill = [str(e) for e in order.index if e not in previous][: size - len(keep)]
    return keep + fill


def membership(panel: pd.DataFrame, quality: UniverseQuality | None = None) -> pd.DataFrame:
    """``date, entity_id, in_universe, turnover_rank`` for every panel row.

    ``turnover_rank`` (Int64) is the entity's rank at the recompute that applies to
    the row, <NA> when it was not eligible. ``quality`` defaults to
    ``survivorship_biased`` for a local_csv panel, else ``pit``; it is returned in
    ``attrs["universe_quality"]``.
    """
    u = config.UNIVERSE
    if quality is None:
        dev = len(panel) > 0 and bool(panel["source"].eq("local_csv").all())
        quality = "survivorship_biased" if dev else "pit"
    if panel.empty:
        out = pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "entity_id": pd.Series(dtype=str),
                            "in_universe": pd.Series(dtype=bool), "turnover_rank": pd.Series(dtype="Int64")})
        out.attrs["universe_quality"] = quality
        return out
    dates = np.unique(panel["date"].to_numpy(dtype="datetime64[ns]"))
    ents = np.unique(panel["entity_id"].to_numpy(dtype=str))
    di = np.searchsorted(dates, panel["date"].to_numpy())
    ei = np.searchsorted(ents, panel["entity_id"].to_numpy())
    shape = (len(dates), len(ents))
    traded_rows = panel["volume"].fillna(0).to_numpy() > 0
    close = np.full(shape, np.nan)
    close[di, ei] = panel["close"].to_numpy(dtype="float64")
    traded = np.zeros(shape, dtype=bool)
    traded[di, ei] = traded_rows
    turnover = np.full(shape, np.nan)
    turnover[di, ei] = np.where(traded_rows, panel["turnover_inr"].to_numpy(dtype="float64"), np.nan)
    first = np.full(len(ents), len(dates))
    np.minimum.at(first, ei, di)

    months = pd.DatetimeIndex(dates).to_period("M")
    month_codes = np.asarray(months.asi8)
    is_last = np.r_[month_codes[1:] != month_codes[:-1], True]
    recompute = np.flatnonzero(is_last)  # last session of each month

    w_close, w_rank, w_traded = u["median_close_window_sessions"], u["rank_window_sessions"], u["traded_window_sessions"]
    in_mat = np.zeros((len(recompute), len(ents)), dtype=bool)
    rank_mat = np.full((len(recompute), len(ents)), np.nan)
    members: set[str] = set()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN medians
        for r, t in enumerate(recompute):
            med_close = np.nanmedian(close[max(0, t - w_close + 1): t + 1], axis=0)
            n_traded = traded[max(0, t - w_traded + 1): t + 1].sum(axis=0)
            med_turn = np.nanmedian(turnover[max(0, t - w_rank + 1): t + 1], axis=0)
            eligible = (
                (first <= t - u["min_history_sessions"] + 1)
                & (med_close >= u["min_median_close_inr"])
                & (n_traded >= u["min_traded_share"] * w_traded)
                & np.isfinite(med_turn)
            )
            idx = np.flatnonzero(eligible)
            ranks = pd.Series(med_turn[idx], index=ents[idx]).rank(ascending=False, method="first")
            rank_mat[r, idx] = ranks.to_numpy()
            members = set(select_members(ranks, members, u["size"], u["buffer_rank"]))
            in_mat[r, np.searchsorted(ents, sorted(members))] = True

    # Each session uses the latest recompute strictly before its month began.
    month_first = np.r_[True, month_codes[1:] != month_codes[:-1]]
    first_pos = np.maximum.accumulate(np.where(month_first, np.arange(len(dates)), 0))
    applies = np.searchsorted(recompute, first_pos, side="left") - 1  # -1: none yet
    row_r = applies[di]
    has = row_r >= 0
    safe_r = np.where(has, row_r, 0)
    in_u = has & in_mat[safe_r, ei]
    rank = np.where(has, rank_mat[safe_r, ei], np.nan)
    if quality == "survivorship_biased":
        in_u = np.ones(len(panel), dtype=bool)
    out = pd.DataFrame({
        "date": panel["date"].to_numpy(),
        "entity_id": panel["entity_id"].to_numpy(),
        "in_universe": in_u,
        "turnover_rank": pd.array(np.where(np.isfinite(rank), rank, np.nan), dtype="Float64").astype("Int64"),
    })
    out = out.sort_values(["entity_id", "date"], kind="stable").reset_index(drop=True)
    out.attrs["universe_quality"] = quality
    return out
