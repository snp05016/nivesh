"""Corporate-action factors, the forward-chained price index and quality checks (spec 3.3-3.5).

Factor: f_t = prev_close_t / close_p, where p is the entity's previous traded row;
an override row (``research/ref/adjustment_overrides.csv``: isin, ex_date, factor,
note; the ISIN is the one the row carries on the ex-date) wins. When |f_t - 1| is
above 0.5% an event is recorded and the factor is ALWAYS applied (D34); otherwise
f_t = 1. Fallback rows (``source == "yfinance"``, prev_close NaN) take no factor
except a yfinance split dated that day.

Index: px_idx_t = px_idx_q * close_t / (close_q * prod f over (q, t]), with q the
previous valid row, 1.0 on the entity's first valid row. Valid = traded (volume > 0)
and not suspect. It only ever uses data up to t, except that a bad tick found by the
reversal rule is blanked retroactively once the reversal appears (spec 3.5).

Classification (``event``) is a quality note and never changes px_idx: ``split``,
``override``, ``dividend`` or ``ca_unverified``. Dividends are never added (D35).

``quality_flags`` carries one value per row, by priority: suspect, delisted,
zero_volume, fallback, ca_unverified, or "".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research import config

OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "ref" / "adjustment_overrides.csv"
_OHLC_RTOL = 1e-6
_SOURCE_PRIORITY = {"nse_bhavcopy": 0, "local_csv": 1, "yfinance": 2}


class RowAccountingError(RuntimeError):
    """A step dropped more than the allowed share of its expected rows (ML-06)."""


def check_drops(step: str, n_in: int, n_out: int, limit: float = config.QUALITY["drop_limit"]) -> float:
    """Return the dropped share of a step; raise ``RowAccountingError`` above ``limit``."""
    share = (n_in - n_out) / n_in if n_in else 0.0
    if share > limit:
        raise RowAccountingError(
            f"{step}: dropped {n_in - n_out} of {n_in} rows ({share:.2%} > {limit:.0%})"
        )
    return share


def quality_filter(rows: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows that fail the row checks; return (kept, n_dropped).

    Every row needs a positive close. Traded rows (volume > 0) also need positive
    OHLC in the right order. Duplicate (date, symbol) rows keep the best source
    (bhavcopy over yfinance).
    """
    close = rows["close"]
    traded = rows["volume"].fillna(0) > 0
    o, h, lo = rows["open"], rows["high"], rows["low"]
    hi_ref = pd.concat([o, close, lo], axis=1).max(axis=1)
    lo_ref = pd.concat([o, close, h], axis=1).min(axis=1)
    ohlc_ok = (o > 0) & (h > 0) & (lo > 0) & (h >= hi_ref * (1 - _OHLC_RTOL)) & (lo <= lo_ref * (1 + _OHLC_RTOL))
    keep = (close > 0) & np.isfinite(close) & (~traded | ohlc_ok)
    kept = rows.loc[keep]
    prio = kept["source"].map(_SOURCE_PRIORITY).fillna(9)
    kept = (
        kept.assign(_p=prio)
        .sort_values(["date", "symbol", "_p"], kind="stable")
        .drop_duplicates(["date", "symbol"], keep="first")
        .drop(columns="_p")
        .reset_index(drop=True)
    )
    return kept, len(rows) - len(kept)


def load_overrides(path: Path | None = None) -> pd.DataFrame:
    """Override table (isin, ex_date as datetime64[ns], factor > 0, note)."""
    df = pd.read_csv(path or OVERRIDES_PATH, dtype={"isin": str, "note": str}, comment="#")
    missing = {"isin", "ex_date", "factor", "note"} - set(df.columns)
    if missing:
        raise ValueError(f"adjustment overrides missing columns: {sorted(missing)}")
    df["isin"] = df["isin"].str.strip()
    df["ex_date"] = pd.to_datetime(df["ex_date"], format="%Y-%m-%d").astype("datetime64[ns]")
    df["factor"] = df["factor"].astype("float64")
    if bool((df["factor"] <= 0).any()) or bool(df["factor"].isna().any()):
        raise ValueError("adjustment override factors must be positive")
    return df


def _lookup(df: pd.DataFrame, table: pd.DataFrame | None, keys: list[str], col: str) -> pd.Series:
    """Value of ``table[col]`` matched on ``keys`` for every row of ``df`` (NaN if none)."""
    if table is None or table.empty or col not in table.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    t = table.loc[:, [*keys, col]].dropna(subset=[col]).copy()
    t["date"] = pd.to_datetime(t["date"]).astype("datetime64[ns]")
    t = t.drop_duplicates(keys, keep="last")
    merged = df[keys].merge(t, on=keys, how="left")
    return pd.Series(merged[col].to_numpy(dtype="float64"), index=df.index)


