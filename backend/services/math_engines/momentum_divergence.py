import logging
"""
Task 17 — Momentum Divergence Detection.

Detects:
  - RSI divergence (bullish/bearish)
  - MACD crossover signals
  - Bollinger Band squeeze (low volatility → breakout incoming)
"""

from __future__ import annotations
import math
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class RsiDivergenceResponse(BaseModel):
    bullish_divergence: bool
    bearish_divergence: bool
    latest_rsi: Optional[float]
    signal: str
    description: str
    rsi_overbought: Optional[bool] = None
    rsi_oversold: Optional[bool] = None

class MacdCrossoverResponse(BaseModel):
    signal: str
    macd: Optional[float]
    signal_line: Optional[float]
    histogram: Optional[float]
    crossover: bool
    crossover_direction: Optional[str] = None
    description: str

class BollingerSqueezeResponse(BaseModel):
    squeeze: bool
    bandwidth: Optional[float]
    upper: Optional[float]
    lower: Optional[float]
    middle: Optional[float]
    signal: str
    direction_hint: Optional[str] = None
    description: str
    current_price: Optional[float] = None
    price_vs_upper: Optional[float] = None

def _compute_rsi(prices: list[float], period: int = 14) -> list[Optional[float]]:
    """Compute the Relative Strength Index (RSI) series.
    
    Args:
        prices (list[float]): Chronological list of closing prices.
        period (int, optional): The RSI calculation period. Defaults to 14.
        
    Returns:
        list[Optional[float]]: List of RSI values. Returns None for early positions 
            with insufficient data.
    """
    if len(prices) < period + 1:
        return [None] * len(prices)

    rsi: list[Optional[float]] = [None] * period
    gains = []
    losses = []

    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    def _rsi_from_avg(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    rsi.append(_rsi_from_avg(avg_gain, avg_loss))

    for i in range(period + 1, len(prices)):
        change = prices[i] - prices[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi.append(_rsi_from_avg(avg_gain, avg_loss))

    return rsi


def _ema(values: list[float], period: int) -> list[Optional[float]]:
    """Calculate the Exponential Moving Average (EMA).
    
    Args:
        values (list[float]): The series of values to average.
        period (int): The EMA period length.
        
    Returns:
        list[Optional[float]]: List of EMA values. Returns None for early positions.
    """
    if len(values) < period:
        return [None] * len(values)

    k = 2.0 / (period + 1)
    result: list[Optional[float]] = [None] * (period - 1)
    seed = sum(values[:period]) / period
    result.append(seed)

    for v in values[period:]:
        result.append(result[-1] * (1 - k) + v * k)  # type: ignore[operator]

    return result


def detect_rsi_divergence(prices: list[float], rsi_period: int = 14) -> RsiDivergenceResponse:
    """Detect bullish or bearish RSI divergence.

    Bullish divergence occurs when price makes a lower low, but RSI makes a higher low.
    Bearish divergence occurs when price makes a higher high, but RSI makes a lower high.

    Args:
        prices (list[float]): Chronological list of closing prices.
        rsi_period (int, optional): RSI calculation period. Defaults to 14.

    Returns:
        dict: A dictionary containing 'bullish_divergence', 'bearish_divergence', 
            'latest_rsi', 'signal', 'description', 'rsi_overbought', and 'rsi_oversold'.
    """
    if len(prices) < rsi_period + 5:
        return RsiDivergenceResponse(
            bullish_divergence=False,
            bearish_divergence=False,
            latest_rsi=None,
            signal="NEUTRAL",
            description="Insufficient data",
        )

    rsi_series = _compute_rsi(prices, rsi_period)
    valid_rsi = [(i, r) for i, r in enumerate(rsi_series) if r is not None]

    if len(valid_rsi) < 5:
        return RsiDivergenceResponse(
            bullish_divergence=False,
            bearish_divergence=False,
            latest_rsi=None,
            signal="NEUTRAL",
            description="Insufficient RSI data",
        )

    # Look at last N periods for divergence
    n = min(20, len(valid_rsi))
    recent_idx = [x[0] for x in valid_rsi[-n:]]
    recent_prices = [prices[i] for i in recent_idx]
    recent_rsi = [x[1] for x in valid_rsi[-n:]]

    # Identify price swing lows and highs by checking adjacent points
    def find_local_extrema(series: list[float]) -> tuple[list[int], list[int]]:
        lows, highs = [], []
        for i in range(1, len(series) - 1):
            if series[i] < series[i - 1] and series[i] < series[i + 1]:
                lows.append(i)
            if series[i] > series[i - 1] and series[i] > series[i + 1]:
                highs.append(i)
        return lows, highs

    p_lows, p_highs = find_local_extrema(recent_prices)
    r_lows, r_highs = find_local_extrema(recent_rsi)

    bullish_divergence = False
    bearish_divergence = False

    # Bullish Divergence check: price lower low but RSI higher low
    if len(p_lows) >= 2 and len(r_lows) >= 2:
        pl1, pl2 = p_lows[-2], p_lows[-1]
        if recent_prices[pl2] < recent_prices[pl1] and recent_rsi[pl2] > recent_rsi[pl1]:
            bullish_divergence = True

    # Bearish Divergence check: price higher high but RSI lower high
    if len(p_highs) >= 2 and len(r_highs) >= 2:
        ph1, ph2 = p_highs[-2], p_highs[-1]
        if recent_prices[ph2] > recent_prices[ph1] and recent_rsi[ph2] < recent_rsi[ph1]:
            bearish_divergence = True

    latest_rsi = valid_rsi[-1][1] if valid_rsi else None

    if bullish_divergence and not bearish_divergence:
        signal = "BULLISH"
        description = "Price lower low with RSI higher low — potential reversal upward"
    elif bearish_divergence and not bullish_divergence:
        signal = "BEARISH"
        description = "Price higher high with RSI lower high — potential reversal downward"
    elif bullish_divergence and bearish_divergence:
        signal = "MIXED"
        description = "Conflicting divergence signals"
    else:
        signal = "NEUTRAL"
        description = "No divergence detected"

    return RsiDivergenceResponse(
        bullish_divergence=bullish_divergence,
        bearish_divergence=bearish_divergence,
        latest_rsi=round(latest_rsi, 2) if latest_rsi is not None else None,
        signal=signal,
        description=description,
        rsi_overbought=(latest_rsi or 50) > 70,
        rsi_oversold=(latest_rsi or 50) < 30,
    )


def detect_macd_crossover(prices: list[float]) -> MacdCrossoverResponse:
    """Detect MACD crossover signals using 12/26/9 standard parameters.

    Args:
        prices (list[float]): Chronological list of closing prices.

    Returns:
        dict: A dictionary with 'signal' (BULLISH/BEARISH/NEUTRAL), 'macd', 
            'signal_line', 'histogram', 'crossover' (bool), and 'crossover_direction'.
    """
    if len(prices) < 35:
        return MacdCrossoverResponse(
            signal="NEUTRAL",
            macd=None,
            signal_line=None,
            histogram=None,
            crossover=False,
            crossover_direction=None,
            description="Insufficient data (need 35+ prices)",
        )

    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)

    macd_line: list[Optional[float]] = []
    for e12, e26 in zip(ema12, ema26):
        if e12 is not None and e26 is not None:
            macd_line.append(e12 - e26)
        else:
            macd_line.append(None)

    valid_macd = [m for m in macd_line if m is not None]
    if len(valid_macd) < 9:
        return MacdCrossoverResponse(
            signal="NEUTRAL",
            macd=None,
            signal_line=None,
            histogram=None,
            crossover=False,
            crossover_direction=None,
            description="Insufficient MACD data",
        )

    signal_ema = _ema(valid_macd, 9)
    valid_signal = [(m, s) for m, s in zip(valid_macd, signal_ema) if s is not None]

    if len(valid_signal) < 2:
        return MacdCrossoverResponse(
            signal="NEUTRAL",
            macd=None,
            signal_line=None,
            histogram=None,
            crossover=False,
            crossover_direction=None,
            description="Insufficient signal line data",
        )

    prev_macd, prev_sig = valid_signal[-2]
    curr_macd, curr_sig = valid_signal[-1]
    histogram = curr_macd - curr_sig
    prev_histogram = prev_macd - prev_sig

    crossover = (prev_histogram < 0 and histogram > 0) or (prev_histogram > 0 and histogram < 0)

    if prev_histogram < 0 and histogram > 0:
        crossover_direction = "BULLISH"
        signal = "BULLISH"
        description = "MACD crossed above signal line — bullish momentum"
    elif prev_histogram > 0 and histogram < 0:
        crossover_direction = "BEARISH"
        signal = "BEARISH"
        description = "MACD crossed below signal line — bearish momentum"
    else:
        crossover_direction = None
        signal = "BULLISH" if histogram > 0 else "BEARISH"
        description = f"No crossover. MACD {'above' if histogram > 0 else 'below'} signal line"

    return MacdCrossoverResponse(
        signal=signal,
        macd=round(curr_macd, 4),
        signal_line=round(curr_sig, 4),
        histogram=round(histogram, 4),
        crossover=crossover,
        crossover_direction=crossover_direction,
        description=description,
    )


def detect_bollinger_squeeze(
    prices: list[float], period: int = 20, std_dev: float = 2.0
) -> BollingerSqueezeResponse:
    """Detect Bollinger Band squeeze.
    
    A squeeze indicates low volatility and potentially an incoming breakout,
    identified when the bandwidth is at a multi-period low.

    Args:
        prices (list[float]): Chronological list of closing prices.
        period (int, optional): Moving average period. Defaults to 20.
        std_dev (float, optional): Standard deviation multiplier. Defaults to 2.0.

    Returns:
        dict: A dictionary with 'squeeze' (bool), 'bandwidth', 'upper', 'lower', 
            'middle', 'signal', 'direction_hint', and 'description'.
    """
    if len(prices) < period + 10:
        return BollingerSqueezeResponse(
            squeeze=False,
            bandwidth=None,
            upper=None,
            lower=None,
            middle=None,
            signal="NEUTRAL",
            description="Insufficient data",
        )

    # Compute rolling Bollinger Bands
    bandwidths = []
    for i in range(period, len(prices) + 1):
        window = prices[i - period : i]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = math.sqrt(variance)
        upper = mean + std_dev * sd
        lower = mean - std_dev * sd
        bw = (upper - lower) / mean if mean else 0
        bandwidths.append((mean, upper, lower, bw))

    if not bandwidths:
        return BollingerSqueezeResponse(
            squeeze=False,
            bandwidth=None,
            upper=None,
            lower=None,
            middle=None,
            signal="NEUTRAL",
            description="No bands computed",
        )

    current_mean, current_upper, current_lower, current_bw = bandwidths[-1]

    # Evaluate Squeeze: determine if current bandwidth is within the bottom 20% of the recent range
    lookback_bws = [b[3] for b in bandwidths[-20:]]
    bw_min = min(lookback_bws)
    bw_max = max(lookback_bws)
    bw_range = bw_max - bw_min if bw_max > bw_min else 1

    squeeze_threshold = bw_min + 0.2 * bw_range
    squeeze = current_bw <= squeeze_threshold

    # Direction hint based on whether the current price sits above or below the middle band
    current_price = prices[-1]
    direction_hint = "UPWARD" if current_price > current_mean else "DOWNWARD"

    if squeeze:
        signal = "SQUEEZE"
        description = f"Bollinger squeeze detected — expect {direction_hint} breakout"
    else:
        signal = "NEUTRAL"
        description = "No squeeze — normal volatility"

    return BollingerSqueezeResponse(
        squeeze=squeeze,
        bandwidth=round(current_bw, 4),
        upper=round(current_upper, 2),
        lower=round(current_lower, 2),
        middle=round(current_mean, 2),
        signal=signal,
        direction_hint=direction_hint,
        description=description,
        current_price=round(current_price, 2),
        price_vs_upper=round((current_price - current_upper) / current_upper * 100, 2),
    )


if __name__ == "__main__":
    import random
    random.seed(42)

    # Simulate 60 days of prices with a slight uptrend
    prices = [100.0]
    for _ in range(59):
        prices.append(prices[-1] * (1 + random.uniform(-0.02, 0.025)))

    rsi_result = detect_rsi_divergence(prices)
    logging.info(f"RSI divergence: {rsi_result.signal} — {rsi_result.description}")
    assert rsi_result.signal in {"BULLISH", "BEARISH", "NEUTRAL", "MIXED"}

    macd_result = detect_macd_crossover(prices)
    logging.info(f"MACD: {macd_result.signal} — {macd_result.description}")
    assert macd_result.signal in {"BULLISH", "BEARISH", "NEUTRAL"}

    bb_result = detect_bollinger_squeeze(prices)
    logging.info(f"Bollinger: {bb_result.signal} — {bb_result.description}")
    assert bb_result.signal in {"SQUEEZE", "NEUTRAL"}

    logging.info("All momentum_divergence tests passed.")
