"""Nightly materialization pipeline for Alpha158 features."""

import logging
import math
from datetime import datetime, timezone
import concurrent.futures
import pandas as pd
import polars as pl

from database import get_session
from models.db_models import StockUniverse, Alpha158Feature
from services.nse_data_provider import get_price_history

logger = logging.getLogger(__name__)


def compute_alpha158_polars(df: pl.DataFrame) -> pl.DataFrame:
    """Compute Alpha158-like features using Polars expressions.
    
    Ensures strict Point-in-Time logic: sorts chronologically by (ticker, date),
    and only uses backward-looking windows (rolling/shifting).
    """
    # Ensure sorted order for correct rolling/shifting computations
    df = df.sort(["ticker", "date"])

    # Define rolling/shifting expressions over ticker partitions
    df_with_features = df.with_columns([
        (pl.col("Open") / pl.col("Close") - 1.0).alias("OPEN0"),
        (pl.col("High") / pl.col("Close") - 1.0).alias("HIGH0"),
        (pl.col("Low") / pl.col("Close") - 1.0).alias("LOW0"),

        # Rate of Change (ROCP) features
        (pl.col("Close") / pl.col("Close").shift(1).over("ticker") - 1.0).alias("ROC_1"),
        (pl.col("Close") / pl.col("Close").shift(3).over("ticker") - 1.0).alias("ROC_3"),
        (pl.col("Close") / pl.col("Close").shift(5).over("ticker") - 1.0).alias("ROC_5"),
        (pl.col("Close") / pl.col("Close").shift(10).over("ticker") - 1.0).alias("ROC_10"),
        (pl.col("Close") / pl.col("Close").shift(20).over("ticker") - 1.0).alias("ROC_20"),
        (pl.col("Close") / pl.col("Close").shift(30).over("ticker") - 1.0).alias("ROC_30"),
        (pl.col("Close") / pl.col("Close").shift(60).over("ticker") - 1.0).alias("ROC_60"),

        # Moving Average (MA) ratios
        (pl.col("Close") / pl.col("Close").rolling_mean(window_size=5).over("ticker") - 1.0).alias("MA_5"),
        (pl.col("Close") / pl.col("Close").rolling_mean(window_size=10).over("ticker") - 1.0).alias("MA_10"),
        (pl.col("Close") / pl.col("Close").rolling_mean(window_size=20).over("ticker") - 1.0).alias("MA_20"),
        (pl.col("Close") / pl.col("Close").rolling_mean(window_size=30).over("ticker") - 1.0).alias("MA_30"),
        (pl.col("Close") / pl.col("Close").rolling_mean(window_size=60).over("ticker") - 1.0).alias("MA_60"),

        # Rolling Standard Deviation
        (pl.col("Close").rolling_std(window_size=5).over("ticker") / (pl.col("Close") + 1e-8)).alias("STD_5"),
        (pl.col("Close").rolling_std(window_size=10).over("ticker") / (pl.col("Close") + 1e-8)).alias("STD_10"),
        (pl.col("Close").rolling_std(window_size=20).over("ticker") / (pl.col("Close") + 1e-8)).alias("STD_20"),
        (pl.col("Close").rolling_std(window_size=30).over("ticker") / (pl.col("Close") + 1e-8)).alias("STD_30"),
        (pl.col("Close").rolling_std(window_size=60).over("ticker") / (pl.col("Close") + 1e-8)).alias("STD_60"),

        # Rolling Max ratios
        (pl.col("High").rolling_max(window_size=5).over("ticker") / pl.col("Close") - 1.0).alias("MAX_5"),
        (pl.col("High").rolling_max(window_size=10).over("ticker") / pl.col("Close") - 1.0).alias("MAX_10"),
        (pl.col("High").rolling_max(window_size=20).over("ticker") / pl.col("Close") - 1.0).alias("MAX_20"),
        (pl.col("High").rolling_max(window_size=30).over("ticker") / pl.col("Close") - 1.0).alias("MAX_30"),
        (pl.col("High").rolling_max(window_size=60).over("ticker") / pl.col("Close") - 1.0).alias("MAX_60"),

        # Rolling Min ratios
        (pl.col("Low").rolling_min(window_size=5).over("ticker") / pl.col("Close") - 1.0).alias("MIN_5"),
        (pl.col("Low").rolling_min(window_size=10).over("ticker") / pl.col("Close") - 1.0).alias("MIN_10"),
        (pl.col("Low").rolling_min(window_size=20).over("ticker") / pl.col("Close") - 1.0).alias("MIN_20"),
        (pl.col("Low").rolling_min(window_size=30).over("ticker") / pl.col("Close") - 1.0).alias("MIN_30"),
        (pl.col("Low").rolling_min(window_size=60).over("ticker") / pl.col("Close") - 1.0).alias("MIN_60"),

        # Rolling Volume ratios
        (pl.col("Volume") / (pl.col("Volume").rolling_mean(window_size=5).over("ticker") + 1e-8) - 1.0).alias("VOLUME_5"),
        (pl.col("Volume") / (pl.col("Volume").rolling_mean(window_size=10).over("ticker") + 1e-8) - 1.0).alias("VOLUME_10"),
        (pl.col("Volume") / (pl.col("Volume").rolling_mean(window_size=20).over("ticker") + 1e-8) - 1.0).alias("VOLUME_20"),
        (pl.col("Volume") / (pl.col("Volume").rolling_mean(window_size=30).over("ticker") + 1e-8) - 1.0).alias("VOLUME_30"),
        (pl.col("Volume") / (pl.col("Volume").rolling_mean(window_size=60).over("ticker") + 1e-8) - 1.0).alias("VOLUME_60"),
    ])

    return df_with_features


