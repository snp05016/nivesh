"""
HTTP client for the ml-engine microservice (port 8001).

Provides cross-sectional ML predictions for individual stocks.
Every call is fire-and-forget-safe: timeouts, connection errors,
and malformed responses all return None — never raise into the
orchestrator and never cause 500s.
"""

import os
import asyncio
import logging
import time as _time
from datetime import datetime, time
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

ML_ENGINE_URL = os.getenv("ML_ENGINE_URL", "http://localhost:8001")
ML_ENGINE_TIMEOUT = float(os.getenv("ML_ENGINE_TIMEOUT", "5.0"))

# Training builds each row from the last 120 completed daily bars.
ML_MIN_HISTORY_ROWS = 120
ML_MAX_HISTORY_ROWS = 252
_IST = ZoneInfo("Asia/Kolkata")
# NSE closes at 15:30 IST; the day's bar is treated as final from 15:45.
_SESSION_FINAL_AT = time(15, 45)

# Last WARNING time per failure reason, so an ml-engine outage logs once a minute
# per cause instead of once per analysis.
# ponytail: per-process throttle; a metrics counter replaces it when one exists.
_WARN_INTERVAL_S = 60.0
_last_warned: dict[str, float] = {}


def _warn(reason: str, msg: str, *args, **kwargs) -> None:
    now = _time.monotonic()
    if now - _last_warned.get(reason, float("-inf")) < _WARN_INTERVAL_S:
        return
    _last_warned[reason] = now
    logger.warning(msg, *args, **kwargs)


def ml_engine_headers() -> dict[str, str]:
    """Shared-secret header for ml-engine calls (AUTH-21); empty when no key is set."""
    key = os.getenv("ML_ENGINE_API_KEY")
    return {"X-ML-Engine-Key": key} if key else {}


def build_ml_ohlcv_payload(df: pd.DataFrame | None, now: datetime | None = None) -> list[dict]:
    """Build the ml-engine OHLCV payload from a yfinance-style daily frame.

    The single builder for every backend caller, so all of them send the same
    shape as training: completed bars only (today's in-progress bar dropped),
    ascending unique dates, no NaN rows, and no ``vwap`` key (ml-engine then
    uses (H+L+C)/3, as training does). Returns [] when fewer than
    ML_MIN_HISTORY_ROWS completed bars remain.
    """
    cols = ["Open", "High", "Low", "Close", "Volume"]
    if df is None or df.empty or not set(cols).issubset(df.columns):
        return []
    frame = pd.DataFrame(df[cols]).dropna()
    idx = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)  # keep the exchange-local trading date
    frame = frame.set_axis(idx).sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]

    days = [ts.strftime("%Y-%m-%d") for ts in pd.DatetimeIndex(frame.index)]
    values = frame.to_numpy(dtype=float)
    now_ist = (now or datetime.now(_IST)).astimezone(_IST)
    if days and days[-1] == now_ist.strftime("%Y-%m-%d") and now_ist.time() < _SESSION_FINAL_AT:
        days, values = days[:-1], values[:-1]

    days, values = days[-ML_MAX_HISTORY_ROWS:], values[-ML_MAX_HISTORY_ROWS:]
    if len(days) < ML_MIN_HISTORY_ROWS:
        return []
    return [
        {"date": d, "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v)}
        for d, (o, h, l, c, v) in zip(days, values)
    ]


async def predict_cross_section(ticker: str, ohlcv_data: list) -> dict | None:
    """Call the ml-engine /predict/single endpoint for one ticker.

    The name is historical (kept to avoid churn in callers and tests); the
    request is a single-stock prediction, not a cross-section.

    Args:
        ticker: Stock ticker symbol (e.g. "RELIANCE").
        ohlcv_data: List of OHLCV dicts with keys
            open, high, low, close, volume (all float).

    Returns:
        dict with keys ``direction`` (int: -1 / 0 / +1),
        ``confidence`` (float 0-1) and ``p_up``, or **None** on any failure
        and whenever the engine reports no validated signal
        (``signal_state`` other than ``"ok"``).
    """
    try:
        async with httpx.AsyncClient(timeout=ML_ENGINE_TIMEOUT) as client:
            response = await client.post(
                f"{ML_ENGINE_URL}/predict/single",
                json={
                    "ticker": ticker,
                    "ohlcv_data": ohlcv_data,
                },
                headers=ml_engine_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                # Only a gated model's output carries a direction; anything else
                # (including an older engine without signal_state) is no signal.
                if data.get("signal_state") != "ok":
                    return None
                lightgbm_loaded = bool(data.get("lightgbm_loaded", False))
                ml_engine_mode = data.get("ml_engine_mode") or (
                    "trained_lightgbm_baseline"
                    if lightgbm_loaded
                    else "fallback_technical_heuristic"
                )
                fallback_used = data.get(
                    "fallback_used",
                    ml_engine_mode != "trained_lightgbm_baseline",
                )
                if data.get("model_validated"):
                    ml_engine_mode = "trained_live_calibrated"
                return {
                    "direction": data.get("direction", data.get("expected_direction")),
                    "confidence": data.get("confidence", data.get("confidence_score")),
                    "ml_engine_mode": ml_engine_mode,
                    "model_version": data.get("model_version"),
                    "lightgbm_loaded": lightgbm_loaded,
                    "horizon": data.get("horizon"),
                    "feature_count": data.get("feature_count"),
                    "fallback_used": fallback_used,
                    "p_up": data.get("p_up"),
                }
            _warn(
                f"http_{response.status_code}",
                "[ml_client] ml-engine /predict/single returned %s: %s",
                response.status_code,
                response.text[:200],
            )
            return None
    except (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadError,
        httpx.RemoteProtocolError,
        asyncio.TimeoutError,
        ValueError,
        OSError,
        RuntimeError,
    ) as exc:
        _warn(type(exc).__name__, "[ml_client] ml-engine call failed: %r", exc)
        return None


def predict_cross_section_sync(ticker: str, ohlcv_data: list) -> dict | None:
    """Synchronous wrapper suitable for ThreadPoolExecutor.

    Creates a fresh event loop because ThreadPoolExecutor threads
    do not carry one by default (and sharing loops across threads
    is unsafe).
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            predict_cross_section(ticker, ohlcv_data)
        )
    except Exception as e:
        _warn("sync", "[ml_client] sync call failed: %s", type(e).__name__, exc_info=True)
        return None
    finally:
        loop.close()
        asyncio.set_event_loop(None)
