"""
DataAdapter — load and validate OHLCV data for the ML training pipeline.

Sources supported:
  * CSV / Parquet files with the expected schema
  * Live fetch via yfinance (individual symbols or NIFTY 50 batch)
  * Synthetic random-walk data for testing

Every public function returns a DataFrame with at minimum:
  symbol | date | open | high | low | close | volume
sorted by (symbol, date) with correct dtypes.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: Final[list[str]] = [
    "symbol", "date", "open", "high", "low", "close", "volume",
]

OPTIONAL_COLUMNS: Final[list[str]] = ["vwap", "sector"]

_NUMERIC_COLUMNS: Final[list[str]] = ["open", "high", "low", "close", "volume"]

# ---------------------------------------------------------------------------
# NIFTY 50 constituents (as of 2024-12; used by fetch_nifty500 as minimum)
# ---------------------------------------------------------------------------

NIFTY50_SYMBOLS: Final[list[str]] = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "BAJFINANCE", "ASIANPAINT", "MARUTI",
    "HCLTECH", "SUNPHARMA", "TATAMOTORS", "WIPRO", "ULTRACEMCO",
    "ONGC", "NTPC", "POWERGRID", "M&M", "TITAN",
    "NESTLEIND", "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
    "TECHM", "BAJAJFINSV", "INDUSINDBK", "GRASIM", "CIPLA",
    "DRREDDY", "EICHERMOT", "APOLLOHOSP", "COALINDIA", "DIVISLAB",
    "BRITANNIA", "HEROMOTOCO", "SBILIFE", "HDFCLIFE", "TATACONSUM",
    "HINDALCO", "BPCL", "SHRIRAMFIN", "BAJAJ-AUTO", "HAL",
]

# Point-in-time constituents are not available offline, so the bias is
# disclosed (in every model's training metadata) rather than fixed.
SURVIVORSHIP_NOTE: Final[str] = (
    "static NIFTY 50 list as of 2024-12 applied to all history; survivorship-biased "
    "(past index exits are missing, later entrants are included); TATAMOTORS has 0 "
    "rows in nifty50_data.csv"
)


# ---------------------------------------------------------------------------
# CSV / Parquet loaders
# ---------------------------------------------------------------------------

def load_csv(path: str) -> pd.DataFrame:
    """Load OHLCV data from a CSV file.

    The CSV must contain all REQUIRED_COLUMNS.  Dates are parsed
    automatically, and the result is sorted by (symbol, date).

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If required columns are missing.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(p)
    # Normalise column names to lowercase
    df.columns = [c.strip().lower() for c in df.columns]

    _check_required_columns(df, path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    _LOG.info("Loaded CSV %s: %d rows, %d symbols", path, len(df), df["symbol"].nunique())
    return df


def load_parquet(path: str) -> pd.DataFrame:
    """Load OHLCV data from a Parquet file.

    Same contract as :func:`load_csv`.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")

    df = pd.read_parquet(p)
    df.columns = [c.strip().lower() for c in df.columns]

    _check_required_columns(df, path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    _LOG.info("Loaded Parquet %s: %d rows, %d symbols", path, len(df), df["symbol"].nunique())
    return df


# ---------------------------------------------------------------------------
# yfinance fetcher
# ---------------------------------------------------------------------------

def fetch_from_yfinance(
    symbols: list[str],
    start_date: str = "2019-01-01",
    end_date: str | None = None,
    suffix: str = ".NS",
) -> pd.DataFrame:
    """Download historical OHLCV data from Yahoo Finance.

    Parameters
    ----------
    symbols
        NSE symbol names without exchange suffix (e.g. ``["RELIANCE", "TCS"]``).
    start_date
        ISO date string for the history start.
    end_date
        ISO date string for the history end.  Defaults to today.
    suffix
        Exchange suffix appended to each symbol.  ``".NS"`` for NSE.

    Returns
    -------
    pd.DataFrame
        Validated DataFrame in the standard OHLCV schema.
    """
    import yfinance as yf  # deferred so module is importable without yfinance

    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    frames: list[pd.DataFrame] = []

    for i, sym in enumerate(symbols):
        ticker = f"{sym}{suffix}"
        try:
            _LOG.info("Fetching %s (%d/%d)", ticker, i + 1, len(symbols))
            hist = yf.Ticker(ticker).history(start=start_date, end=end_date, auto_adjust=True)

            if hist.empty:
                _LOG.warning("No data returned for %s — skipping", ticker)
                continue

            chunk = pd.DataFrame({
                "symbol": sym,
                "date": hist.index,
                "open": hist["Open"].values,
                "high": hist["High"].values,
                "low": hist["Low"].values,
                "close": hist["Close"].values,
                "volume": hist["Volume"].values,
            })
            frames.append(chunk)
        except Exception:
            _LOG.exception("Failed to fetch %s — skipping", ticker)

        # Rate-limit: sleep between symbols (not after last)
        if i < len(symbols) - 1:
            time.sleep(0.5)

    if not frames:
        raise RuntimeError(
            f"Could not fetch data for any of the {len(symbols)} symbols. "
            "Check network connectivity and symbol names."
        )

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    _LOG.info(
        "yfinance fetch complete: %d symbols, %d rows, %s to %s",
        df["symbol"].nunique(), len(df),
        df["date"].min().strftime("%Y-%m-%d"),
        df["date"].max().strftime("%Y-%m-%d"),
    )
    return df


def fetch_nifty50(start_date: str = "2019-01-01") -> pd.DataFrame:
    """Fetch NIFTY 50 constituents via yfinance.

    This is the default data source when no CSV or Parquet file is provided.
    """
    _LOG.info("Fetching NIFTY 50 constituents (%d symbols) from %s", len(NIFTY50_SYMBOLS), start_date)
    return fetch_from_yfinance(NIFTY50_SYMBOLS, start_date=start_date)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean an OHLCV DataFrame.

    Steps:
      1. Check required columns exist.
      2. Coerce ``date`` to datetime.
      3. Coerce OHLCV columns to numeric (non-numeric → NaN).
      4. Drop rows with NaN in any required OHLCV column.
      5. Sort by (symbol, date).
      6. Log summary statistics.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame.

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    _check_required_columns(df, "<DataFrame>")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    for col in _NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before = len(df)
    df = df.dropna(subset=_NUMERIC_COLUMNS).reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        _LOG.warning("Dropped %d rows with NaN in OHLCV columns", dropped)

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    if df.empty:
        _LOG.warning("validate_ohlcv: no valid rows after cleaning")
        return df

    n_symbols = df["symbol"].nunique()
    date_min = df["date"].min().strftime("%Y-%m-%d")
    date_max = df["date"].max().strftime("%Y-%m-%d")
    _LOG.info(
        "Validation complete: %d symbols, %d rows, date range %s to %s",
        n_symbols, len(df), date_min, date_max,
    )
    return df


# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------

def generate_sample_csv(
    path: str,
    n_symbols: int = 5,
    n_days: int = 1000,
    seed: int = 42,
) -> None:
    """Generate a synthetic OHLCV CSV for testing.

    Produces a random-walk price series for each symbol with realistic
    ranges (open ~500-3000, daily moves ~1-3 %, volume ~1M-10M).

    Parameters
    ----------
    path
        Output CSV file path.
    n_symbols
        Number of synthetic symbols to generate.
    n_days
        Number of trading days per symbol.
    seed
        Random seed for reproducibility.
    """
    rng = np.random.default_rng(seed)

    symbol_names = [f"SYM{i:03d}" for i in range(n_symbols)]
    base_date = datetime(2019, 1, 1)
    # Generate business days only (skip weekends)
    dates = pd.bdate_range(start=base_date, periods=n_days)

    rows: list[dict] = []

    for sym in symbol_names:
        # Starting price drawn uniformly from 500-3000
        price = rng.uniform(500, 3000)

        for dt in dates:
            # Daily return: normal with slight positive drift
            ret = rng.normal(loc=0.0003, scale=0.018)
            close = price * (1 + ret)
            close = max(close, 1.0)  # floor at ₹1

            # Intraday range
            spread = abs(rng.normal(0, 0.012)) * close
            high = close + rng.uniform(0, spread)
            low = close - rng.uniform(0, spread)
            low = max(low, 0.5)
            open_ = rng.uniform(low, high)

            volume = int(rng.uniform(1_000_000, 10_000_000))

            rows.append({
                "symbol": sym,
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(open_, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
            })

            price = close

    df = pd.DataFrame(rows)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    _LOG.info(
        "Generated sample CSV: %s (%d symbols x %d days = %d rows)",
        path, n_symbols, n_days, len(df),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_required_columns(df: pd.DataFrame, source: str) -> None:
    """Raise ValueError if any REQUIRED_COLUMNS are missing from *df*."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {source}: {missing}. "
            f"Expected: {REQUIRED_COLUMNS}. Got: {list(df.columns)}"
        )
