"""
Seasonality Analysis Engine
Provides functions for detecting and analyzing seasonal patterns in financial time series.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

def calculate_monthly_returns_seasonality(
    df: pd.DataFrame, 
    date_col: str, 
    price_col: str
) -> pd.DataFrame:
    """
    Calculates the average return for each month across all years to detect monthly seasonality.
    
    Args:
        df: DataFrame containing historical prices
        date_col: Name of the date column
        price_col: Name of the price column
        
    Returns:
        DataFrame with average return and win rate per month
    """
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(by=date_col)
    
    # Calculate daily returns
    data['return'] = data[price_col].pct_change()
    
    # Extract month and year
    data['year'] = data[date_col].dt.year
    data['month'] = data[date_col].dt.month
    
    # Calculate monthly returns
    monthly_data = data.groupby(['year', 'month'])['return'].apply(
        lambda x: (1 + x).prod() - 1
    ).reset_index(name='monthly_return')
    
    # Calculate stats per month
    seasonality_stats = monthly_data.groupby('month').agg(
        avg_return=('monthly_return', 'mean'),
        median_return=('monthly_return', 'median'),
        win_rate=('monthly_return', lambda x: (x > 0).mean() * 100),
        count=('monthly_return', 'count')
    ).reset_index()
    
    return seasonality_stats

def detect_day_of_week_seasonality(
    df: pd.DataFrame, 
    date_col: str, 
    price_col: str
) -> pd.DataFrame:
    """
    Calculates average returns by day of the week to detect day-of-week seasonality.
    
    Args:
        df: DataFrame containing historical prices
        date_col: Name of the date column
        price_col: Name of the price column
        
    Returns:
        DataFrame with average return per day of the week
    """
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.sort_values(by=date_col)
    
    # Calculate daily returns
    data['return'] = data[price_col].pct_change()
    
    # Extract day of week (0=Monday, 6=Sunday)
    data['day_of_week'] = data[date_col].dt.dayofweek
    data['day_name'] = data[date_col].dt.day_name()
    
    # Calculate stats per day of week
    dow_stats = data.groupby(['day_of_week', 'day_name']).agg(
        avg_return=('return', 'mean'),
        win_rate=('return', lambda x: (x > 0).mean() * 100),
        count=('return', 'count')
    ).reset_index()
    
    return dow_stats
