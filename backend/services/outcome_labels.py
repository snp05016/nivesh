"""
Outcome labels: the one definition of "was this call right" (ML-15).

Every evaluator (AnalysisPrediction tracker, AnalysisHistory evaluator) scores a
signal through direction_hit() so the vocabulary and the abstain rule cannot drift
apart again, and prices both ends of a window from one auto-adjusted daily series
(fetch_adjusted_history) so splits and bonuses cancel out.
"""

import math
from typing import Any, Optional

import pandas as pd
import yfinance as yf

# Rows with no usable prices this long after the prediction get a terminal outcome (delisted).
UNRESOLVABLE_AGE_DAYS = 120

# Directional calls. HOLD, NEUTRAL and anything unknown map to 0 (abstain).
SIGNAL_DIRECTION = {
    "BULLISH": 1,
    "CAUTIOUSLY BULLISH": 1,
    "BUY": 1,
    "STRONG BUY": 1,
    "ACCUMULATE": 1,
    "BEARISH": -1,
    "CAUTIOUSLY BEARISH": -1,
    "SELL": -1,
    "STRONG SELL": -1,
    "AVOID": -1,
    "REDUCE": -1,
    "EXIT": -1,
}


def signal_direction(signal: Any) -> int:
    """Return +1 / -1 for a directional signal, 0 for HOLD, NEUTRAL or unknown."""
    key = str(signal or "").upper().strip().replace("_", " ")
    return SIGNAL_DIRECTION.get(key, 0)


def direction_hit(signal: Any, ret: Optional[float]) -> Optional[bool]:
    """True/False for a directional call given its realised return; None = abstain.

    A zero return counts as a miss for both directions.
    """
    direction = signal_direction(signal)
    if direction == 0 or ret is None or math.isnan(ret):
        return None
    return ret > 0 if direction == 1 else ret < 0


def fetch_adjusted_history(symbol: str, **history_kwargs):
    """Auto-adjusted daily history with a tz-naive, date-normalised index, or None if empty.

    history_kwargs go to yf.Ticker.history (default period="2y"). NSE symbols get ".NS".
    """
    yf_symbol = symbol if symbol.startswith("^") or symbol.endswith((".NS", ".BO")) else f"{symbol}.NS"
    if "start" not in history_kwargs:
        history_kwargs.setdefault("period", "2y")
    hist = yf.Ticker(yf_symbol).history(auto_adjust=True, **history_kwargs)
    if hist is None or hist.empty:
        return None
    hist.index = hist.index.tz_localize(None).normalize()  # pyright: ignore[reportAttributeAccessIssue]  (DatetimeIndex)
    return hist


def close_on_or_before(hist, ts) -> Optional[float]:
    """Last close at or before ts, or None."""
    closes = hist.loc[hist.index <= pd.Timestamp(ts), "Close"]
    return float(closes.iloc[-1]) if len(closes) else None


def close_on_or_after(hist, ts) -> Optional[float]:
    """First close at or after ts, or None."""
    closes = hist.loc[hist.index >= pd.Timestamp(ts), "Close"]
    return float(closes.iloc[0]) if len(closes) else None


def window_return(hist, anchor, exit_on) -> Optional[float]:
    """Return from the close on/before anchor to the first close on/after exit_on, both from hist."""
    if hist is None:
        return None
    entry = close_on_or_before(hist, anchor)
    exit_ = close_on_or_after(hist, exit_on)
    if not entry or entry <= 0 or exit_ is None:
        return None
    return (exit_ - entry) / entry
