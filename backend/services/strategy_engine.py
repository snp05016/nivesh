"""
services/strategy_engine.py — Backtesting and execution engine for quantitative strategies.

Provides functions to run historical backtests, calculate performance metrics like CAGR
and Sharpe ratio, and evaluate predefined technical trading rules.
"""
import math
from typing import Dict, Any, List
import pandas as pd
import yfinance as yf
from datetime import timedelta
import logging

from services.factor_engine import compute_indicators

logger = logging.getLogger(__name__)

def _calculate_cagr(start_value: float, end_value: float, days: int) -> float:
    """
    Calculate the Compound Annual Growth Rate (CAGR).

    Args:
        start_value (float): The initial investment value.
        end_value (float): The final investment value.
        days (int): The total number of invested days.

    Returns:
        float: The annualized CAGR percentage.
    """
    if days <= 0 or start_value <= 0:
        return 0.0
    years = days / 252.0
    cagr = (math.pow(end_value / start_value, 1.0 / years) - 1.0) * 100
    return round(cagr, 2)

def _calculate_sharpe(returns: List[float], risk_free_rate: float = 0.05) -> float:
    """
    Calculate the annualized Sharpe Ratio from a series of daily returns.

    Args:
        returns (List[float]): A list of daily percentage returns.
        risk_free_rate (float): The annualized risk-free interest rate. Defaults to 0.05.

    Returns:
        float: The computed Sharpe ratio.
    """
    if not returns or len(returns) < 2:
        return 0.0
    returns_series = pd.Series(returns)
    mean_return = returns_series.mean() * 252
    std_return = returns_series.std() * math.sqrt(252)
    if std_return == 0:
        return 0.0
    sharpe = (mean_return - risk_free_rate) / std_return
    return round(sharpe, 2)

def _calculate_max_drawdown(equity_curve: List[Dict[str, Any]]) -> float:
    """
    Calculate the maximum peak-to-trough drawdown from an equity curve.

    Args:
        equity_curve (List[Dict[str, Any]]): A list of dictionaries representing portfolio values over time.

    Returns:
        float: The maximum drawdown as a positive percentage.
    """
    max_dd = 0.0
    peak = -1.0
    for point in equity_curve:
        val = point["portfolio_value"]
        if val > peak:
            peak = val
        dd = (val - peak) / peak if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)

