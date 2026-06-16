"""
Rate limiter with sliding-window counters for FastAPI endpoints.
Extracted from helpers.py to keep core infrastructure separate.
"""
from collections import defaultdict, deque
import threading
import time
from fastapi import HTTPException

# nested dict: store[client_id][endpoint] = deque()
_rate_limit_store: dict[str, dict[str, deque[float]]] = defaultdict(lambda: defaultdict(deque))
_rate_limit_lock = threading.Lock()

_RATE_LIMITS = {
    "/analyze": {"window": 3600, "max_requests": 10},
    "/market/quick-info": {"window": 60, "max_requests": 60},
    "/auth/login": {"window": 60, "max_requests": 5},
    "default": {"window": 60, "max_requests": 120}
}

def _check_rate_limit(client_id: str, endpoint: str = "default") -> bool:
    """
    Checks the sliding window rate limit for the given client_id and endpoint.
    Limits: /analyze 10/hour, /market/quick-info 60/minute, /auth/login 5/minute.
    Raises HTTPException 429 with Retry-After header if exceeded.
    Returns True if allowed.
    """
    now = time.time()
    
    matched_limit = _RATE_LIMITS["default"]
    for prefix, limits in _RATE_LIMITS.items():
        if prefix != "default" and endpoint.startswith(prefix):
            matched_limit = limits
            break

    window = matched_limit["window"]
    max_reqs = matched_limit["max_requests"]
    
    with _rate_limit_lock:
        dq = _rate_limit_store[client_id][endpoint]
        
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
