"""
HTTP client for the ml-engine microservice (port 8001).

Provides cross-sectional ML predictions for individual stocks.
Every call is fire-and-forget-safe: timeouts, connection errors,
and malformed responses all return None — never raise into the
orchestrator and never cause 500s.
"""

import os
import asyncio
import httpx

ML_ENGINE_URL = os.getenv("ML_ENGINE_URL", "http://localhost:8001")
ML_ENGINE_TIMEOUT = float(os.getenv("ML_ENGINE_TIMEOUT", "5.0"))


async def predict_cross_section(ticker: str, ohlcv_data: list) -> dict | None:
    """Call the ml-engine /predict/cross-section endpoint.

    Args:
        ticker: Stock ticker symbol (e.g. "RELIANCE").
        ohlcv_data: List of OHLCV dicts with keys
            open, high, low, close, volume (all float).

    Returns:
        dict with keys ``direction`` (int: -1 / 0 / +1) and
        ``confidence`` (float 0-1), or **None** on any failure.
    """
    try:
        async with httpx.AsyncClient(timeout=ML_ENGINE_TIMEOUT) as client:
            response = await client.post(
                f"{ML_ENGINE_URL}/predict/single",
                json={
                    "ticker": ticker,
                    "ohlcv_data": ohlcv_data,
                },
            )
            if response.status_code == 200:
                data = response.json()
                lightgbm_loaded = bool(data.get("lightgbm_loaded", False))
                ml_engine_mode = data.get("ml_engine_mode") or (
                    "trained_lightgbm_baseline"
                    if lightgbm_loaded
                    else "fallback_technical_heuristic"
                )
                return {
                    "direction": data.get("direction", data.get("expected_direction")),
                    "confidence": data.get("confidence", data.get("confidence_score")),
                    "ml_engine_mode": ml_engine_mode,
                    "model_version": data.get("model_version"),
                    "lightgbm_loaded": lightgbm_loaded,
                    "horizon": data.get("horizon"),
                    "feature_count": data.get("feature_count"),
                    "fallback_used": data.get(
                        "fallback_used",
                        ml_engine_mode != "trained_lightgbm_baseline",
                    ),
                }
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
    ):
        return None


def predict_cross_section_sync(ticker: str, ohlcv_data: list) -> dict | None:
    """Synchronous wrapper suitable for ThreadPoolExecutor.

    Creates a fresh event loop because ThreadPoolExecutor threads
    do not carry one by default (and sharing loops across threads
    is unsafe).
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            predict_cross_section(ticker, ohlcv_data)
        )
        loop.close()
        return result
    except Exception as _e:
        return None
