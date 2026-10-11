"""
Rate limiter with sliding-window counters for FastAPI endpoints.
Extracted from helpers.py to keep core infrastructure separate.
"""
from collections import defaultdict, deque
import threading
import time
from fastapi import HTTPException

# nested dict: store[client_id][bucket] = deque()
# ponytail: per-process memory, so N uvicorn workers allow N x each limit; move to
# Redis when the server runs several workers.
_rate_limit_store: dict[str, dict[str, deque[float]]] = defaultdict(lambda: defaultdict(deque))
_rate_limit_lock = threading.Lock()

# Exact "METHOD path" rules (routers are mounted at root) plus named buckets that
# callers pass themselves (research_compute). Exact, not prefix: the old "/analyze"
# prefix put the app's GET /analyze/job/<id> and /analyze/active polling on the
# 10-per-hour job-start budget (AUTH-11). Any other request gets "default", per path.
_RATE_LIMITS = {
    "POST /analyze": {"window": 3600, "max_requests": 10},
    "GET /quick-info": {"window": 60, "max_requests": 60},
    "POST /login": {"window": 60, "max_requests": 5},
    "POST /register": {"window": 3600, "max_requests": 10},
    "research_compute": {"window": 3600, "max_requests": 20},
    "default": {"window": 60, "max_requests": 120}
}

# Windows idle for longer than their own limit window are dropped this often, so
# one-off paths (job ids, tickers) cannot grow the store without bound.
_SWEEP_EVERY_SEC = 60
_last_sweep = 0.0


def _limits(bucket: str) -> dict:
    return _RATE_LIMITS.get(bucket, _RATE_LIMITS["default"])


def _sweep(now: float) -> None:
    """Drop windows with no request inside their own window, then empty clients."""
    for client_id in list(_rate_limit_store):
        buckets = _rate_limit_store[client_id]
        for bucket in [b for b, dq in buckets.items()
                       if not dq or now - dq[-1] > _limits(b)["window"]]:
            del buckets[bucket]
        if not buckets:
            del _rate_limit_store[client_id]


def _check_rate_limit(client_id: str, endpoint: str = "default", method: str | None = None) -> bool:
    """
    Checks the sliding window rate limit for the given client_id and endpoint.
    Limits: POST /analyze 10/hour, GET /quick-info 60/minute, POST /login 5/minute,
    POST /register 10/hour, research_compute 20/hour; any other path 120/minute.
    Raises HTTPException 429 with Retry-After header if exceeded.
    Returns True if allowed.
    """
    global _last_sweep
    now = time.time()
    bucket = f"{method} {endpoint}" if method else endpoint
    if bucket not in _RATE_LIMITS:
        bucket = endpoint  # no rule for this method + path: its own default window
    limits = _limits(bucket)
    window = limits["window"]
    max_reqs = limits["max_requests"]

    with _rate_limit_lock:
        if now - _last_sweep >= _SWEEP_EVERY_SEC:
            _sweep(now)
            _last_sweep = now

        dq = _rate_limit_store[client_id][bucket]

        while dq and now - dq[0] > window:
            dq.popleft()

        if len(dq) >= max_reqs:
            retry_after = int(window - (now - dq[0]))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(max(1, retry_after))}
            )

        dq.append(now)
        return True
