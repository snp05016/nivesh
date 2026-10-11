"""
Health probes, the only place they are defined (REL-18).

- /ping (main.py), /api/v1/ping, /health/live: process liveness, no dependencies.
- /health, /health/ready: readiness, DB `SELECT 1`; 503 with no error text when down.
- /healthz: admin-only dependency/config report; no third-party (yfinance) calls.
"""
import importlib.util
import os
import time

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.config_guard import apns_configured, jwt_secret_problem
from core.logging_config import get_logger
from core.security import require_admin
from database import get_session

router = APIRouter(tags=["Health"])
logger = get_logger("health")


@router.get("/api/v1/ping")
def ping():
    """Lightweight liveness check — no dependency checks."""
    return {"status": "ok"}


@router.get("/health/live")
def liveness():
    """Process liveness only: 200 while the server answers requests."""
    return {"status": "alive"}


def _db_ok() -> bool:
    try:
        with get_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Readiness DB check failed")
        return False


@router.get("/health")
@router.get("/health/ready")
def readiness():
    """Readiness: 200 when the database answers, else 503 (no error text)."""
    if _db_ok():
        return {"status": "ok"}
    return JSONResponse({"status": "unavailable"}, status_code=503)


def _ml_engine_ok() -> bool:
    url = (os.getenv("ML_ENGINE_URL") or "http://localhost:8001").rstrip("/")
    try:
        return httpx.get(f"{url}/health", timeout=1.0).status_code == 200
    except Exception:
        return False


def _redis_ok() -> bool:
    try:
        import redis as _redis
        _redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), socket_timeout=1).ping()
        return True
    except Exception:
        return False


@router.get("/healthz")
def healthz(_admin: int = Depends(require_admin)):
    """Admin dependency/config report. 503 only when the DB is down; other gaps are 'degraded'."""
    from services.harvest_worker import _scheduler

    db_ok = _db_ok()
    config = {
        "deepseek_key_set": bool(os.getenv("DEEPSEEK_API_KEY")),
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "jwt_secret_set": jwt_secret_problem(os.getenv("JWT_SECRET")) is None,
        "apns_configured": apns_configured() and os.path.isfile(os.getenv("APNS_AUTH_KEY_PATH", "")),
        "h2_installed": importlib.util.find_spec("h2") is not None,
    }
    checks = {
        "scheduler": bool(_scheduler and _scheduler.running),
        "ml_engine": _ml_engine_ok(),
        "redis": _redis_ok(),
        **config,
    }
    payload = {
        "status": "healthy" if db_ok else "unavailable",
        "db": "ok" if db_ok else "error",
        "config": config,
        "scheduler": {"running": checks["scheduler"]},
        "ml_engine": "ok" if checks["ml_engine"] else "unreachable",
        "redis": "ok" if checks["redis"] else "unavailable",
        "degraded": sorted(name for name, ok in checks.items() if not ok),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return JSONResponse(content=payload, status_code=200 if db_ok else 503)
