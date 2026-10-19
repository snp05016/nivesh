import logging
import os
from contextlib import asynccontextmanager

# tradingagents-core installed via: pip install -e ./tradingagents-core

# ---------------------------------------------------------------------------
# Load environment before any other imports
# ---------------------------------------------------------------------------
from core.env import load_backend_env
load_backend_env()  # no-op under pytest (NIVESH_TESTING=1)

# Refuse to boot production with a forgeable JWT secret or wildcard CORS (REL-26).
from core.config_guard import docs_enabled, validate_startup_config
validate_startup_config()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from core import lifecycle
from middleware.request_log import RequestLogMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from services.error_telemetry import CorrelationIDMiddleware

# Single definition lives in helpers.py; routers raise that class, so the
# 503 handler below must bind the same one.
from helpers import DataHarvestingError


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await lifecycle.on_startup()
    yield
    await lifecycle.on_shutdown()


_ENABLE_DOCS = docs_enabled()
app = FastAPI(
    title="Indian Stock Market Analysis API", 
    lifespan=_lifespan,
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
    openapi_url="/openapi.json" if _ENABLE_DOCS else None
)

# ---------------------------------------------------------------------------
# CORS — env-configurable for production
# ---------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

# Fixes #171: Default ALLOWED_ORIGINS is empty — restrictive by default.
# localhost:3000 should only be added in dev via env var.
_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")
_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]
# A wildcard is never combined with credentials (production refuses '*' outright).
_wildcard = "*" in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _wildcard else _origins,
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global OPTIONS handler — returns 200 for all preflight requests.
# Kept on purpose: CORSMiddleware answers real preflights before routing, iOS never sends OPTIONS,
# and tests/test_ios_endpoints.py asserts 200/204 for OPTIONS on many paths.
@app.options("/{rest_of_path:path}")
async def global_options_handler(rest_of_path: str):
    return Response(status_code=200)


app.add_middleware(RequestLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIDMiddleware)
# PERF-23: added last, so outermost: compresses the final body (>= 1 KB) when the
# client sends Accept-Encoding: gzip. Starlette >= 0.46 never compresses
# text/event-stream, so the SSE dashboard stream is unaffected.
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ---------------------------------------------------------------------------
# Financial Error Boundary Handlers
# DataHarvestingError → 503, generic Exception → 500
# ---------------------------------------------------------------------------

logger = logging.getLogger("nivesh.main")