def adjust(
    rows: pd.DataFrame,
    *,
    overrides: pd.DataFrame | None = None,
    actions: pd.DataFrame | None = None,
    second_source: pd.DataFrame | None = None,
    quality: dict[str, Any] | None = None,
    lookback: int = config.LINKING["lookback_sessions"],
    apply_factors: bool = True,
) -> pd.DataFrame:
    """Add ``px_idx``, ``event``, ``quality_flags`` and ``ret`` to linked rows.

    ``rows`` carries date, entity_id, isin, symbol (the values on that row), open,
    high, low, close, prev_close, volume, turnover_inr, trades and source.
    ``actions``: yfinance (symbol, date, split, dividend), split as yfinance's ratio
    (2.0 = 2-for-1). ``second_source``: yfinance raw (symbol, date, close).
    ``ret`` is the adjusted simple return against the previous traded row (used by
    the store to pick bad-tick candidates for the second-source check).
    Zero-volume rows get NaN volume, turnover and trades. ``apply_factors=False``
    (dev mode, already-adjusted closes) chains px_idx from closes with f = 1.
    """
    q = quality or config.QUALITY
    df = rows.sort_values(["entity_id", "date"], kind="stable").reset_index(drop=True)
    eid = df["entity_id"]
    vol = df["volume"].fillna(0.0)
    traded = (vol > 0) & (df["close"] > 0)
    fallback = df["source"].eq("yfinance")
    close_t = df["close"].where(traded)
    cp = close_t.groupby(eid).ffill().groupby(eid).shift()  # previous traded close

    split = _lookup(df, actions, ["symbol", "date"], "split")
    div = _lookup(df, actions, ["symbol", "date"], "dividend")
    ov_table = None if overrides is None else overrides.rename(columns={"ex_date": "date"})
    ov = _lookup(df, ov_table, ["isin", "date"], "factor")

    if apply_factors:
        f = (df["prev_close"] / cp).where(traded & ~fallback)
        f = f.where(~fallback, 1.0 / split.where(split > 0))
    else:  # local_csv: px_idx straight from (already adjusted) closes
        f = pd.Series(np.nan, index=df.index)
        ov = pd.Series(np.nan, index=df.index)
    has_ov = ov.notna() & traded
    f = f.where(~has_ov, ov).fillna(1.0)
    is_event = traded & ((f - 1.0).abs() > q["event_threshold"])
    f = f.where(is_event, 1.0)

    split_ok = is_event & (split > 0) & (((1.0 / f) / split - 1.0).abs() <= q["split_match_tolerance"])
    div_ok = is_event & (((1.0 - f) - div / cp).abs() < q["dividend_match_tolerance"])
    event = np.select(
        [split_ok, is_event & has_ov, div_ok, is_event],
        ["split", "override", "dividend", "ca_unverified"],
        "",
    )

    ret = (df["close"] / (cp * f) - 1.0).where(traded & cp.notna())
    cand = ret.abs() > q["jump_threshold"]

    # (i) second source: the yfinance raw close disagrees with the bhavcopy close.
    yf_close = _lookup(df, second_source, ["symbol", "date"], "close")
    sus_i = cand & df["source"].eq("nse_bhavcopy") & (
        (yf_close / df["close"] - 1.0).abs() > q["second_source_tolerance"]
    )

    # (ii) the log move reverses by >= 80% within the next 3 sessions, with no event.
    sidx = df["date"].rank(method="dense").astype("int64")
    log_f = pd.Series(np.log(f.to_numpy(dtype="float64")), index=df.index)
    log_close = pd.Series(np.log(df["close"].where(traded).to_numpy(dtype="float64")), index=df.index)
    la = log_close - log_f.groupby(eid).cumsum()  # log of the factor-adjusted close
    t = pd.DataFrame({
        "eid": eid[traded], "la": la[traded], "sidx": sidx[traded],
        "ev": is_event[traded].astype("int64").groupby(eid[traded]).cumsum(),
    })
    m = np.log1p(ret[traded])
    g = t.groupby("eid", sort=False)
    reverses = pd.Series(False, index=t.index)
    for k in range(1, q["reversal_window_sessions"] + 1):
        moved = g["la"].shift(-k) - t["la"]
        reverses |= (
            (g["sidx"].shift(-k) - t["sidx"] <= q["reversal_window_sessions"])
            & (g["ev"].shift(-k) == t["ev"])
            & (-moved / m >= q["reversal_share"])
        )
    sus_ii = pd.Series(False, index=df.index)
    sus_ii[t.index] = reverses & cand[traded] & ~is_event[traded]
    suspect = sus_i | sus_ii

    valid = traded & ~suspect
    first_la = la.where(valid).groupby(eid).transform("first")
    df["px_idx"] = pd.Series(np.exp((la - first_la).to_numpy(dtype="float64")), index=df.index).where(valid)

    last_sidx = sidx.groupby(eid).transform("max")
    delisted = (sidx == last_sidx) & (last_sidx < sidx.max() - lookback)
    zero = vol <= 0
    df["event"] = event
    df["quality_flags"] = np.select(
        [suspect, delisted, zero, fallback, df["event"].eq("ca_unverified")],
        ["suspect", "delisted", "zero_volume", "fallback", "ca_unverified"],
        "",
    )
    df.loc[zero, ["volume", "turnover_inr", "trades"]] = np.nan
    df["ret"] = ret
    return df