def run_backtest(ticker: str, strategy_id: str, years: int = 5) -> Dict[str, Any]:
    """
    Run a historical backtest for a specific trading strategy on a given ticker.

    Args:
        ticker (str): The stock ticker symbol.
        strategy_id (str): The identifier for the strategy to test (e.g., 'rsi_oversold').
        years (int): Number of years of historical data to backtest. Defaults to 5.

    Returns:
        Dict[str, Any]: A dictionary containing backtest metrics like CAGR, Sharpe ratio,
        max drawdown, win rate, individual trades, and the equity curve.
    """
    # 1. Fetch historical data
    end_date = pd.Timestamp.now()
    start_date = end_date - timedelta(days=years * 365 + 300) # extra for warmup
    
    ticker_obj = yf.Ticker(ticker)
    df = ticker_obj.history(start=start_date, end=end_date)
    if df.empty or len(df) < 200:
        raise ValueError(f"Not enough data for {ticker}")
        
    df.index = df.index.tz_localize(None)
    start_backtest_date = end_date.tz_localize(None) - timedelta(days=years * 365)
    
    # Pre-fetch info for PE / Promoter
    info = ticker_obj.info
    current_pe = info.get("trailingPE", 25.0)
    promoter_holding = info.get("heldPercentInsiders", 0) * 100
    current_price = float(df['Close'].iloc[-1])
    eps = current_price / current_pe if current_pe else 1.0
    sector_pe = 25.0
    
    # Dividends for Dividend Capture
    dividends = ticker_obj.dividends
    div_dates = []
    if not dividends.empty:
        dividends.index = dividends.index.tz_localize(None)
        div_dates = [d.date() for d in dividends.index]
    
    # Filter backtest days
    bt_df = df[df.index >= start_backtest_date].copy()
    if bt_df.empty:
        raise ValueError("No data in backtest window")
        
    initial_capital = 100000.0
    cash = initial_capital
    shares = 0
    trades = []
    equity_curve = []
    
    b_cash = initial_capital
    b_shares = 0
    b_first_day = True
    
    entry_price = 0.0
    entry_date = None
    
    cost_factor = 0.0025 # 0.1% brokerage + 0.1% STT + 0.05% slippage
    
    # For daily returns calculation (for Sharpe)
    daily_returns = []
    prev_portfolio_value = initial_capital
    
    consecutive_down_days = 0

    # Iteration
    for i in range(len(df)):
        current_dt = df.index[i]
        if current_dt < start_backtest_date:
            continue
            
        close = float(df['Close'].iloc[i])
        
        # Benchmark logic
        if b_first_day:
            b_shares = math.floor(b_cash / close)
            b_cash -= b_shares * close * (1 + cost_factor)
            b_first_day = False
            
        benchmark_value = b_cash + b_shares * close
        
        # Indicators (only compute if needed by strategy, but to be safe we compute for all except buy_hold)
        ind = {}
        if strategy_id not in ["buy_and_hold", "dividend_capture"]:
            # df.iloc[:i+1] is data up to current day
            ind = compute_indicators(df.iloc[:i+1], ticker)
            
        # Down days counter
        if i > 0 and df['Close'].iloc[i] < df['Close'].iloc[i-1]:
            consecutive_down_days += 1
        else:
            consecutive_down_days = 0
            
        # Strategy Logic
        signal = 0 # 1 for buy, -1 for sell
        
        if strategy_id == "rsi_oversold":
            rsi = ind.get("rsi_14")
            if rsi is not None:
                if rsi < 30 and shares == 0:
                    signal = 1
                elif rsi > 70 and shares > 0:
                    signal = -1
                    
        elif strategy_id == "golden_cross":
            sma50 = ind.get("sma_50")
            sma200 = ind.get("sma_200")
            if sma50 and sma200:
                # To detect exact crossover, we should look at previous day too, 
                # but we can rely on the factor engine's golden_cross boolean
                # wait, golden_cross in factor engine stays true for 20 days.
                # If we have 0 shares, we buy.
                if ind.get("golden_cross") and shares == 0:
                    signal = 1
                elif ind.get("death_cross") and shares > 0:
                    signal = -1
                    
        elif strategy_id == "low_pe_promoter":
            hist_pe = close / eps if eps > 0 else 25.0
            if hist_pe < sector_pe and promoter_holding > 50.0 and shares == 0:
                signal = 1
            elif hist_pe > 1.5 * sector_pe and shares > 0:
                signal = -1
                
        elif strategy_id == "momentum_roc":
            roc = ind.get("roc_21")
            if roc is not None:
                if roc > 0 and shares == 0:
                    signal = 1
                elif roc < 0 and consecutive_down_days >= 5 and shares > 0:
                    signal = -1
                    
        elif strategy_id == "bollinger_reversion":
            pos = ind.get("bb_position")
            if pos is not None:
                if pos <= 0 and shares == 0:
                    signal = 1
                elif pos >= 0.5 and shares > 0: # > 0.5 means touching middle band
                    signal = -1
                    
        elif strategy_id == "volume_breakout":
            vol = float(df['Volume'].iloc[i])
            vol_sma = ind.get("volume_sma_20")
            sma50 = ind.get("sma_50")
            if vol_sma and sma50:
                if vol > 2 * vol_sma and close > sma50 and shares == 0:
                    signal = 1
                elif vol < vol_sma and shares > 0:
                    signal = -1
                    
        elif strategy_id == "macd_signal":
            if ind.get("macd_bullish_cross") and shares == 0:
                signal = 1
            elif ind.get("macd_bearish_cross") and shares > 0:
                signal = -1
                
        elif strategy_id == "buy_and_hold":
            if shares == 0 and b_first_day is False: # we buy on first day
                signal = 1
            elif i == len(df) - 1 and shares > 0:
                signal = -1
                
        elif strategy_id == "dividend_capture":
            # Check if there is a dividend ex-date in next 3 trading days
            # Looking ahead is fine for backtesting this specific mechanical strategy 
            # (as corporate actions are announced in advance)
            if i + 3 < len(df):
                future_date = df.index[i + 3].date()
                if future_date in div_dates:
                    if shares == 0:
                        signal = 1
            # Sell on ex-date
            if current_dt.date() in div_dates and shares > 0:
                signal = -1
                
        elif strategy_id == "low_volatility":
            hv = ind.get("hist_vol_21_annualized")
            if hv is not None:
                if hv < 15 and shares == 0:
                    signal = 1
                elif hv > 30 and shares > 0:
                    signal = -1

        # Execute signals
        if signal == 1 and shares == 0:
            qty = math.floor(cash / close)
            if qty > 0:
                cost = qty * close * (1 + cost_factor)
                cash -= cost
                shares = qty
                entry_price = close
                entry_date = current_dt

        elif signal == -1 and shares > 0:
            proceeds = shares * close * (1 - cost_factor)
            cash += proceeds
            
            # Record trade
            ret_pct = ((close * (1 - cost_factor)) / (entry_price * (1 + cost_factor)) - 1) * 100
            holding_days = (current_dt - entry_date).days
            trades.append({
                "entry_date": entry_date.strftime("%Y-%m-%d"),
                "exit_date": current_dt.strftime("%Y-%m-%d"),
                "entry_price": round(entry_price, 2),
                "exit_price": round(close, 2),
                "return_pct": round(ret_pct, 2),
                "holding_days": holding_days
            })
            shares = 0
            
        # Dividend capture (add cash for dividends if held on ex-date)
        if shares > 0 and not dividends.empty and current_dt.date() in div_dates:
            # find the div amount
            div_idx = [idx for idx in dividends.index if idx.date() == current_dt.date()][0]
            div_amt = dividends.loc[div_idx]
            cash += shares * float(div_amt)
            
        # Equity curve update
        portfolio_value = cash + shares * close
        equity_curve.append({
            "date": current_dt.strftime("%Y-%m-%d"),
            "portfolio_value": round(portfolio_value, 2),
            "benchmark_value": round(benchmark_value, 2)
        })
        
        # Calculate daily return for Sharpe
        ret = (portfolio_value - prev_portfolio_value) / prev_portfolio_value
        daily_returns.append(ret)
        prev_portfolio_value = portfolio_value

    # Close open position on last day
    if shares > 0:
        last_close = float(df['Close'].iloc[-1])
        last_dt = df.index[-1]
        proceeds = shares * last_close * (1 - cost_factor)
        cash += proceeds
        ret_pct = ((last_close * (1 - cost_factor)) / (entry_price * (1 + cost_factor)) - 1) * 100
        holding_days = (last_dt - entry_date).days
        trades.append({
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "exit_date": last_dt.strftime("%Y-%m-%d"),
            "entry_price": round(entry_price, 2),
            "exit_price": round(last_close, 2),
            "return_pct": round(ret_pct, 2),
            "holding_days": holding_days
        })
        shares = 0
        portfolio_value = cash
        equity_curve[-1]["portfolio_value"] = round(portfolio_value, 2)
        
    # Metrics
    final_value = equity_curve[-1]["portfolio_value"]
    total_days = (bt_df.index[-1] - bt_df.index[0]).days
    
    cagr = _calculate_cagr(initial_capital, final_value, total_days)
    sharpe_ratio = _calculate_sharpe(daily_returns)
    max_drawdown = _calculate_max_drawdown(equity_curve)
    
    win_trades = [t for t in trades if t["return_pct"] > 0]
    win_rate = (len(win_trades) / len(trades) * 100) if trades else 0.0
    
    b_final_value = equity_curve[-1]["benchmark_value"]
    b_cagr = _calculate_cagr(initial_capital, b_final_value, total_days)
    outperformance = round(cagr - b_cagr, 2)
    
    return {
        "cagr": cagr,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "win_rate": round(win_rate, 2),
        "outperformance": outperformance,
        "trades": trades,
        "equity_curve": equity_curve
    }
