"""
FeatureBuilder — construct training matrices from bulk OHLCV data.

Wraps the existing FeatureComputer (pipeline.feature_computer) to produce a
pandas DataFrame suitable for LightGBM training.  For each (symbol, date)
observation with sufficient history, it computes:

  * 158 Alpha158 features  (via FeatureComputer)
  * 8  extra momentum / volatility / volume features
  * 4  forward-return targets (20d / 60d return + direction)
  * Optional one-hot sector encoding

CRITICAL: no lookahead leakage.
  - Features for date T use only OHLCV rows with date <= T.
  - Targets for date T use close prices strictly AFTER T.
"""

from __future__ import annotations

import logging
from typing import Final

import numpy as np
import pandas as pd
import polars as pl

from pipeline.feature_computer import FeatureComputer
from config import FEATURE_LIST

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

EXTRA_FEATURES: Final[list[str]] = [
    "momentum_20d",
    "momentum_60d",
    "momentum_120d",
    "volatility_20d",
    "volatility_60d",
    "volume_trend_20d",
    "drawdown_20d",
    "rsi_14",
]

TARGET_COLUMNS: Final[list[str]] = [
    "forward_return_20d",
    "forward_return_60d",
    "direction_20d",
    "direction_60d",
]

# Minimum rows the FeatureComputer needs (largest Alpha158 window is 60)
_MIN_ALPHA158_ROWS: Final[int] = 60

# Abort when more than this share of eligible rows fails feature computation:
# silently dropping them would bias the training set.
MAX_DROP_RATE: Final[float] = 0.02

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_rsi(closes: np.ndarray, period: int = 14) -> float:
    """Standard Wilder RSI over the last *period* daily returns.

    Returns 50.0 when insufficient data or zero average-loss.
    """
    if len(closes) < period + 1:
        return 50.0

    deltas = np.diff(closes[-(period + 1):])
    gains = np.maximum(deltas, 0.0)
    losses = np.maximum(-deltas, 0.0)

    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _safe_pct(current: float, past: float) -> float:
    """(current - past) / past, guarded against zero denominator."""
    return (current - past) / past if past != 0.0 else 0.0


