"""
Task 54: Token bucket rate limiter for yfinance API calls.
Prevents hitting yfinance rate limits by metering outbound requests.
"""
import threading
import time
import os

_YF_BUCKET_LOCK = threading.Lock()
_YF_TOKENS: float = float(os.getenv("YF_RATE_LIMIT_TOKENS", 30))
_YF_RATE: float = float(os.getenv("YF_RATE_LIMIT_PER_SEC", 0.5))
_YF_LAST: float = time.monotonic()


def yf_acquire() -> None:
    """Block until a yfinance request token is available (token bucket algorithm)."""
    global _YF_TOKENS, _YF_LAST
    with _YF_BUCKET_LOCK:
        now = time.monotonic()
        # Refill tokens based on elapsed time
        _YF_TOKENS = min(
            float(os.getenv("YF_RATE_LIMIT_TOKENS", 30)),
            _YF_TOKENS + (now - _YF_LAST) * _YF_RATE,
        )
        _YF_LAST = now
        if _YF_TOKENS < 1:
            sleep_for = (1 - _YF_TOKENS) / _YF_RATE
            time.sleep(sleep_for)
            _YF_TOKENS = 0.0
        else:
            _YF_TOKENS -= 1


def yf_bucket_status() -> dict:
    """Return current bucket state for health/debug endpoints."""
    with _YF_BUCKET_LOCK:
        return {
            "tokens_available": round(_YF_TOKENS, 2),
            "rate_per_sec": _YF_RATE,
            "max_tokens": float(os.getenv("YF_RATE_LIMIT_TOKENS", 30)),
        }
