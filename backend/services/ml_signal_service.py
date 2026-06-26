"""
ML Signal Service

Proxies prediction requests to the ML engine at http://localhost:8001
and enriches responses with reliability metrics from the calibration service.
"""

import logging
import yfinance as yf
from datetime import datetime, timezone

import httpx

from schemas.ml_signal import FeatureDriver, MLReliability, MLSignalResponse

logger = logging.getLogger(__name__)

ML_ENGINE_URL = "http://localhost:8001/predict/single"
ML_ENGINE_TIMEOUT = 5.0  # seconds


def _direction_label(direction: int) -> str:
    """
    Map numeric direction to human-readable label.
    
    Args:
        direction (int): Numeric representation of the trend direction.
        
    Returns:
        str: "BULLISH" for 1, "BEARISH" for -1, and "NEUTRAL" otherwise.
    """
    if direction == 1:
        return "BULLISH"
    elif direction == -1:
        return "BEARISH"
    return "NEUTRAL"


def _build_unavailable_response(symbol: str, warning: str) -> MLSignalResponse:
    """
    Return a graceful unavailable response when the ML engine is unreachable.
    
    Args:
        symbol (str): The stock ticker symbol.
        warning (str): The specific reason why the ML engine is unavailable.
        
    Returns:
        MLSignalResponse: A populated response object indicating the service is unavailable.
    """
    return MLSignalResponse(
        symbol=symbol.strip().upper(),
        direction=0,
        direction_label="NEUTRAL",
        confidence=None,
        confidence_pct=None,
        model_version=None,
        model_status=None,
        ml_engine_mode="unavailable",
        lightgbm_loaded=False,
        prediction_horizon="20d",
        generated_at=datetime.now(timezone.utc).isoformat(),
        feature_drivers=[],
        reliability=None,
        status="unavailable",
        warning=warning,
    )


def _fetch_reliability() -> MLReliability | None:
    """Attempt to fetch reliability metrics from the calibration service."""
    try:
        from services.prediction_calibration_service import get_model_version_analytics

        analytics = get_model_version_analytics()
        if not analytics or not analytics.get("versions"):
            return None

        # Use the latest version's metrics
        versions = analytics["versions"]
        if not versions:
            return None

        latest = versions[0]
        return MLReliability(
            hit_rate_30d=latest.get("hit_rate"),
            brier_score_30d=latest.get("brier_score"),
            calibration_error_30d=latest.get("calibration_error"),
        )
    except Exception:
        logger.debug("Reliability metrics unavailable", exc_info=True)
        return None


def get_ml_signal(symbol: str) -> MLSignalResponse:
    """
    Fetch ML prediction signal for a given stock symbol.

    Calls the ML engine POST /predict/single endpoint. On failure or timeout,
    returns a graceful unavailable response instead of raising.
    """
    symbol = symbol.strip().upper()

    # Fetch recent OHLCV data for the ML engine
    ohlcv_data = []
    try:
        ns_ticker = f"{symbol}.NS" if not symbol.endswith((".NS", ".BO")) else symbol
        ticker_obj = yf.Ticker(ns_ticker)
        hist = ticker_obj.history(period="3mo")
        if not hist.empty:
            hist.index = hist.index.tz_localize(None)
            for dt, row in hist.tail(90).iterrows():
                ohlcv_data.append({
                    "date": dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
    except Exception as e:
        logger.warning("Failed to fetch OHLCV data for %s: %s", symbol, e)
        return _build_unavailable_response(symbol, f"Could not fetch OHLCV data: {e}")

    if len(ohlcv_data) < 5:
        return _build_unavailable_response(symbol, f"Insufficient OHLCV data ({len(ohlcv_data)} rows, need 5+)")

    try:
        with httpx.Client(timeout=ML_ENGINE_TIMEOUT) as client:
            resp = client.post(
                f"{ML_ENGINE_URL}/predict/single",
                json={"ticker": symbol, "ohlcv_data": ohlcv_data},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("ML engine timeout for %s", symbol)
        return _build_unavailable_response(symbol, "ML engine request timed out")
    except httpx.ConnectError:
        logger.warning("ML engine connection refused for %s", symbol)
        return _build_unavailable_response(symbol, "ML engine is not running")
    except httpx.HTTPStatusError as exc:
        logger.warning("ML engine returned %s for %s", exc.response.status_code, symbol)
        return _build_unavailable_response(
            symbol, f"ML engine returned HTTP {exc.response.status_code}"
        )
    except Exception:
        logger.exception("Unexpected error calling ML engine for %s", symbol)
        return _build_unavailable_response(symbol, "Unexpected error contacting ML engine")

    # Map ML engine response to our schema
    direction = data.get("direction", 0)
    confidence = data.get("confidence")
    confidence_pct = int(confidence * 100) if confidence is not None else None

    # Parse feature drivers if present
    feature_drivers = []
    for fd in data.get("feature_drivers", []):
        try:
            feature_drivers.append(FeatureDriver(
                feature=fd.get("feature", "unknown"),
                contribution=fd.get("contribution", 0.0),
                direction=fd.get("direction", "positive"),
            ))
        except Exception:
            continue

    # Fetch reliability metrics (best-effort, never crash)
    reliability = _fetch_reliability()

    return MLSignalResponse(
        symbol=symbol,
        direction=direction,
        direction_label=_direction_label(direction),
        confidence=confidence,
        confidence_pct=confidence_pct,
        model_version=data.get("model_version"),
        model_status=data.get("model_status"),
        ml_engine_mode=data.get("ml_engine_mode", "unknown"),
        lightgbm_loaded=data.get("lightgbm_loaded", False),
        prediction_horizon=data.get("prediction_horizon", "20d"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        feature_drivers=feature_drivers,
        reliability=reliability,
        status="ready",
        warning=data.get("warning"),
    )