def _compute_extra_features(closes: np.ndarray, volumes: np.ndarray) -> dict[str, float]:
    """Compute the 8 extra features from historical close/volume arrays.

    *closes* and *volumes* are aligned, ending at date T (inclusive).
    """
    c = closes[-1]

    # -- momentum --
    momentum_20d = _safe_pct(c, closes[-20]) if len(closes) >= 20 else 0.0
    momentum_60d = _safe_pct(c, closes[-60]) if len(closes) >= 60 else 0.0
    momentum_120d = _safe_pct(c, closes[-120]) if len(closes) >= 120 else 0.0

    # -- volatility (std of daily log-returns) --
    def _vol(n: int) -> float:
        if len(closes) < n + 1:
            return 0.0
        daily_ret = np.diff(closes[-n - 1:]) / closes[-n - 1:-1]
        return float(np.std(daily_ret))

    volatility_20d = _vol(20)
    volatility_60d = _vol(60)

    # -- volume trend --
    if len(volumes) >= 20:
        vol_mean_20 = float(np.mean(volumes[-20:]))
        volume_trend_20d = volumes[-1] / vol_mean_20 if vol_mean_20 != 0.0 else 1.0
    else:
        volume_trend_20d = 1.0

    # -- drawdown --
    if len(closes) >= 20:
        peak_20 = float(np.max(closes[-20:]))
        drawdown_20d = (c - peak_20) / peak_20 if peak_20 != 0.0 else 0.0
    else:
        drawdown_20d = 0.0

    # -- RSI 14 --
    rsi_14 = _compute_rsi(closes, period=14)

    return {
        "momentum_20d": momentum_20d,
        "momentum_60d": momentum_60d,
        "momentum_120d": momentum_120d,
        "volatility_20d": volatility_20d,
        "volatility_60d": volatility_60d,
        "volume_trend_20d": volume_trend_20d,
        "drawdown_20d": drawdown_20d,
        "rsi_14": rsi_14,
    }


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def _build_for_symbol(
    sym_df: pd.DataFrame,
    fc: FeatureComputer,
    min_history: int,
) -> tuple[list[dict], int, int]:
    """Build feature rows for a single symbol (already sorted by date asc).

    Returns (rows, attempts, failures): one dict per valid date, the number of
    rows sent to the FeatureComputer and how many of those it rejected.
    """
    rows: list[dict] = []
    attempts = 0
    failures = 0
    n = len(sym_df)
    symbol = sym_df.iloc[0]["symbol"]

    closes_all = sym_df["close"].to_numpy(dtype=np.float64)
    volumes_all = sym_df["volume"].to_numpy(dtype=np.float64)
    dates_all = sym_df["date"].values  # numpy datetime or object

    for i in range(min_history, n):
        # -- Lookahead guard: slice OHLCV up to and including index i --
        ohlcv_slice = sym_df.iloc[: i + 1]

        # Forward returns: need data AFTER index i
        fr_20d = np.nan
        fr_60d = np.nan
        if i + 20 < n:
            fr_20d = _safe_pct(closes_all[i + 20], closes_all[i])
        if i + 60 < n:
            fr_60d = _safe_pct(closes_all[i + 60], closes_all[i])

        # Skip rows where we cannot compute ANY target
        if np.isnan(fr_20d) and np.isnan(fr_60d):
            continue

        # -- Alpha158 features via FeatureComputer (expects Polars) --
        cols_for_fc = ["date", "open", "high", "low", "close", "volume"]
        if "vwap" in ohlcv_slice.columns:
            cols_for_fc.append("vwap")

        # Take only the last max(min_history, _MIN_ALPHA158_ROWS) rows
        # to keep conversion lightweight
        lookback = max(min_history, _MIN_ALPHA158_ROWS)
        fc_input = ohlcv_slice[cols_for_fc].tail(lookback)
        pl_df = pl.from_pandas(fc_input)

        attempts += 1
        try:
            alpha_row = fc.compute_all(pl_df)
        except Exception as exc:
            failures += 1
            _LOG.debug("FeatureComputer failed for %s @ idx %d: %s", symbol, i, exc)
            continue

        # Extract Alpha158 values as a dict
        record: dict = {}
        for col_name in FEATURE_LIST:
            val = alpha_row[col_name][0]
            record[col_name] = float(val) if val is not None else 0.0

        # -- Extra features (use raw numpy slices up to index i) --
        closes_up_to_i = closes_all[: i + 1]
        volumes_up_to_i = volumes_all[: i + 1]
        extra = _compute_extra_features(closes_up_to_i, volumes_up_to_i)
        record.update(extra)

        # -- Metadata --
        record["symbol"] = symbol
        record["date"] = dates_all[i]

        # -- Targets --
        record["forward_return_20d"] = fr_20d
        record["forward_return_60d"] = fr_60d
        record["direction_20d"] = bool(fr_20d > 0) if not np.isnan(fr_20d) else np.nan
        record["direction_60d"] = bool(fr_60d > 0) if not np.isnan(fr_60d) else np.nan

        rows.append(record)

    if failures:
        _LOG.warning(
            "FeatureComputer failed on %d of %d rows for %s (rows dropped)",
            failures, attempts, symbol,
        )
    return rows, attempts, failures


