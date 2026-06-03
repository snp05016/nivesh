"""
Nivesh Factor Engine
--------------------
Deterministic pre-computation of all technical indicators from raw OHLCV data.

CRITICAL: Zero LLM calls. Every number is mathematically guaranteed.
Runs BEFORE LangGraph initializes so market_analyst receives exact values.

Uses `ta` library (0.11.0, Python 3.14 compatible) with numpy fallbacks.

Indicators:
  Momentum:    RSI-14, MACD (12/26/9), ROC-21
  Trend:       SMA-20/50/200, EMA-20/50
  Volatility:  ATR-14, Bollinger Bands, Historical Volatility (21d annualized)
  Volume:      OBV, Volume Ratio
  Crossovers:  Golden Cross, Death Cross, MACD signal cross
  Regimes:     Trend regime, Volatility regime, Momentum score (-100 to +100)
"""
import logging
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("[factor_engine] ta not installed. Using numpy fallbacks.")


def _rsi_numpy(close: pd.Series, period: int = 14) -> float:
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 2) if not np.isnan(val) else 50.0


def compute_indicators(df: pd.DataFrame, ticker: str = "") -> dict:
    """
    Compute all technical indicators from an OHLCV DataFrame.

    Args:
        df: DataFrame with columns [Open, High, Low, Close, Volume].
            Index must be DatetimeIndex. Minimum 250 rows recommended.
        ticker: Used only for log messages.

    Returns:
        dict with all computed values. Missing values are None (not NaN).
    """
    result = {
        "ticker": ticker,
        "computed_at": pd.Timestamp.now().isoformat(),
        "data_points": len(df) if df is not None else 0,
        "rsi_14": None,
        "macd_line": None,
        "macd_signal": None,
        "macd_histogram": None,
        "roc_21": None,
        "sma_20": None,
        "sma_50": None,
        "sma_200": None,
        "ema_20": None,
        "ema_50": None,
        "price_vs_sma50_pct": None,
        "price_vs_sma200_pct": None,
        "atr_14": None,
        "bb_upper": None,
        "bb_middle": None,
        "bb_lower": None,
        "bb_position": None,
        "hist_vol_21_annualized": None,
        "volume_sma_20": None,
        "volume_ratio": None,
        "obv": None,
        "golden_cross": False,
        "death_cross": False,
        "macd_bullish_cross": False,
        "macd_bearish_cross": False,
        "trend_regime": "NEUTRAL",
        "volatility_regime": "NORMAL",
        "momentum_score": 0,
    }

    if df is None or len(df) < 50:
        logger.warning(f"[factor_engine] {ticker}: Insufficient data ({len(df) if df is not None else 0} rows).")
        return result

    # Flatten MultiIndex columns (yfinance sometimes returns them)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1)
    df.columns = [str(c) for c in df.columns]

    close  = df["Close"].astype(float).squeeze()
    high   = df["High"].astype(float).squeeze()
    low    = df["Low"].astype(float).squeeze()
    volume = df["Volume"].astype(float).squeeze()
    current_price = float(close.iloc[-1])

    try:
        # ── RSI ──────────────────────────────────────────────────────────────
        if TA_AVAILABLE:
            rsi_ind = ta.momentum.RSIIndicator(close=close, window=14)
            rsi_val = rsi_ind.rsi().iloc[-1]
            result["rsi_14"] = round(float(rsi_val), 2) if not np.isnan(float(rsi_val)) else _rsi_numpy(close)
        else:
            result["rsi_14"] = _rsi_numpy(close)

        # ── MACD ─────────────────────────────────────────────────────────────
        if TA_AVAILABLE:
            macd_ind    = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
            macd_line   = macd_ind.macd()
            macd_signal = macd_ind.macd_signal()
            macd_hist   = macd_ind.macd_diff()
            result["macd_line"]      = round(float(macd_line.iloc[-1]), 4)
            result["macd_signal"]    = round(float(macd_signal.iloc[-1]), 4)
            result["macd_histogram"] = round(float(macd_hist.iloc[-1]), 4)
            if len(macd_hist) >= 2:
                prev_h = float(macd_hist.iloc[-2])
                curr_h = float(macd_hist.iloc[-1])
                if prev_h < 0 and curr_h > 0:
                    result["macd_bullish_cross"] = True
                elif prev_h > 0 and curr_h < 0:
                    result["macd_bearish_cross"] = True

        # ── SMAs ─────────────────────────────────────────────────────────────
        for period in [20, 50, 200]:
            if len(close) >= period:
                sma_val = round(float(close.rolling(period).mean().iloc[-1]), 2)
                result[f"sma_{period}"] = sma_val
                if period in (50, 200):
                    pct = round(((current_price - sma_val) / sma_val) * 100, 2)
                    result[f"price_vs_sma{period}_pct"] = pct

        # ── EMAs ─────────────────────────────────────────────────────────────
        for period in [20, 50]:
            if len(close) >= period:
                if TA_AVAILABLE:
                    ema_val = ta.trend.EMAIndicator(close=close, window=period).ema_indicator().iloc[-1]
                    result[f"ema_{period}"] = round(float(ema_val), 2)
                else:
                    result[f"ema_{period}"] = round(float(close.ewm(span=period, adjust=False).mean().iloc[-1]), 2)

        # ── Golden / Death Cross (within last 20 sessions) ───────────────────
        if result["sma_50"] and result["sma_200"] and len(close) >= 205:
            sma50  = close.rolling(50).mean()
            sma200 = close.rolling(200).mean()
            diff   = sma50 - sma200
            recent = diff.iloc[-20:]
            result["golden_cross"] = bool(((recent.shift(1) < 0) & (recent > 0)).any())
            result["death_cross"]  = bool(((recent.shift(1) > 0) & (recent < 0)).any())

        # ── ATR ────────────────────────────────────────────────────────────────
        if TA_AVAILABLE:
            atr_val = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1]
            result["atr_14"] = round(float(atr_val), 2)

        # ── Bollinger Bands ───────────────────────────────────────────────────
        if TA_AVAILABLE and len(close) >= 20:
            bb_ind = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
            upper  = float(bb_ind.bollinger_hband().iloc[-1])
            mid    = float(bb_ind.bollinger_mavg().iloc[-1])
            lower  = float(bb_ind.bollinger_lband().iloc[-1])
            result["bb_upper"]  = round(upper, 2)
            result["bb_middle"] = round(mid, 2)
            result["bb_lower"]  = round(lower, 2)
            band_width = upper - lower
            if band_width > 0:
                result["bb_position"] = round((current_price - lower) / band_width, 3)

        # ── Historical Volatility ─────────────────────────────────────────────
        if len(close) >= 22:
            log_ret = np.log(close / close.shift(1)).dropna()
            hv = float(log_ret.rolling(21).std().iloc[-1]) * np.sqrt(252) * 100
            result["hist_vol_21_annualized"] = round(hv, 2)

        # ── Volume ────────────────────────────────────────────────────────────
        if len(volume) >= 20:
            vol_sma = float(volume.rolling(20).mean().iloc[-1])
            result["volume_sma_20"] = round(vol_sma)
            curr_vol = float(volume.iloc[-1])
            result["volume_ratio"] = round(curr_vol / vol_sma, 2) if vol_sma > 0 else 1.0

        if TA_AVAILABLE:
            obv_val = ta.volume.OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume().iloc[-1]
            result["obv"] = int(obv_val)
        else:
            price_change = close.diff()
            obv_arr = np.where(price_change > 0, volume, np.where(price_change < 0, -volume, 0))
            result["obv"] = int(pd.Series(obv_arr).cumsum().iloc[-1])

        # ── Rate of Change ───────────────────────────────────────────────────
        if len(close) >= 22:
            result["roc_21"] = round(float(((close.iloc[-1] / close.iloc[-22]) - 1) * 100), 2)

        # ── Regime Classification ─────────────────────────────────────────────
        rsi_v = result["rsi_14"] or 50.0
        roc_v = result["roc_21"] or 0.0
        hv_v  = result["hist_vol_21_annualized"] or 25.0
        pct50 = result["price_vs_sma50_pct"] or 0.0

        if pct50 > 10 and roc_v > 15:
            result["trend_regime"] = "STRONG_UPTREND"
        elif pct50 > 3 and roc_v > 5:
            result["trend_regime"] = "UPTREND"
        elif pct50 < -10 and roc_v < -15:
            result["trend_regime"] = "STRONG_DOWNTREND"
        elif pct50 < -3 and roc_v < -5:
            result["trend_regime"] = "DOWNTREND"
        else:
            result["trend_regime"] = "NEUTRAL"

        if hv_v > 60:
            result["volatility_regime"] = "HIGH"
        elif hv_v > 40:
            result["volatility_regime"] = "ELEVATED"
        elif hv_v < 15:
            result["volatility_regime"] = "LOW"
        else:
            result["volatility_regime"] = "NORMAL"

        rsi_contrib = (rsi_v - 50) * 1.0
        roc_contrib = min(max(roc_v * 2, -50), 50)
        result["momentum_score"] = round(min(max(rsi_contrib + roc_contrib, -100), 100))

    except Exception as e:
        logger.error(f"[factor_engine] {ticker}: Computation error: {e}", exc_info=True)

    return result