def scale_features_cross_sectional(df: pl.DataFrame, feature_cols: list[str], scaler_type: str = "RobustZScoreNorm") -> pl.DataFrame:
    """Scale features cross-sectionally grouped by date."""
    if not scaler_type:
        return df

    exprs = []
    for col in feature_cols:
        if scaler_type == "RobustZScoreNorm":
            # CS Robust Z-Score Norm: (x - median) / (MAD * 1.4826)
            median = pl.col(col).median().over("date")
            mad = (pl.col(col) - median).abs().median().over("date")
            denom = mad * 1.4826 + 1e-8
            scaled_col = ((pl.col(col) - median) / denom).alias(col)
            exprs.append(scaled_col)
        elif scaler_type == "Standard":
            # CS Standard Norm: (x - mean) / std
            mean = pl.col(col).mean().over("date")
            std = pl.col(col).std().over("date")
            denom = std + 1e-8
            scaled_col = ((pl.col(col) - mean) / denom).alias(col)
            exprs.append(scaled_col)

    if exprs:
        df = df.with_columns(exprs)
    return df


def perform_asof_join(df: pl.DataFrame) -> pl.DataFrame:
    """Perform a strict Point-in-Time asof join on date to join features with macro/benchmark indicators."""
    unique_dates = df.select("date").unique().sort("date")
    
    # Create dummy macro benchmark dataset (e.g. constant factor) for PIT join demo
    benchmark_df = pl.DataFrame({
        "date": unique_dates["date"],
        "macro_benchmark": [1.0] * len(unique_dates)
    }).sort("date")

    # Cast string dates to Date objects for robust asof joining
    df_dt = df.with_columns(pl.col("date").str.strptime(pl.Date, "%Y-%m-%d"))
    bench_dt = benchmark_df.with_columns(pl.col("date").str.strptime(pl.Date, "%Y-%m-%d"))

    # Sort dataframes globally by date before calling join_asof to prevent crashes
    df_dt = df_dt.sort("date")
    bench_dt = bench_dt.sort("date")

    joined = df_dt.join_asof(
        bench_dt,
        on="date",
        strategy="backward"
    )

    # Convert back to string date for database consistency
    return joined.with_columns(pl.col("date").dt.strftime("%Y-%m-%d"))