@app.exception_handler(DataHarvestingError)
async def _data_harvesting_error_handler(_req: Request, exc: DataHarvestingError):
    """Exception handler for DataHarvestingError — 503 without echoing upstream error text."""
    logger.warning("DataHarvestingError at %s %s: %s", _req.method, _req.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Market data source temporarily unavailable. Please retry shortly."},
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(_req: Request, exc: HTTPException):
    """Sanitize HTTP exceptions — never expose internal details for 500 errors."""
    headers = getattr(exc, "headers", None)
    # 502/503/504 carry deliberate, client-safe retry messages (callers must not put
    # exception text in them); every other 5xx is masked.
    if exc.status_code >= 500 and exc.status_code not in (502, 503, 504):
        # Routers raise HTTPException(500) inside `except Exception`; log that cause (SILENT-06).
        cause = exc.__cause__ or exc.__context__
        logger.error(
            "HTTP %s at %s %s: %s", exc.status_code, _req.method, _req.url.path, exc.detail,
            exc_info=(type(cause), cause, cause.__traceback__) if cause else None,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Internal server error. The error has been logged."},
            headers=headers,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def _global_exception_handler(_req: Request, exc: Exception):
    """Catch-all handler — log full traceback, return sanitized error to client.
    Prevents internal details (file paths, stack traces, SQL) from leaking to clients.
    """
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception at {_req.method} {_req.url.path}:\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. The error has been logged."},
    )


# ---------------------------------------------------------------------------
# Import and register routers
# ---------------------------------------------------------------------------
from routers import auth, portfolio, market, analysis, portfolio_analytics, morning_brief, advisor_consensus, portfolio_exports, trade_journal, earnings, institutional, ideas, admin_errors, alerts, user, dashboard, notifications, brainstorming, strategy, copilot, anomalies, correlation, nl_screener, stress_test, sector_rotation, earnings_surprise, options_strategy, predictions, fundamentals, backtests, ml_signal, preferences, notifications_inbox, search, ipo, mutual_funds, forum, finance, compliance, subscription, kyc, fixed_deposits, account
from routers import harvester as harvester_router
from routers.health import router as health_router  # Task 56
from routers import youtube_summary as youtube_summary_router
from routers import client_telemetry
from routers import features as features_router

app.include_router(health_router)  # every health probe (REL-18)
app.include_router(auth.router)
app.include_router(correlation.router)
# Domain routers split out of portfolio.py / market.py (ARCH-14). portfolio_analytics must stay
# BEFORE portfolio: GET /portfolio/benchmark and /portfolio/signal-warnings would otherwise be
# captured by GET /portfolio/{user_id}.
app.include_router(portfolio_analytics.router)
app.include_router(portfolio.router)
app.include_router(morning_brief.router)
app.include_router(advisor_consensus.router)
app.include_router(portfolio_exports.router)
app.include_router(trade_journal.router)
app.include_router(market.router)
app.include_router(earnings.router)
app.include_router(institutional.router)
app.include_router(ideas.router)
app.include_router(admin_errors.router)
app.include_router(analysis.router)
app.include_router(alerts.router)
app.include_router(user.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(harvester_router.router)
app.include_router(brainstorming.router)
app.include_router(strategy.router)
app.include_router(strategy.router_legacy)
app.include_router(copilot.router)
app.include_router(anomalies.router)
app.include_router(nl_screener.router)
app.include_router(stress_test.router)
app.include_router(sector_rotation.router, prefix="/api/v1")
app.include_router(earnings_surprise.router)
app.include_router(options_strategy.router)
app.include_router(predictions.router)
app.include_router(fundamentals.router)
app.include_router(fundamentals.router_v1)
app.include_router(backtests.router, prefix="/api/v1/backtests")
app.include_router(ml_signal.router)  # FAKE-04: the mock stock_financials router is gone
app.include_router(preferences.router)
app.include_router(subscription.router)
app.include_router(notifications_inbox.router)
app.include_router(youtube_summary_router.router)
app.include_router(search.router)
app.include_router(client_telemetry.router)
app.include_router(features_router.router)  # GET /api/v1/features (server-side flags)
# ARCH-17: money-control routers live under /api/v1/<name>. The old /api/<name>
# paths stay as deprecated aliases, hidden from OpenAPI, for the shipped iOS app;
# drop them in the release that moves the app to /api/v1.
for _router, _name in (
    (ipo.router, "ipo"),
    (mutual_funds.router, "mutual-funds"),
    (forum.router, "forum"),
    (finance.router, "finance"),
    (kyc.router, "kyc"),
    (account.router, "me"),
    (fixed_deposits.router, "fixed-deposits"),
):
    app.include_router(_router, prefix=f"/api/v1/{_name}")
    app.include_router(_router, prefix=f"/api/{_name}", include_in_schema=False, deprecated=True)
app.include_router(compliance.router)
# Portfolio chart PNGs are served only through the owner-checked route
# GET /api/v1/portfolio/charts/{user_id}/image/{filename} (routers/portfolio_analytics.py).
# Never mount backend/charts publicly.

# ---------------------------------------------------------------------------
# Admin Harvest Endpoints & Scheduler — imported from harvest_worker (Phase 3)
# ---------------------------------------------------------------------------
from services.harvest_worker import router as harvest_router

app.include_router(harvest_router)


# Admin dashboard page, assets and feeds (routers/admin_dashboard.py).
from routers import admin_dashboard

app.mount("/admin-assets", StaticFiles(directory=admin_dashboard.ADMIN_DIR), name="admin-assets")
app.include_router(admin_dashboard.router)