def build_feature_matrix(
    ohlcv_df: pd.DataFrame,
    min_history: int = 120,
) -> pd.DataFrame:
    """Build a training-ready feature matrix from bulk OHLCV data.

    Parameters
    ----------
    ohlcv_df : pd.DataFrame
        Must contain columns: symbol, date, open, high, low, close, volume.
        Optional columns: vwap, sector.
    min_history : int
        Minimum number of prior trading days required before a row is
        eligible for feature computation.  Defaults to 120 to ensure
        the 60-day Alpha158 windows and 120-day momentum are available.

    Returns
    -------
    pd.DataFrame
        Columns: symbol, date, [158 Alpha158], [8 extra], [4 targets],
        plus optional one-hot sector columns.
        Rows with insufficient history or no computable targets are dropped.
    """
    # ── Validate input columns ────────────────────────────────────────────
    required = {"symbol", "date", "open", "high", "low", "close", "volume"}
    missing = required - set(ohlcv_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if ohlcv_df.empty:
        raise ValueError("Input DataFrame is empty")

    _LOG.info(
        "Building feature matrix: %d rows, %d symbols",
        len(ohlcv_df),
        ohlcv_df["symbol"].nunique(),
    )

    # ── Ensure date is datetime, sort ─────────────────────────────────────
    df = ohlcv_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # ── Instantiate FeatureComputer (no scaler for training) ──────────────
    fc = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)

    # ── Process each symbol ───────────────────────────────────────────────
    all_rows: list[dict] = []
    total_attempts = 0
    total_failures = 0
    symbols = df["symbol"].unique()

    for idx, sym in enumerate(symbols):
        sym_df = df[df["symbol"] == sym].reset_index(drop=True)
        if len(sym_df) < min_history + 1:
            _LOG.debug(
                "Skipping %s: only %d rows (need %d)",
                sym, len(sym_df), min_history + 1,
            )
            continue

        rows, attempts, failures = _build_for_symbol(sym_df, fc, min_history)
        all_rows.extend(rows)
        total_attempts += attempts
        total_failures += failures

        if (idx + 1) % 50 == 0:
            _LOG.info("Processed %d / %d symbols", idx + 1, len(symbols))

    if total_attempts and total_failures / total_attempts > MAX_DROP_RATE:
        raise RuntimeError(
            f"FeatureComputer failed on {total_failures} of {total_attempts} rows "
            f"({total_failures / total_attempts:.1%} > {MAX_DROP_RATE:.0%}); "
            "fix the input data instead of training on a biased subset"
        )
    if total_failures:
        _LOG.warning(
            "Dropped %d of %d rows on FeatureComputer failures", total_failures, total_attempts,
        )

    if not all_rows:
        _LOG.warning("No valid training rows produced")
        return pd.DataFrame()

    _LOG.info("Built %d training rows from %d symbols", len(all_rows), len(symbols))

    result = pd.DataFrame(all_rows)

    # ── Sector one-hot encoding ───────────────────────────────────────────
    has_sector = "sector" in ohlcv_df.columns
    if has_sector:
        # Map symbol -> sector from original data (take first non-null)
        sector_map = (
            ohlcv_df[["symbol", "sector"]]
            .dropna(subset=["sector"])
            .drop_duplicates(subset=["symbol"])
            .set_index("symbol")["sector"]
            .to_dict()
        )
        result["sector"] = result["symbol"].map(sector_map).fillna("Unknown")
        sector_dummies = pd.get_dummies(result["sector"], prefix="sector")
        # Convert bool columns to int for LightGBM compatibility
        sector_dummies = sector_dummies.astype(np.int8)
        result = pd.concat([result, sector_dummies], axis=1)
        result = result.drop(columns=["sector"])

    # ── Column ordering ───────────────────────────────────────────────────
    meta_cols = ["symbol", "date"]
    feature_cols = list(FEATURE_LIST) + EXTRA_FEATURES
    sector_cols = [c for c in result.columns if c.startswith("sector_")]
    target_cols = [c for c in TARGET_COLUMNS if c in result.columns]
    other_cols = [
        c for c in result.columns
        if c not in meta_cols + feature_cols + sector_cols + target_cols
    ]

    ordered = meta_cols + feature_cols + sector_cols + target_cols + other_cols
    # Keep only columns that actually exist
    ordered = [c for c in ordered if c in result.columns]
    result = result[ordered]

    return result