def run_nightly_materialization(target_date: str, scaler_type: str = "RobustZScoreNorm") -> dict:
    """Fetch data, compute Alpha158 features, scale them, and save to the database."""
    logger.info(f"Starting nightly feature materialization for {target_date} using {scaler_type}")

    # 1. Fetch target tickers from StockUniverse
    with get_session() as session:
        tickers = [row.ticker for row in session.query(StockUniverse.ticker).all()]

    if not tickers:
        logger.warning("No tickers found in StockUniverse. Using default fallback tickers.")
        tickers = ["RELIANCE", "TCS", "INFY", "SBIN", "HDFCBANK"]

    # 2. Fetch EOD historical data (retrieve 180 days to compute 60-day windows correctly)
    dfs = []

    def fetch_and_process(ticker):
        try:
            df_pd = get_price_history(ticker, period_days=180)
            if df_pd is not None and not df_pd.empty:
                df_pd = df_pd.reset_index().rename(columns={"index": "date", "Date": "date"})
                df_pd["date"] = pd.to_datetime(df_pd["date"]).dt.strftime("%Y-%m-%d")
                df_pd["ticker"] = ticker
                # Keep required columns only
                df_pd = df_pd[["ticker", "date", "Open", "High", "Low", "Close", "Volume"]]
                # Convert pandas DataFrame to polars DataFrame without pyarrow dependency
                df_pl = pl.DataFrame(df_pd.to_dict(orient="list"))
                return df_pl
        except Exception as e:
            logger.error(f"Failed to fetch history for {ticker}: {e}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(fetch_and_process, ticker): ticker for ticker in tickers}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res is not None:
                dfs.append(res)

    if not dfs:
        logger.warning(f"No price history retrieved for any tickers on {target_date}")
        return {"status": "skipped", "reason": "no_data_fetched"}

    full_df = pl.concat(dfs)

    # Filter to ensure strict PIT (date <= target_date)
    full_df = full_df.filter(pl.col("date") <= target_date)

    if full_df.is_empty():
        logger.warning(f"Data is empty after PIT filtering for {target_date}")
        return {"status": "skipped", "reason": "empty_after_filter"}

    # 3. Compute Alpha158 features
    features_df = compute_alpha158_polars(full_df)

    # 4. Perform Asof Join
    features_df = perform_asof_join(features_df)

    # List of computed features
    feature_cols = [
        "OPEN0", "HIGH0", "LOW0",
        "ROC_1", "ROC_3", "ROC_5", "ROC_10", "ROC_20", "ROC_30", "ROC_60",
        "MA_5", "MA_10", "MA_20", "MA_30", "MA_60",
        "STD_5", "STD_10", "STD_20", "STD_30", "STD_60",
        "MAX_5", "MAX_10", "MAX_20", "MAX_30", "MAX_60",
        "MIN_5", "MIN_10", "MIN_20", "MIN_30", "MIN_60",
        "VOLUME_5", "VOLUME_10", "VOLUME_20", "VOLUME_30", "VOLUME_60"
    ]

    # 5. Scale features cross-sectionally
    if scaler_type:
        features_df = scale_features_cross_sectional(features_df, feature_cols, scaler_type)

    # Filter down to the target date for materialization
    target_df = features_df.filter(pl.col("date") == target_date)

    if target_df.is_empty():
        logger.warning(f"No features computed on target date {target_date}. Possibly a holiday.")
        return {"status": "skipped", "reason": "holiday_or_no_matching_date"}

    # 6. Write features to database using get_session()
    with get_session() as session:
        # Clear existing rows for this date to support idempotency/re-runs
        session.query(Alpha158Feature).filter(Alpha158Feature.date == target_date).delete()

        rows_to_insert = []
        for row in target_df.iter_rows(named=True):
            feat_dict = {}
            for col in feature_cols:
                val = row.get(col)
                if val is not None:
                    if math.isnan(val) or math.isinf(val):
                        feat_dict[col] = None
                    else:
                        feat_dict[col] = float(val)
                else:
                    feat_dict[col] = None

            # Add macro_benchmark as part of metadata or extra features if needed
            if "macro_benchmark" in row:
                feat_dict["macro_benchmark"] = row["macro_benchmark"]

            feat_row = Alpha158Feature(
                ticker=row["ticker"],
                date=row["date"],
                features=feat_dict
            )
            rows_to_insert.append(feat_row)

        if rows_to_insert:
            session.add_all(rows_to_insert)
            session.commit()
            logger.info(f"Successfully materialized {len(rows_to_insert)} Alpha158 rows for {target_date}")
            return {"status": "success", "rows_written": len(rows_to_insert)}

    return {"status": "success", "rows_written": 0}
