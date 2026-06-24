"""
Task 56: /healthz system health check endpoint.
Checks DB, yfinance, Anthropic API key, and Redis availability.
"""
import os
import time

from fastapi import APIRouter
from core.logging_config import get_logger

router = APIRouter(tags=["Health"])
logger = get_logger("health")


@router.get("/api/v1/ping")
def ping():
    """Lightweight liveness check — no dependency checks."""
    return {"status": "ok"}


@router.get("/healthz")
def healthz():
    """
    System health check. Returns status of each component.
    200 = all critical components healthy.
    503 = one or more critical components down.
    """
    results: dict = {}
    overall_ok = True

    # 1. Database connectivity
    try:
        from database import get_session
        with get_session() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
        results["db"] = {"status": "ok"}
    except Exception as e:
        results["db"] = {"status": "error", "detail": str(e)[:120]}
        overall_ok = False

    # 2. yfinance lightweight ping
    try:
        import yfinance as yf
        fi = yf.Ticker("RELIANCE.NS").fast_info
        price = getattr(fi, "last_price", None)
        results["yfinance"] = {"status": "ok", "last_price": price}
    except Exception as e:
        results["yfinance"] = {"status": "degraded", "detail": str(e)[:120]}
        # Not critical — don't fail overall

    # 3. Anthropic API key present
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    results["anthropic"] = {
        "status": "ok" if anthropic_key else "missing_key",
        "key_set": bool(anthropic_key),
    }
    if not anthropic_key:
        overall_ok = False

    # 4. Redis (optional)
    try:
        import redis as _redis
        r = _redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), socket_timeout=2)
        r.ping()
        results["redis"] = {"status": "ok"}
    except Exception as e:
        results["redis"] = {"status": "unavailable", "detail": str(e)[:80]}
        # Redis is optional — not a critical failure

    status_code = 200 if overall_ok else 503
    payload = {
        "status": "healthy" if overall_ok else "degraded",
        "components": results,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    from fastapi.responses import JSONResponse
    return JSONResponse(content=payload, status_code=status_code)