def format_for_prompt(indicators: dict) -> str:
    """
    Format pre-computed indicators into a structured string for injection
    into the market_analyst prompt's HUMAN message (volatile layer only).
    Never inject into the static INDIAN_MARKET_SYSTEM_PROMPT cache breakpoint.
    """
    r = indicators
    lines = [
        "=== PRE-COMPUTED TECHNICAL INDICATORS (DETERMINISTIC — DO NOT RECOMPUTE) ===",
        f"Data points: {r.get('data_points', 'N/A')} sessions",
        "",
        "MOMENTUM:",
        f"  RSI-14:           {r.get('rsi_14', 'N/A')}",
        f"  MACD Line:        {r.get('macd_line', 'N/A')}",
        f"  MACD Signal:      {r.get('macd_signal', 'N/A')}",
        f"  MACD Histogram:   {r.get('macd_histogram', 'N/A')}",
        f"  ROC-21:           {r.get('roc_21', 'N/A')}%",
        f"  Momentum Score:   {r.get('momentum_score', 0)} / 100",
        "",
        "TREND:",
        f"  SMA-20:           ₹{r.get('sma_20', 'N/A')}",
        f"  SMA-50:           ₹{r.get('sma_50', 'N/A')}  ({r.get('price_vs_sma50_pct', 'N/A')}% vs price)",
        f"  SMA-200:          ₹{r.get('sma_200', 'N/A')}  ({r.get('price_vs_sma200_pct', 'N/A')}% vs price)",
        f"  EMA-20:           ₹{r.get('ema_20', 'N/A')}",
        f"  EMA-50:           ₹{r.get('ema_50', 'N/A')}",
        f"  Trend Regime:     {r.get('trend_regime', 'NEUTRAL')}",
        f"  Golden Cross:     {'YES — recent (within 20 sessions)' if r.get('golden_cross') else 'No'}",
        f"  Death Cross:      {'YES — recent (within 20 sessions)' if r.get('death_cross') else 'No'}",
        "",
        "VOLATILITY:",
        f"  ATR-14:           ₹{r.get('atr_14', 'N/A')}",
        f"  BB Upper:         ₹{r.get('bb_upper', 'N/A')}",
        f"  BB Middle:        ₹{r.get('bb_middle', 'N/A')}",
        f"  BB Lower:         ₹{r.get('bb_lower', 'N/A')}",
        f"  BB Position:      {r.get('bb_position', 'N/A')} (0=at lower band, 1=at upper band)",
        f"  HV-21 Ann.:       {r.get('hist_vol_21_annualized', 'N/A')}%",
        f"  Volatility Regime:{r.get('volatility_regime', 'NORMAL')}",
        "",
        "VOLUME:",
        f"  Volume Ratio:     {r.get('volume_ratio', 'N/A')}x 20-day avg",
        f"  OBV Trend:        {'Accumulation' if (r.get('obv') or 0) > 0 else 'Distribution'}",
        "",
        "CROSSOVER ALERTS:",
        f"  MACD Bullish Cross: {'YES' if r.get('macd_bullish_cross') else 'No'}",
        f"  MACD Bearish Cross: {'YES' if r.get('macd_bearish_cross') else 'No'}",
        "=== END PRE-COMPUTED INDICATORS ===",
    ]
    return "\n".join(lines)
