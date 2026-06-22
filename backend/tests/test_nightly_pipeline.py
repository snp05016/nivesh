import polars as pl
import pandas as pd
import pytest
from sqlalchemy import create_engine
from datetime import datetime, timedelta

from models.db_models import Base, Alpha158Feature, StockUniverse
from services.nightly_pipeline import (
    compute_alpha158_polars,
    scale_features_cross_sectional,
    perform_asof_join,
    run_nightly_materialization
)


def test_database_table_creation():
    """Verify that creating tables via Base.metadata.create_all() works against local SQLite."""
    engine = create_engine("sqlite:///:memory:")
    # Base.metadata.create_all should run without raising any exceptions
    Base.metadata.create_all(bind=engine)

    # Check that alpha158_features table is created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "alpha158_features" in tables
    assert "stock_universe" in tables


def test_alpha158_polars_computation():
    """Verify that passing a mock Polars DataFrame of OHLCV data through the Alpha158 calculation pipeline works."""
    tickers = ["T1", "T2"]
    dates = [(datetime(2026, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(75)]

    data = []
    for ticker in tickers:
        for i, date_str in enumerate(dates):
            data.append({
                "ticker": ticker,
                "date": date_str,
                "Open": 100.0 + i * 0.5,
                "High": 105.0 + i * 0.5,
                "Low": 95.0 + i * 0.5,
                "Close": 101.0 + i * 0.5,
                "Volume": 1000.0 + i * 10.0
            })

    df = pl.DataFrame(data)

    # Run computation
    out_df = compute_alpha158_polars(df)

    # Assertions
    assert out_df.shape[0] == len(data)

    # Check that all feature columns are present and contain floats
    feature_cols = [
        "OPEN0", "HIGH0", "LOW0",
        "ROC_1", "ROC_3", "ROC_5", "ROC_10", "ROC_20", "ROC_30", "ROC_60",
        "MA_5", "MA_10", "MA_20", "MA_30", "MA_60",
        "STD_5", "STD_10", "STD_20", "STD_30", "STD_60",
        "MAX_5", "MAX_10", "MAX_20", "MAX_30", "MAX_60",
        "MIN_5", "MIN_10", "MIN_20", "MIN_30", "MIN_60",
        "VOLUME_5", "VOLUME_10", "VOLUME_20", "VOLUME_30", "VOLUME_60"
    ]
    for col in feature_cols:
        assert col in out_df.columns
        # For dates after index 65, rolling windows of size 60 should have valid float values
        valid_slice = out_df.filter(pl.col("date") >= dates[65]).select(col).to_series()
        assert not valid_slice.is_null().any(), f"Column {col} has nulls in valid slice"


def test_scale_features_cross_sectional():
    """Verify that scale_features_cross_sectional normalizes values cross-sectionally."""
    data = [
        {"ticker": "T1", "date": "2026-06-22", "OPEN0": 1.0, "MA_5": 10.0},
        {"ticker": "T2", "date": "2026-06-22", "OPEN0": 2.0, "MA_5": 20.0},
        {"ticker": "T3", "date": "2026-06-22", "OPEN0": 3.0, "MA_5": 30.0},
    ]
    df = pl.DataFrame(data)

    # Run scaling
    scaled = scale_features_cross_sectional(df, ["OPEN0", "MA_5"], scaler_type="RobustZScoreNorm")

    # Median of [1.0, 2.0, 3.0] is 2.0. So T2's scaled OPEN0 should be 0.0
    t2_open = scaled.filter(pl.col("ticker") == "T2").select("OPEN0").to_series().to_list()[0]
    assert abs(t2_open) < 1e-5


def test_perform_asof_join():
    """Verify perform_asof_join joins a daily benchmark without looking ahead."""
    data = [
        {"ticker": "T1", "date": "2026-06-22", "Open": 100.0, "High": 105.0, "Low": 95.0, "Close": 101.0, "Volume": 1000.0},
        {"ticker": "T2", "date": "2026-06-22", "Open": 200.0, "High": 205.0, "Low": 195.0, "Close": 201.0, "Volume": 2000.0},
    ]
    df = pl.DataFrame(data)

    joined = perform_asof_join(df)
    assert "macro_benchmark" in joined.columns
    assert joined.select("macro_benchmark").to_series().to_list() == [1.0, 1.0]


def test_perform_asof_join_multiple_tickers_and_dates():
    """Verify perform_asof_join with multiple tickers and dates does not crash due to sort order."""
    data = [
        {"ticker": "T1", "date": "2026-06-21", "Open": 100.0, "High": 105.0, "Low": 95.0, "Close": 101.0, "Volume": 1000.0},
        {"ticker": "T1", "date": "2026-06-22", "Open": 101.0, "High": 106.0, "Low": 96.0, "Close": 102.0, "Volume": 1100.0},
        {"ticker": "T2", "date": "2026-06-21", "Open": 200.0, "High": 205.0, "Low": 195.0, "Close": 201.0, "Volume": 2000.0},
        {"ticker": "T2", "date": "2026-06-22", "Open": 201.0, "High": 206.0, "Low": 196.0, "Close": 202.0, "Volume": 2100.0},
    ]
    df = pl.DataFrame(data)

    # This should not crash when sorting is applied internally
    joined = perform_asof_join(df)
    assert "macro_benchmark" in joined.columns
    assert joined.shape[0] == 4
    assert joined.select("macro_benchmark").to_series().to_list() == [1.0, 1.0, 1.0, 1.0]

