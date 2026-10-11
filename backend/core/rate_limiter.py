"""
Rate limiter with sliding-window counters for FastAPI endpoints.
Extracted from helpers.py to keep core infrastructure separate.
"""
from collections import defaultdict, deque
import logging
import os
import threading
import time
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Fallback when Redis is unreachable: nested dict store[client_id][bucket] = deque().
# Per-process, so then N uvicorn workers allow N x each limit (FINSEC-23).
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
    # Per-user write buckets for identity and money endpoints (core.security.rate_limited_user).
    "kyc_consent": {"window": 3600, "max_requests": 30},
    "kyc_bind": {"window": 3600, "max_requests": 20},
    "money_write": {"window": 3600, "max_requests": 30},
    "subscription": {"window": 3600, "max_requests": 10},
    "compliance": {"window": 3600, "max_requests": 10},
    "default": {"window": 60, "max_requests": 120}
}

# Windows idle for longer than their own limit window are dropped this often, so
# one-off paths (job ids, tickers) cannot grow the store without bound.
_SWEEP_EVERY_SEC = 60
_last_sweep = 0.0

# Shared counters live in Redis so every uvicorn worker sees the same counts.
# ponytail: process-local circuit breaker; after a Redis error each worker uses its
# own memory for _REDIS_RETRY_SEC before trying Redis again.
_REDIS_RETRY_SEC = 60
_redis_client = None
_redis_down_until = 0.0


def _redis():
    """Shared Redis client, or None under pytest or while the breaker is open."""
    global _redis_client, _redis_down_until
    if os.getenv("NIVESH_TESTING") == "1" or time.time() < _redis_down_until:
        return None
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                socket_connect_timeout=0.2, socket_timeout=0.2,
            )
        except Exception as e:
            logger.warning("rate limiter: Redis unavailable, using process memory: %s", e)
            _redis_down_until = time.time() + _REDIS_RETRY_SEC
            return None
    return _redis_client


def _too_many(retry_after: float) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Rate limit exceeded. Try again later.",
        headers={"Retry-After": str(max(1, int(retry_after)))}
    )


def _redis_hit(key: str, window: int, max_reqs: int, now: float) -> bool:
    """Count one request in Redis (fixed window). False when Redis is unusable."""
    global _redis_down_until
    r = _redis()
    if r is None:
        return False
    slot = int(now // window)
    rkey = f"rl:{key}:{slot}"
    try:
        pipe = r.pipeline()
        pipe.incr(rkey)
        pipe.expire(rkey, window)
        count = int(pipe.execute()[0])
    except Exception as e:  # redis.RedisError / OSError: fall back to memory
        logger.warning("rate limiter: Redis error, using process memory: %s", e)
        _redis_down_until = now + _REDIS_RETRY_SEC
        return False
    if count > max_reqs:
        raise _too_many((slot + 1) * window - now)
    return True


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
    POST /register 10/hour, the named buckets above; any other path 120/minute.
    Counts in Redis (shared by all workers) when reachable, else in process memory.
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

    if _redis_hit(f"{client_id}|{bucket}", window, max_reqs, now):
        return True

    with _rate_limit_lock:
        if now - _last_sweep >= _SWEEP_EVERY_SEC:
            _sweep(now)
            _last_sweep = now

        dq = _rate_limit_store[client_id][bucket]

        while dq and now - dq[0] > window:
            dq.popleft()

        if len(dq) >= max_reqs:
            raise _too_many(window - (now - dq[0]))

        dq.append(now)
        return True
