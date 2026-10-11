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
    # Wilder smoothing, mirroring ta.momentum.RSIIndicator.
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_gain, avg_loss = float(gain.iloc[-1]), float(loss.iloc[-1])
    if np.isnan(avg_gain) or np.isnan(avg_loss):
        return 50.0  # insufficient history
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0  # no losses = max overbought; flat = neutral
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


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
        "corporate_action_suspected": False,
        "macd_bullish_cross": False,
        "macd_bearish_cross": False,
        "trend_regime": "NEUTRAL",
        "volatility_regime": "NORMAL",
        "momentum_score": 0,
        "regime_state": None,
        "regime_state_label": None,
        "regime_confidence_multiplier": None,
        "regime_description": None,
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

        # ── Corporate Action Detection (fix 2.1) ────────────────────────────
        if len(close) >= 2:
            single_day_pct = float(((close.iloc[-1] / close.iloc[-2]) - 1) * 100)
            if abs(single_day_pct) > 40:
                result["corporate_action_suspected"] = True
                # Override trend signals — a 40%+ move is a split/bonus, not a trend
                result["trend_regime"] = "CORPORATE_ACTION"
                result["golden_cross"] = False
                result["death_cross"] = False

        # ── Regime Classification ─────────────────────────────────────────────
        rsi_v = result["rsi_14"] or 50.0
        roc_v = result["roc_21"] or 0.0
        hv_v  = result["hist_vol_21_annualized"] or 25.0
        pct50 = result["price_vs_sma50_pct"] or 0.0

        # Skip trend classification if corporate action already detected
        if not result.get("corporate_action_suspected"):
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

        if hv_v == 0.0:
            # Flat-locked on consecutive circuit limits — no trading possible
            result["volatility_regime"] = "CRITICAL_LIQUIDITY_RISK"
        elif hv_v > 60:
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

        # ── HMM Market Regime Detection (GAP 2) ─────────────────────────────
        regime = detect_market_regime(close)
        result["regime_state"] = regime["state"]
        result["regime_state_label"] = regime["state_label"]
        result["regime_confidence_multiplier"] = regime["confidence_multiplier"]
        result["regime_description"] = regime["regime_description"]

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
        "MARKET REGIME (HMM):",
        f"  Regime State:     {r.get('regime_state', 'N/A')} ({r.get('regime_state_label', 'N/A')})",
        f"  Description:      {r.get('regime_description', 'N/A')}",
        f"  Conf Multiplier:  {r.get('regime_confidence_multiplier', 1.0)}x",
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


def detect_market_regime(close_series: pd.Series) -> dict:
    """
    Detect market regime using HMM on EGARCH(1,1) conditional volatility.

    Trains a 3-state GaussianHMM on rolling EGARCH(1,1) conditional vol.
    State 0 = Stable (lowest mean vol), State 2 = Crisis (highest mean vol).

    Falls back to hist_vol_21_annualized thresholds if hmmlearn/arch
    are unavailable.

    Returns:
        dict with keys: state, state_label, confidence_multiplier,
        regime_description
    """
    default = {
        "state": 1,
        "state_label": "NORMAL",
        "confidence_multiplier": 1.0,
        "regime_description": "Unknown regime (insufficient data)",
    }

    if close_series is None or len(close_series) < 50:
        return default

    # Try HMM-backed regime detection
    try:
        from hmmlearn.hmm import GaussianHMM

        try:
            from arch import arch_model
            ARCH_AVAILABLE = True
        except ImportError:
            ARCH_AVAILABLE = False

        log_ret = np.log(close_series / close_series.shift(1)).dropna() * 100

        if ARCH_AVAILABLE and len(log_ret) >= 60:
            am = arch_model(log_ret, vol="EGARCH", p=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)
            cond_vol = res.conditional_volatility.dropna().values.reshape(-1, 1)
        else:
            hv_series = log_ret.rolling(21).std().dropna() * np.sqrt(252)
            cond_vol = hv_series.values.reshape(-1, 1)

        if len(cond_vol) < 10:
            return default

        model = GaussianHMM(
            n_components=3,
            covariance_type="full",
            random_state=42,
            n_iter=500,
            tol=1e-4,
        )
        model.fit(cond_vol)
        hidden_states = model.predict(cond_vol)

        # Map states: 0 = lowest vol (Stable), 2 = highest vol (Crisis)
        state_means = {}
        for s in range(3):
            mask = hidden_states == s
            state_means[s] = float(np.mean(cond_vol[mask])) if mask.sum() > 0 else 0.0

        sorted_states = sorted(state_means, key=state_means.get)
        stable_idx = sorted_states[0]
        crisis_idx = sorted_states[-1]
        normal_idx = sorted_states[1]

        mapping = {stable_idx: 0, normal_idx: 1, crisis_idx: 2}
        current_state_raw = int(hidden_states[-1])
        mapped_state = mapping.get(current_state_raw, 1)

        current_vol = float(cond_vol[-1, 0])
        stable_mean = state_means.get(stable_idx, current_vol)
        crisis_mean = state_means.get(crisis_idx, current_vol)

        if crisis_mean > stable_mean:
            raw_mult = 1.0 + (current_vol - stable_mean) / (crisis_mean - stable_mean) * 0.5
        else:
            raw_mult = 1.0
        confidence_multiplier = round(min(max(raw_mult, 0.5), 1.5), 2)

        if mapped_state == 0:
            state_label = "STABLE"
            description = "Low-volatility regime; normal position sizing applies."
        elif mapped_state == 2:
            state_label = "CRISIS"
            description = "High-volatility regime; reduce position size and tighten stops."
        else:
            state_label = "NORMAL"
            description = "Moderate-volatility regime; standard risk parameters."

        return {
            "state": mapped_state,
            "state_label": state_label,
            "confidence_multiplier": confidence_multiplier,
            "regime_description": description,
        }

    except Exception as exc:
        logger.debug(f"[factor_engine] HMM regime detection failed: {exc}")

    # Fallback: hist_vol_21_annualized thresholds
    try:
        log_ret = np.log(close_series / close_series.shift(1)).dropna()
        hv = float(log_ret.rolling(21).std().iloc[-1]) * np.sqrt(252) * 100

        if hv > 60:
            return {
                "state": 2,
                "state_label": "CRISIS",
                "confidence_multiplier": 0.6,
                "regime_description": "High-volatility regime (fallback: HV-21 > 60)",
            }
        elif hv > 40:
            return {
                "state": 1,
                "state_label": "NORMAL",
                "confidence_multiplier": 0.8,
                "regime_description": "Elevated volatility (fallback: HV-21 40-60)",
            }
        elif hv < 15:
            return {
                "state": 0,
                "state_label": "STABLE",
                "confidence_multiplier": 1.0,
                "regime_description": "Low-volatility regime (fallback: HV-21 < 15)",
            }
        else:
            return {
                "state": 1,
                "state_label": "NORMAL",
                "confidence_multiplier": 1.0,
                "regime_description": "Normal volatility (fallback: HV-21 15-40)",
            }
    except Exception as _e:
        return default
