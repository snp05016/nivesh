import os
import sys
import json
import hashlib
import time
import time as _time
import io
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# tradingagents-core installed via: pip install -e ./tradingagents-core

# ---------------------------------------------------------------------------
# Load environment before any other imports
# ---------------------------------------------------------------------------
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Disk cache — L2 persistent layer (L1 = in-memory _quick_info_cache)
from services.disk_cache import get as _dcache_get, set as _dcache_set, stats as _dcache_stats
from services.ai_engine_monitor import build_ai_engine_monitor
from services.error_telemetry import CorrelationIDMiddleware

import multiprocessing
import asyncio
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uuid
from fastapi.responses import StreamingResponse, HTMLResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, validator
from typing import Optional as _Optional, List as _List
from pydantic import BaseModel as _BaseModel
import yfinance as yf

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font as XLFont, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

import importlib.util as _importlib_util
FPDF2_AVAILABLE = _importlib_util.find_spec("fpdf2") is not None
if FPDF2_AVAILABLE:
    try:
        from fpdf import FPDF
    except Exception as _e:
        FPDF2_AVAILABLE = False

from database import init_db, get_session, save_analysis, get_recent_analyses, get_user_by_credentials, Portfolio, User, AnalysisHistory, SignalEvent, get_analysis_for_date, get_all_ticker_history, PriceTarget, TradeJournal, DeviceToken, AdvisorInsight, NewsArticle, YouTubeVideo, PortfolioValuationHistory, PKScreenerSignal, MacroEvent, NetWorthLedger, create_access_token, verify_access_token, is_admin
from helpers import format_indian_currency, _ban_western_scale  # GH #123 — canonical home in helpers.py


# ---------------------------------------------------------------------------
# Constants: Prompt Caching Blocks
# ---------------------------------------------------------------------------


import logging
import threading

# ---------------------------------------------------------------------------
# Dashboard state — single source of truth is core.dashboard_state (written by
# helpers/routers/services). Importing the same objects here keeps the admin
# dashboard and the request-log middleware on that one copy (ARCH-05).
# /dashboard-data reads through the module (_ds) so it always sees live values
# (and tests can monkeypatch them).
# ---------------------------------------------------------------------------
import core.dashboard_state as _ds
from core.dashboard_state import (
    _dash_lock, _active_analyses, _completed_analyses, _request_log,
    _dash_logs as _harvest_logs, _token_stats, _harvest_status,
    TOKEN_LOG_PATH, _dash_log_request,
)

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter
# ---------------------------------------------------------------------------
# The _check_rate_limit function is now imported from helpers.py

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# JWT Auth Dependencies — imported from core.security (Phase 2 refactor)
# ---------------------------------------------------------------------------
from fastapi import Header, Depends
from core.security import get_current_user_id, require_auth, require_admin

# ---------------------------------------------------------------------------
# Custom exception classes — Financial Error Boundaries
# ---------------------------------------------------------------------------

# Single definition lives in helpers.py; routers raise that class, so the
# 503 handler below must bind the same one.
from helpers import DataHarvestingError, _quick_info_cache


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await _on_startup()
    yield
    await _on_shutdown()


_ENABLE_DOCS = os.getenv("ENABLE_API_DOCS", "true").lower() == "true"
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global OPTIONS handler — returns 200 for all preflight requests.
# Kept on purpose: CORSMiddleware answers real preflights before routing, iOS never sends OPTIONS,
# and tests/test_ios_endpoints.py asserts 200/204 for OPTIONS on many paths.
@app.options("/{rest_of_path:path}")
async def global_options_handler(rest_of_path: str):
    return Response(status_code=200)


class _RequestLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log standard HTTP requests to the dashboard state.
    """
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        dur_ms = (time.time() - start) * 1000
        if request.url.path not in ("/", "/dashboard-data", "/ping"):
            _dash_log_request(
                method=request.method,
                path=request.url.path,
                params=dict(request.query_params),
                status=response.status_code,
                duration_ms=dur_ms,
            )
        return response

app.add_middleware(_RequestLogMiddleware)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject security headers and enforce basic rate limits.
    """
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        from helpers import _check_rate_limit
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse
        
        try:
            _check_rate_limit(client_ip, endpoint)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code, 
                content={"detail": e.detail},
                headers=e.headers
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # setdefault: the admin dashboard route sets its own, wider policy.
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Fixes #109: Prevent CDN/browser caching of authenticated API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(CorrelationIDMiddleware)

# ---------------------------------------------------------------------------
# Financial Error Boundary Handlers
# DataHarvestingError → 503, generic Exception → 500
# ---------------------------------------------------------------------------
from fastapi import Request as _FRequest
from fastapi.responses import JSONResponse as _JSONResponse

logger = logging.getLogger("nivesh.main")

@app.exception_handler(DataHarvestingError)
async def _data_harvesting_error_handler(_req: _FRequest, exc: DataHarvestingError):
    """Exception handler for DataHarvestingError — 503 without echoing upstream error text."""
    logger.warning("DataHarvestingError at %s %s: %s", _req.method, _req.url.path, exc)
    return _JSONResponse(
        status_code=503,
        content={"detail": "Market data source temporarily unavailable. Please retry shortly."},
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(_req: _FRequest, exc: HTTPException):
    """Sanitize HTTP exceptions — never expose internal details for 500 errors."""
    headers = getattr(exc, "headers", None)
    # 502/503/504 carry deliberate, client-safe retry messages (callers must not put
    # exception text in them); every other 5xx is masked.
    if exc.status_code >= 500 and exc.status_code not in (502, 503, 504):
        logger.error(f"HTTP {exc.status_code} at {_req.method} {_req.url.path}: {exc.detail}")
        return _JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Internal server error. The error has been logged."},
            headers=headers,
        )
    return _JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def _global_exception_handler(_req: _FRequest, exc: Exception):
    """Catch-all handler — log full traceback, return sanitized error to client.
    Prevents internal details (file paths, stack traces, SQL) from leaking to clients.
    """
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception at {_req.method} {_req.url.path}:\n{tb}")
    return _JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. The error has been logged."},
    )


# ---------------------------------------------------------------------------
# Import and register routers
# ---------------------------------------------------------------------------
from routers import auth, portfolio, market, analysis, alerts, user, dashboard, notifications, brainstorming, strategy, copilot, anomalies, correlation, nl_screener, stress_test, sector_rotation, earnings_surprise, options_strategy, predictions, fundamentals, backtests, stock_financials, preferences, notifications_inbox, search, stocks, compare, ipo, mutual_funds, forum, finance, compliance, subscription, kyc, fixed_deposits, account
from routers import harvester as harvester_router
from routers.health import router as health_router  # Task 56
from routers import youtube_summary as youtube_summary_router

app.include_router(health_router)  # /healthz
app.include_router(auth.router)
app.include_router(correlation.router)
app.include_router(portfolio.router)
app.include_router(market.router)
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
app.include_router(stock_financials.router)
app.include_router(preferences.router)
app.include_router(subscription.router)
app.include_router(notifications_inbox.router)
app.include_router(youtube_summary_router.router)
app.include_router(search.router)
app.include_router(stocks.router)
app.include_router(compare.router)
app.include_router(ipo.router)
app.include_router(mutual_funds.router)
app.include_router(forum.router)
app.include_router(finance.router)
app.include_router(kyc.router)
app.include_router(compliance.router)
app.include_router(account.router)
app.include_router(fixed_deposits.router)
# Portfolio chart PNGs are served only through the owner-checked route
# GET /api/v1/portfolio/charts/{user_id}/image/{filename} (routers/portfolio.py).
# Never mount backend/charts publicly.

# ---------------------------------------------------------------------------
# Admin Harvest Endpoints & Scheduler — imported from harvest_worker (Phase 3)
# ---------------------------------------------------------------------------
from services.harvest_worker import router as harvest_router, start_scheduler, stop_scheduler

app.include_router(harvest_router)


def _seed_catalogs():
    """Seed catalogs at startup, never from GET handlers (FAKE-06 / GH-696).

    Forum boards are structural categories and always seeded. The mutual-fund,
    IPO, loan-offer and FD-scheme catalogs hold illustrative figures, so they
    are seeded only when DEMO_MODE is set (dev/demo servers).
    """
    from config.settings import DEMO_MODE
    from services import fixed_deposit_service, forum_service, ipo_service
    from services import loan_marketplace_service, mutual_fund_service
    seeders = [forum_service.seed_mock_boards_if_empty]
    if DEMO_MODE:
        seeders += [
            mutual_fund_service.seed_mock_funds_if_empty,
            ipo_service.seed_mock_ipos_if_empty,
            loan_marketplace_service.seed_mock_loan_offers_if_empty,
            fixed_deposit_service.seed_mock_fd_schemes_if_empty,
        ]
    for seed in seeders:
        try:
            seed()
        except Exception as e:
            logging.warning("[startup] %s failed: %s", seed.__name__, e)


async def _on_startup():
    """
    Execute application startup routines.

    Initializes structured logging, the scheduler, database tables, and kicks off
    background syncs. Also sweeps any stale or abandoned jobs left in the database.
    """
    # Wire up structured JSON logging (fixes #83)
    from core.logging_config import configure_logging
    configure_logging()
    # Init DB and seed on startup (fixes #87 — moved from module level)
    init_db()
    start_scheduler()
    # v2 engine crash recovery: any analysis job left RUNNING/QUEUED by a previous
    # process (deploy/crash) has a dead worker → mark it FAILED so the app shows an
    # honest error and the user can re-run.
    try:
        import database
        swept = database.sweep_stale_jobs(90)
        if swept:
            logging.info("[startup] swept %d stale analysis jobs -> FAILED", swept)
    except Exception as e:
        logging.warning("[startup] analysis job sweep failed: %s", e)
    try:
        from services.harvester_db import init_harvester_db
        from services.harvest_worker import _seed_harvester_sources
        init_harvester_db()
        _seed_harvester_sources()
    except Exception as e:
        logging.warning("Harvester DB init failed: %s", e)
    _seed_catalogs()
    from routers.alerts import _price_alert_poller
    import asyncio
    asyncio.create_task(_price_alert_poller())

    # FinBERT loading is deferred to first request (lazy). Pre-warming at startup
    # causes memory spikes during model load, cascading worker death with uvicorn
    # --workers > 1. The 3-5s cost on first sentiment request is acceptable.

    # Backfill UserPreferences for existing users without one
    def _backfill_preferences():
        try:
            from database import get_session, User
            from models.db_models import UserPreference
            with get_session() as s:
                existing = s.query(UserPreference.user_id).distinct().all()
                existing_ids = {r[0] for r in existing}
                users = s.query(User.id).filter(~User.id.in_(existing_ids)).all() if existing_ids else s.query(User.id).all()
                for (uid,) in users:
                    s.add(UserPreference(user_id=uid))
                s.commit()
                if users:
                    logging.info(f"Backfilled preferences for {len(users)} users")
        except Exception as e:
            logging.warning(f"Preference backfill skipped: {e}")
    threading.Thread(target=_backfill_preferences, daemon=True).start()

    # RAG ingestion is incremental and runs only in the leader scheduler
    # (harvest_worker job 'rag_ingest'), never per worker at startup.

    # ENABLE_SCHEDULER block removed (fixes #85): start_scheduler() from
    # harvest_worker (called above) already registers all cron jobs including
    # harvest_youtube_metadata, harvest_news, and snapshot_all_users.
    # The duplicate AsyncIOScheduler was causing double job execution.


async def _on_shutdown():
    stop_scheduler()
    from services.job_manager import shutdown_all
    shutdown_all()


@app.get("/ping")
def ping():
    """Zero-dependency liveness probe — no DB, no yfinance."""
    """Simple ping endpoint for load balancers."""
    return {"pong": True}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return an empty response for favicon requests to prevent 404s."""
    from fastapi.responses import Response
    return Response(content=b"", media_type="image/x-icon")


# init_db() moved into _on_startup() handler (fixes #87)



# Ticker lookups relocated to services/nse_data_provider and helpers.py (Phase 4)




# ---------------------------------------------------------------------------
# Request models — imported from schemas/ namespace (Phase 1 refactor)
# ---------------------------------------------------------------------------

from schemas import (
    LoginRequest, AnalyzeRequest,
    WatchlistAddRequest, WatchlistRemoveRequest,
    PortfolioAddRequest, PortfolioRemoveRequest,
    PortfolioUpdateRequest, PortfolioNoteRequest,
    AlertAddRequest, AlertRemoveRequest,
    BatchAnalyzeRequest,
    TradeJournalAddRequest, TradeJournalUpdateRequest,
)


# ---------------------------------------------------------------------------
# Liveness probe — Section 16
# Zero-latency, dependency-free. Used by Docker HEALTHCHECK and k8s liveness.
# Confirms DB is reachable; does NOT call yfinance or any external service.
# ---------------------------------------------------------------------------

@app.get("/health/live")
async def liveness_probe():
    """
    Shallow liveness probe endpoint.

    Always returns 200 OK as long as the HTTP server is responsive.
    """
    return {"status": "alive", "time": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nivesh Admin Dashboard</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0a0a0a;color:#c9d1d9;font-family:'SF Mono','Cascadia Code','Fira Code',monospace;font-size:13px;line-height:1.5}
    ::-webkit-scrollbar{width:6px;height:6px}
    ::-webkit-scrollbar-track{background:#0d1117}
    ::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}
    header{background:#111111;border-bottom:2px solid #c9a84c33;padding:14px 28px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
    .brand{display:flex;align-items:center;gap:12px}
    .brand-icon{font-size:22px}
    .brand-text h1{font-size:17px;color:#c9a84c;font-weight:700;letter-spacing:.6px}
    .brand-text .sub{font-size:11px;color:#6e7681;margin-top:1px}
    .hdr-right{display:flex;align-items:center;gap:20px}
    .uptime-pill{background:#1a1a1a;border:1px solid #30363d;border-radius:20px;padding:5px 14px;font-size:11px;color:#8b949e}
    .live-pill{display:flex;align-items:center;gap:7px;background:#0f2110;border:1px solid #238636;border-radius:20px;padding:5px 14px;font-size:11px;color:#3fb950}
    .dot{width:7px;height:7px;border-radius:50%;background:#3fb950;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
    #lu{color:#484f58;font-size:11px}
    /* Nav tabs */
    .main-nav{background:#0d0d0d;border-bottom:1px solid #21262d;padding:0 28px;display:flex;gap:4px;overflow-x:auto}
    .nav-tab{background:none;border:none;color:#6e7681;padding:10px 16px;cursor:pointer;font-family:inherit;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;border-bottom:2px solid transparent;transition:.15s}
    .nav-tab:hover{color:#c9d1d9}
    .nav-tab.active{color:#c9a84c;border-bottom-color:#c9a84c}
    .btn-mode{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:6px 14px;color:#8b949e;cursor:pointer;font-family:inherit;font-size:11px;transition:.15s}
    .btn-mode:hover{color:#c9d1d9;border-color:#c9a84c}
    .btn-mode.active{background:#c9a84c15;color:#c9a84c;border-color:#c9a84c}
    .phase-bar{height:4px;border-radius:2px;background:#21262d;margin-top:4px;overflow:hidden}
    .phase-bar-fill{height:100%;border-radius:2px;transition:width .3s}
    .phase-bar-fill.running{background:#c9a84c}
    .phase-bar-fill.done{background:#3fb950}
    .phase-bar-fill.failed{background:#f85149}
    .timeline-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:11px}
    .timeline-dot{width:8px;height:8px;border-radius:50%;background:#30363d;flex-shrink:0}
    .timeline-dot.active{background:#c9a84c;box-shadow:0 0 6px #c9a84c60}
    .timeline-dot.done{background:#3fb950}
    .timeline-dot.failed{background:#f85149}
    .page{display:none;padding:24px 28px;max-width:1600px;margin:0 auto}
    .page.active{display:block}
    /* Layout */
    .section-label{font-size:10px;font-weight:700;color:#c9a84c;text-transform:uppercase;letter-spacing:2px;margin-bottom:10px;display:flex;align-items:center;gap:8px}
    .section-label::after{content:'';flex:1;height:1px;background:#c9a84c22}
    .row2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
    .row4{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
    /* Cards */
    .card{background:#111111;border:1px solid #21262d;border-radius:10px;overflow:hidden;margin-bottom:20px}
    .card-header{padding:11px 16px;border-bottom:1px solid #21262d;display:flex;justify-content:space-between;align-items:center;background:#0d0d0d}
    .card-title{font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:1.2px}
    .card-body{padding:16px}
    .empty{color:#484f58;font-style:italic;text-align:center;padding:20px;font-size:12px}
    /* Stats */
    .stat-grid{display:grid;gap:10px}
    .stat-grid-4{grid-template-columns:repeat(4,1fr)}
    .stat-grid-2{grid-template-columns:1fr 1fr}
    .stat-grid-3{grid-template-columns:repeat(3,1fr)}
    .stat-tile{border-radius:8px;padding:14px 12px;text-align:center}
    .stat-tile .val{font-size:22px;font-weight:700;line-height:1}
    .stat-tile .lbl{font-size:10px;color:#8b949e;margin-top:5px;text-transform:uppercase;letter-spacing:.6px}
    .tile-dark{background:#0d1117;border:1px solid #21262d}
    .val-gold{color:#c9a84c} .val-red{color:#f85149} .val-green{color:#3fb950} .val-blue{color:#58a6ff} .val-purple{color:#bc8cff} .val-dim{color:#8b949e} .val-amber{color:#d29922}
    /* AI model cards */
    .ai-model-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .model-card{border-radius:10px;overflow:hidden}
    .model-card.claude{background:#0a0e1f;border:1px solid #1d3a7a}
    .model-card.deepseek{background:#120a1f;border:1px solid #4a1d7a}
    .model-card-header{padding:13px 18px;display:flex;align-items:center;gap:10px;border-bottom:1px solid}
    .model-card.claude .model-card-header{border-color:#1d3a7a;background:#0d1229}
    .model-card.deepseek .model-card-header{border-color:#4a1d7a;background:#180d29}
    .model-icon{font-size:20px}
    .model-name{font-size:13px;font-weight:700}
    .model-card.claude .model-name{color:#58a6ff}
    .model-card.deepseek .model-name{color:#bc8cff}
    .model-sub{font-size:10px;color:#6e7681;margin-top:1px}
    .model-body{padding:16px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
    .model-stat{background:#0a0a0a;border-radius:6px;padding:12px 8px;text-align:center}
    .model-stat .mv{font-size:18px;font-weight:700;line-height:1}
    .model-stat .ml{font-size:9px;color:#6e7681;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
    .claude-val{color:#58a6ff} .deepseek-val{color:#bc8cff} .cost-val{color:#c9a84c}
    .model-footer{padding:10px 16px;border-top:1px solid;font-size:11px;color:#6e7681;display:flex;justify-content:space-between}
    .model-card.claude .model-footer{border-color:#1d3a7a}
    .model-card.deepseek .model-footer{border-color:#4a1d7a}
    /* Feature cards */
    .feature-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
    .feature-card{border-radius:8px;overflow:hidden;border:1px solid}
    .feature-card.clean{border-color:#238636;background:#0f2110}
    .feature-card.has-errors{border-color:#da3633;background:#200d0d}
    .feature-header{padding:9px 13px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid}
    .feature-card.clean .feature-header{border-color:#238636;background:#112213}
    .feature-card.has-errors .feature-header{border-color:#da3633;background:#2d0e0e}
    .feature-name{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px}
    .feature-card.clean .feature-name{color:#3fb950}
    .feature-card.has-errors .feature-name{color:#f85149}
    .feat-status-dot{width:7px;height:7px;border-radius:50%}
    .feature-card.clean .feat-status-dot{background:#3fb950}
    .feature-card.has-errors .feat-status-dot{background:#f85149;animation:pulse 1.5s infinite}
    .feature-body{padding:10px}
    .feat-clean-msg{font-size:11px;color:#3fb950;text-align:center;padding:10px 0}
    .feat-err-item{background:#0a0a0a;border-radius:4px;padding:6px 8px;margin-bottom:6px;border-left:2px solid #da3633}
    .feat-err-item:last-child{margin-bottom:0}
    .feat-err-path{font-size:10px;color:#f85149;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .feat-err-meta{font-size:10px;color:#484f58;margin-top:2px}
    /* Analysis items */
    .analysis-item{background:#0d1117;border:1px solid #21262d;border-radius:7px;padding:12px;margin-bottom:10px}
    .analysis-item:last-child{margin-bottom:0}
    .analysis-item.active{border-color:#1d3a7a;background:#0a0e1f}
    .a-ticker{font-size:15px;font-weight:700;color:#f0f6fc}
    .a-meta{color:#6e7681;font-size:11px;margin-top:3px}
    .a-stage{margin-top:8px;color:#58a6ff;font-size:12px}
    .s-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#58a6ff;margin-right:6px;animation:pulse 1s infinite}
    /* Tables */
    table{width:100%;border-collapse:collapse}
    th{text-align:left;padding:8px 12px;font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid #21262d;font-weight:700}
    td{padding:7px 12px;border-bottom:1px solid #161b22;font-size:12px;vertical-align:middle}
    tr:last-child td{border-bottom:none}
    tr:hover td{background:#0d1117}
    .ts{color:#6e7681;font-size:11px}
    .path{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    /* Badges */
    .badge{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600}
    .bull{background:rgba(63,185,80,.15);color:#3fb950}
    .bear{background:rgba(248,81,73,.15);color:#f85149}
    .hold{background:rgba(210,153,34,.15);color:#d29922}
    .cache{background:rgba(88,166,255,.15);color:#58a6ff}
    .smart{background:rgba(188,140,255,.15);color:#bc8cff}
    .full{background:rgba(63,185,80,.12);color:#3fb950}
    .err{background:rgba(248,81,73,.15);color:#f85149}
    .ok{background:rgba(63,185,80,.1);color:#3fb950}
    .mGET{background:rgba(88,166,255,.08);color:#58a6ff}
    .mPOST{background:rgba(63,185,80,.08);color:#3fb950}
    .mDELETE{background:rgba(248,81,73,.08);color:#f85149}
    .mPUT{background:rgba(210,153,34,.08);color:#d29922}
    .positive{background:rgba(63,185,80,.15);color:#3fb950}
    .negative{background:rgba(248,81,73,.15);color:#f85149}
    .neutral{background:rgba(139,148,158,.15);color:#8b949e}
    /* Archive / expand */
    .archive-details{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:12px;margin-top:8px;display:none}
    .json-box{background:#0a0a0a;padding:10px;border-radius:4px;overflow:auto;max-height:280px;font-size:11px;color:#8b949e;border:1px solid #21262d;white-space:pre-wrap;margin-top:8px}
    .btn-view{background:#1f4b2e;color:#3fb950;border:1px solid #238636;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:10px;font-family:inherit}
    .btn-view:hover{background:#238636;color:#fff}
    .btn-blue{background:#0d2a4a;color:#58a6ff;border:1px solid #1d3a7a;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:10px;font-family:inherit}
    .btn-blue:hover{background:#1d3a7a;color:#fff}
    .tab-btn{background:#161b22;color:#8b949e;border:1px solid #30363d;padding:4px 10px;border-radius:4px 4px 0 0;cursor:pointer;font-size:10px;margin-right:2px;font-family:inherit}
    .tab-btn.active{background:#21262d;color:#f0f6fc;border-bottom:none}
    .divider{height:1px;background:linear-gradient(90deg,transparent,#c9a84c44,transparent);margin:4px 0}
    /* User selector */
    .user-selector-bar{background:#111;border:1px solid #21262d;border-radius:10px;padding:16px;margin-bottom:20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
    .user-selector-bar label{font-size:11px;color:#8b949e;font-weight:700;text-transform:uppercase;letter-spacing:.8px}
    select.user-select{background:#0d1117;color:#f0f6fc;border:1px solid #30363d;border-radius:6px;padding:6px 12px;font-family:inherit;font-size:12px;cursor:pointer;min-width:220px}
    select.user-select:focus{outline:none;border-color:#c9a84c}
    .user-stat-row{display:flex;gap:20px;flex-wrap:wrap;margin-top:4px}
    .user-stat-chip{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:4px 10px;font-size:11px}
    .user-stat-chip .chip-val{color:#c9a84c;font-weight:700}
    /* Analysis report cards */
    .analysis-report{background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:14px;margin-bottom:12px}
    .report-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px}
    .report-ticker{font-size:16px;font-weight:700;color:#f0f6fc}
    .report-company{font-size:11px;color:#6e7681;margin-top:2px}
    .report-meta{text-align:right;font-size:11px;color:#6e7681}
    .report-body{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}
    .report-col h4{font-size:10px;font-weight:700;color:#c9a84c;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
    .report-list{list-style:none;padding:0}
    .report-list li{font-size:11px;color:#8b949e;padding:3px 0;border-bottom:1px solid #161b22;padding-left:10px;position:relative}
    .report-list li::before{content:'•';position:absolute;left:0;color:#c9a84c}
    .report-list li:last-child{border-bottom:none}
    .target-prices{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}
    .target-chip{background:#111;border:1px solid #21262d;border-radius:6px;padding:8px;text-align:center}
    .target-chip .tv{font-size:13px;font-weight:700;color:#c9a84c}
    .target-chip .tl{font-size:9px;color:#484f58;text-transform:uppercase;margin-top:2px}
    .key-factors{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}
    .kf-item{background:#111;border:1px solid #21262d;border-radius:4px;padding:6px 8px}
    .kf-label{font-size:9px;color:#484f58;text-transform:uppercase;letter-spacing:.5px}
    .kf-val{font-size:11px;color:#8b949e;margin-top:2px}
    /* Charts */
    .chart-container{position:relative;width:100%;height:220px;padding:10px 0}
    .chart-container-lg{position:relative;width:100%;height:300px;padding:10px 0}
    /* Holdings table badges */
    .pnl-pos{color:#3fb950;font-weight:700}
    .pnl-neg{color:#f85149;font-weight:700}
    /* Journal */
    .journal-entry{background:#0d1117;border:1px solid #21262d;border-radius:7px;padding:12px;margin-bottom:10px}
    .journal-action-buy{border-left:3px solid #3fb950}
    .journal-action-sell{border-left:3px solid #f85149}
    .journal-action-hold{border-left:3px solid #d29922}
    .journal-action-watch{border-left:3px solid #58a6ff}
    /* Alert items */
    .alert-item{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid #161b22}
    .alert-item:last-child{border-bottom:none}
    .alert-triggered{opacity:.5;text-decoration:line-through}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="brand-icon">&#x20B9;</div>
    <div class="brand-text">
      <h1>Nivesh Admin Dashboard</h1>
      <div class="sub" id="uptime">Loading...</div>
    </div>
  </div>
  <div class="hdr-right">
    <button class="btn-view" onclick="refreshAll()">Refresh</button>
    <div class="uptime-pill" id="lu">Connecting...</div>
    <div class="live-pill"><div class="dot"></div>Live &bull; 30s</div>
  </div>
</header>

<nav class="main-nav">
  <button class="nav-tab active" onclick="showPage('overview')">&#x1F4CA; Overview</button>
  <button class="nav-tab" onclick="showPage('users')">&#x1F465; Users</button>
  <button class="nav-tab" onclick="showPage('ai')">&#x1F916; AI Engine</button>
  <button class="nav-tab" onclick="showPage('harvesters')">&#x1F33E; Harvesters</button>
  <button class="nav-tab" onclick="showPage('archive')">&#x1F4DC; Archive</button>
  <button class="nav-tab" onclick="showPage('requests')">&#x1F310; Requests</button>
</nav>

<!-- ═══════════════════════════════════════════════════════════
     PAGE: OVERVIEW
═══════════════════════════════════════════════════════════ -->
<div class="page active" id="page-overview">

  <div class="section-label" style="margin-top:24px">System Overview</div>
  <div class="row4" style="margin-bottom:20px">
    <div class="stat-tile tile-dark"><div class="val val-red" id="db_u">-</div><div class="lbl">Total Users</div></div>
    <div class="stat-tile tile-dark"><div class="val val-green" id="db_h">-</div><div class="lbl">Holdings</div></div>
    <div class="stat-tile tile-dark"><div class="val val-blue" id="db_a">-</div><div class="lbl">Analyses</div></div>
    <div class="stat-tile tile-dark"><div class="val val-gold" id="db_s">-</div><div class="lbl">Signal Events</div></div>
  </div>
  <div class="row4" style="margin-bottom:20px">
    <div class="stat-tile tile-dark"><div class="val val-dim" id="db_tj">-</div><div class="lbl">Journal Entries</div></div>
    <div class="stat-tile tile-dark"><div class="val val-dim" id="db_news">-</div><div class="lbl">News Articles</div></div>
    <div class="stat-tile tile-dark"><div class="val val-dim" id="db_yt">-</div><div class="lbl">YouTube Videos</div></div>
    <div class="stat-tile tile-dark"><div class="val val-dim" id="c_q">-</div><div class="lbl">QuickInfo Cache</div></div>
  </div>

  <div class="section-label">AI Provider Health</div>
  <div class="row3" style="margin-bottom:20px">
    <div class="stat-tile tile-dark"><div class="val" id="h_ant">-</div><div class="lbl">Anthropic</div></div>
    <div class="stat-tile tile-dark"><div class="val" id="h_ds">-</div><div class="lbl">DeepSeek</div></div>
    <div class="stat-tile tile-dark"><div class="val" id="h_goog">-</div><div class="lbl">Google</div></div>
  </div>

  <div class="section-label">Per-Feature Health</div>
  <div class="feature-grid" id="feature-error-grid" style="margin-bottom:20px">
    <div class="empty" style="grid-column:1/-1">Loading...</div>
  </div>

  <div class="section-label">Live Analysis Monitor</div>
  <div class="row2" style="margin-bottom:20px">
    <div class="card">
      <div class="card-header"><span class="card-title">Currently Running</span><span class="ts" id="ac"></span></div>
      <div class="card-body" id="ab"><div class="empty">No active analyses</div></div>
    </div>
    <div class="card">
      <div class="card-header"><span class="card-title">Recently Completed</span><span class="ts" id="anc"></span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Time</th><th>Ticker</th><th>Type</th><th>Signal</th><th>Dur</th><th>Status</th></tr></thead>
        <tbody id="at"><tr><td colspan="6" class="empty">No analyses yet</td></tr></tbody></table>
      </div>
    </div>
  </div>

  <div class="section-label">Harvested Content</div>
  <div class="row2" style="margin-bottom:20px">
    <div class="card">
      <div class="card-header"><span class="card-title">Latest News Articles</span><span class="ts" id="lnc"></span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Time</th><th>Ticker</th><th>Headline</th><th>Sentiment</th></tr></thead>
        <tbody id="lnt"><tr><td colspan="4" class="empty">No news</td></tr></tbody></table>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><span class="card-title">Latest YouTube Videos</span><span class="ts" id="lvc"></span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Time</th><th>Ticker</th><th>Channel</th><th>Title</th></tr></thead>
        <tbody id="lvt"><tr><td colspan="4" class="empty">No videos</td></tr></tbody></table>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════
     PAGE: USERS (per-user deep dive)
═══════════════════════════════════════════════════════════ -->
<div class="page" id="page-users">
  <div style="padding-top:24px">
    <div class="section-label">Per-User Intelligence</div>

    <div class="user-selector-bar">
      <label>Select User</label>
      <select class="user-select" id="user-select" onchange="loadUser(this.value)">
        <option value="">-- select user --</option>
      </select>
      <div class="user-stat-row" id="user-stat-chips"></div>
    </div>

    <!-- User sub-tabs -->
    <div style="display:flex;gap:4px;margin-bottom:16px;border-bottom:1px solid #21262d">
      <button class="tab-btn active" id="utab-portfolio" onclick="showUserTab('portfolio')">&#x1F4BC; Portfolio</button>
      <button class="tab-btn" id="utab-analyses" onclick="showUserTab('analyses')">&#x1F9E0; AI Reports</button>
      <button class="tab-btn" id="utab-valuation" onclick="showUserTab('valuation')">&#x1F4C8; Valuation Chart</button>
      <button class="tab-btn" id="utab-alerts" onclick="showUserTab('alerts')">&#x1F514; Alerts</button>
      <button class="tab-btn" id="utab-journal" onclick="showUserTab('journal')">&#x1F4D3; Trade Journal</button>
      <button class="tab-btn" id="utab-networth" onclick="showUserTab('networth')">&#x1F4B0; Net Worth</button>
    </div>

    <!-- Portfolio tab -->
    <div id="utab-content-portfolio">
      <div class="section-label">Portfolio Holdings</div>
      <div class="row3" style="margin-bottom:16px" id="portfolio-summary-stats">
        <div class="stat-tile tile-dark"><div class="val val-blue" id="p-holdings">-</div><div class="lbl">Holdings</div></div>
        <div class="stat-tile tile-dark"><div class="val val-amber" id="p-invested">-</div><div class="lbl">Total Invested</div></div>
        <div class="stat-tile tile-dark"><div class="val val-dim" id="p-groups">-</div><div class="lbl">Groups</div></div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Holdings Table</span></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>#</th><th>Ticker</th><th>Company</th><th>Shares</th><th>Buy Price (₹)</th><th>Invested (₹)</th><th>Group</th><th>Notes</th><th>Added</th></tr></thead>
          <tbody id="portfolio-table"><tr><td colspan="9" class="empty">Select a user above</td></tr></tbody></table>
        </div>
      </div>
      <div class="row2">
        <div class="card">
          <div class="card-header"><span class="card-title">Allocation by Group</span></div>
          <div class="card-body"><div class="chart-container"><canvas id="chart-allocation"></canvas></div></div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Signal Distribution (Analyses)</span></div>
          <div class="card-body"><div class="chart-container"><canvas id="chart-signals"></canvas></div></div>
        </div>
      </div>
    </div>

    <!-- AI Reports tab -->
    <div id="utab-content-analyses" style="display:none">
      <div class="section-label">AI Analysis Reports</div>
      <div class="row4" style="margin-bottom:16px">
        <div class="stat-tile tile-dark"><div class="val val-blue" id="a-total">-</div><div class="lbl">Total Analyses</div></div>
        <div class="stat-tile tile-dark"><div class="val val-green" id="a-correct">-</div><div class="lbl">Correct Signals</div></div>
        <div class="stat-tile tile-dark"><div class="val val-red" id="a-incorrect">-</div><div class="lbl">Incorrect</div></div>
        <div class="stat-tile tile-dark"><div class="val val-gold" id="a-accuracy">-</div><div class="lbl">Accuracy</div></div>
      </div>
      <div id="analyses-list"><div class="empty">Select a user above</div></div>
    </div>

    <!-- Valuation Chart tab -->
    <div id="utab-content-valuation" style="display:none">
      <div class="section-label">Portfolio Valuation Over Time</div>
      <div class="card">
        <div class="card-header"><span class="card-title">Daily Snapshot — Total Value vs Invested vs Nifty (normalised)</span></div>
        <div class="card-body"><div class="chart-container-lg"><canvas id="chart-valuation"></canvas></div></div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Daily P&L %</span></div>
        <div class="card-body"><div class="chart-container"><canvas id="chart-pnl-pct"></canvas></div></div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Valuation History Table</span></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>Date</th><th>Total Value (₹)</th><th>Invested (₹)</th><th>P&L (₹)</th><th>P&L %</th><th>Nifty Close</th></tr></thead>
          <tbody id="valuation-table"><tr><td colspan="6" class="empty">No data</td></tr></tbody></table>
        </div>
      </div>
    </div>

    <!-- Alerts tab -->
    <div id="utab-content-alerts" style="display:none">
      <div class="section-label">Price Alerts</div>
      <div class="card">
        <div class="card-header"><span class="card-title">Active &amp; Triggered Alerts</span></div>
        <div id="alerts-list"><div class="empty">Select a user above</div></div>
      </div>
    </div>

    <!-- Trade Journal tab -->
    <div id="utab-content-journal" style="display:none">
      <div class="section-label">Trade Journal</div>
      <div id="journal-list"><div class="empty">Select a user above</div></div>
    </div>

    <!-- Net Worth tab -->
    <div id="utab-content-networth" style="display:none">
      <div class="section-label">Net Worth Ledger</div>
      <div class="card">
        <div class="card-header"><span class="card-title">Net Worth Over Time (₹)</span></div>
        <div class="card-body"><div class="chart-container-lg"><canvas id="chart-networth"></canvas></div></div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Daily Ledger</span></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>Date</th><th>Value (₹)</th><th>Day Δ (₹)</th><th>Day Δ %</th><th>Peak (₹)</th><th>Top Gainer</th><th>Top Loser</th></tr></thead>
          <tbody id="networth-table"><tr><td colspan="7" class="empty">No data</td></tr></tbody></table>
        </div>
      </div>
    </div>

  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════
     PAGE: AI ENGINE
═══════════════════════════════════════════════════════════ -->
<div class="page" id="page-ai">
  <div style="padding-top:24px">

    <!-- ═══ AI Engine Monitor — Header ═══ -->
    <div class="section-label">AI Engine Monitor</div>
    <div class="row4" style="margin-bottom:16px">
      <div class="stat-tile tile-dark"><div class="val val-green" id="ai_running">-</div><div class="lbl">Running</div></div>
      <div class="stat-tile tile-dark"><div class="val val-blue" id="ai_queued">-</div><div class="lbl">Queued</div></div>
      <div class="stat-tile tile-dark"><div class="val val-red" id="ai_stuck">-</div><div class="lbl">Stuck</div></div>
      <div class="stat-tile tile-dark"><div class="val val-dim" id="ai_total">-</div><div class="lbl">Total Shown</div></div>
    </div>

    <!-- ═══ Mode selector ═══ -->
    <div style="margin-bottom:16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <button class="btn-mode active" onclick="setAIMode('running',this)">Running</button>
      <button class="btn-mode" onclick="setAIMode('all',this)">All Jobs</button>
      <button class="btn-mode" onclick="setAIMode('stuck',this)">Stuck</button>
      <input id="ai-ticker-filter" type="text" placeholder="Filter by ticker..." style="width:140px;background:#0a0a0a;border:1px solid #30363d;border-radius:6px;padding:6px 10px;color:#c9d1d9;font-size:11px;margin-left:12px" oninput="loadAIEngine()">
      <span class="ts" id="ai_updated" style="margin-left:auto">Loading...</span>
    </div>

    <!-- ═══ Running Jobs Table ═══ -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><span class="card-title">Jobs</span></div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>Ticker</th><th>Status</th><th>Phase / Stage</th><th>Prog</th><th>Age</th><th>Elapsed</th><th>Scan</th><th>Tokens</th><th>Job ID</th>
          </tr></thead>
          <tbody id="ai-jobs-tbody"><tr><td colspan="9" class="empty">No jobs found</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- ═══ Phase Timeline ═══ -->
    <div class="section-label">Phase Timelines</div>
    <div id="ai-timelines" style="margin-bottom:20px">
      <div class="empty">Select a running job to view its phase timeline</div>
    </div>

    <!-- ═══ Latest Successful Summary ═══ -->
    <div class="section-label">Latest Completion per Ticker</div>
    <div style="overflow-x:auto;margin-bottom:20px">
      <table>
        <thead><tr><th>Ticker</th><th>Signal</th><th>Conf</th><th>Tier</th><th>Price</th><th>12M Target</th><th>Upside</th><th>Tokens</th><th>Date</th></tr></thead>
        <tbody id="ai-latest-tbody"><tr><td colspan="9" class="empty">No completed analyses</td></tr></tbody>
      </table>
    </div>

    <!-- ═══ AI Model Usage (keep existing) ═══ -->
    <div class="section-label">AI Model Usage &amp; Cost</div>
    <div class="ai-model-grid" style="margin-bottom:20px">
      <div class="model-card claude">
        <div class="model-card-header"><div class="model-icon">&#x1F916;</div>
          <div><div class="model-name">Claude (Anthropic)</div><div class="model-sub">Sonnet / Haiku — token_log.jsonl</div></div>
        </div>
        <div class="model-body">
          <div class="model-stat"><div class="mv claude-val" id="cl_calls">-</div><div class="ml">Calls</div></div>
          <div class="model-stat"><div class="mv claude-val" id="cl_in">-</div><div class="ml">Input Tokens</div></div>
          <div class="model-stat"><div class="mv claude-val" id="cl_out">-</div><div class="ml">Output Tokens</div></div>
        </div>
        <div class="model-footer">
          <span>Cost: <span id="cl_cost" style="color:#c9a84c">$-.--</span></span>
          <span>Cache hit: <span id="cl_cache_hit" style="color:#3fb950">-</span></span>
        </div>
      </div>
      <div class="model-card deepseek">
        <div class="model-card-header"><div class="model-icon">&#x26A1;</div>
          <div><div class="model-name">DeepSeek</div><div class="model-sub">deepseek-chat — token_log.jsonl</div></div>
        </div>
        <div class="model-body">
          <div class="model-stat"><div class="mv deepseek-val" id="ds_calls">-</div><div class="ml">Calls</div></div>
          <div class="model-stat"><div class="mv deepseek-val" id="ds_in">-</div><div class="ml">Input Tokens</div></div>
          <div class="model-stat"><div class="mv deepseek-val" id="ds_out">-</div><div class="ml">Output Tokens</div></div>
        </div>
        <div class="model-footer">
          <span>Cost: <span id="ds_cost" style="color:#c9a84c">$-.--</span></span>
          <span>Share: <span id="ds_ratio" style="color:#bc8cff">-</span></span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><span class="card-title">Session Token Totals (In-Memory)</span><span class="ts" id="tc"></span></div>
      <div class="card-body">
        <div class="stat-grid stat-grid-4">
          <div class="stat-tile tile-dark"><div class="val val-red" id="ti">-</div><div class="lbl">Input</div></div>
          <div class="stat-tile tile-dark"><div class="val val-green" id="to">-</div><div class="lbl">Output</div></div>
          <div class="stat-tile tile-dark"><div class="val val-blue" id="tr">-</div><div class="lbl">Cache Read</div></div>
          <div class="stat-tile tile-dark"><div class="val val-gold" id="tw">-</div><div class="lbl">Cache Write</div></div>
        </div>
      </div>
    </div>

    <div class="section-label">Recent AI API Calls</div>
    <div class="card">
      <div class="card-header"><span class="card-title">Recent Claude / AI Calls</span><span class="ts" id="clc"></span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Time</th><th>Endpoint</th><th>Input</th><th>Output</th><th>Cache Read</th><th>Cache Write</th></tr></thead>
        <tbody id="ct"><tr><td colspan="6" class="empty">No AI calls yet</td></tr></tbody></table>
      </div>
    </div>

    <div class="section-label">Scraper Engine</div>
    <div class="card">
      <div class="card-header"><span class="card-title">Scraper Cache Age</span></div>
      <div class="card-body"><div class="stat-grid stat-grid-4" id="scraper_status_grid"><div class="empty" style="grid-column:1/-1">Loading...</div></div></div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════
     PAGE: HARVESTERS
═══════════════════════════════════════════════════════════ -->
<div class="page" id="page-harvesters">
  <div style="padding-top:24px">
    <div class="section-label">Background Harvesters</div>
    <div class="row2" style="margin-bottom:20px">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Status &amp; Controls</span>
          <div style="display:flex;gap:8px">
            <button class="btn-view" onclick="triggerHarvest('youtube')" id="btn-yt-harvest">&#x1F3A5; YouTube</button>
            <button class="btn-view" onclick="triggerHarvest('advisor')" id="btn-adv-harvest">&#x1F4BC; Advisor</button>
            <button class="btn-view" onclick="triggerHarvest('news')" id="btn-news-harvest">&#x1F4F0; News</button>
          </div>
        </div>
        <div class="card-body"><div class="stat-grid stat-grid-4" id="harvest-status-grid"><div class="empty" style="grid-column:1/-1">Loading...</div></div></div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Harvester Logs</span><span class="ts" id="hrc"></span></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>Time</th><th>Harvester</th><th>Result</th></tr></thead>
          <tbody id="hrt"><tr><td colspan="3" class="empty">No logs</td></tr></tbody></table>
        </div>
      </div>
    </div>

    <div class="section-label">Latest Harvested Content</div>
    <div class="row2">
      <div class="card">
        <div class="card-header"><span class="card-title">News Articles (last 20)</span></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>Time</th><th>Ticker</th><th>Headline</th><th>Sent</th></tr></thead>
          <tbody id="lnt2"><tr><td colspan="4" class="empty">No news</td></tr></tbody></table>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">YouTube Videos (last 20)</span></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>Time</th><th>Ticker</th><th>Channel</th><th>Title</th></tr></thead>
          <tbody id="lvt2"><tr><td colspan="4" class="empty">No videos</td></tr></tbody></table>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════
     PAGE: ARCHIVE
═══════════════════════════════════════════════════════════ -->
<div class="page" id="page-archive">
  <div style="padding-top:24px">
    <div class="section-label">Historical Analysis Archive (All Users)</div>
    <div class="card">
      <div class="card-header"><span class="card-title">All Analyses (DB)</span><span class="ts" id="hnc"></span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Created</th><th>Ticker</th><th>Date</th><th>Signal</th><th>Conf</th><th>User</th><th>Correct</th><th>Details</th></tr></thead>
        <tbody id="ht"><tr><td colspan="8" class="empty">No data</td></tr></tbody></table>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════
     PAGE: REQUESTS
═══════════════════════════════════════════════════════════ -->
<div class="page" id="page-requests">
  <div style="padding-top:24px">
    <div class="section-label">API Request Log</div>
    <div class="card">
      <div class="card-header"><span class="card-title">Last 50 Requests</span><span class="ts" id="rc"></span></div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>Time</th><th>Method</th><th>Path</th><th>Params</th><th>Status</th><th>Duration</th></tr></thead>
        <tbody id="rt"><tr><td colspan="6" class="empty">No requests</td></tr></tbody></table>
      </div>
    </div>
  </div>
</div>

<script>
// ─── Admin auth ──────────────────────────────────────────────
// Admin JWT kept for this tab only: prompted once, cleared on 401/403 so the next refresh re-prompts.
function authHeaders(){
  let t=sessionStorage.getItem('nivesh_admin_jwt');
  if(!t){t=(prompt('Admin JWT (Bearer token):')||'').trim();if(t)sessionStorage.setItem('nivesh_admin_jwt',t);}
  return {'Authorization':'Bearer '+t};
}
async function adminFetch(url,opts){
  const r=await fetch(url,{...(opts||{}),headers:authHeaders()});
  if(r.status===401||r.status===403)sessionStorage.removeItem('nivesh_admin_jwt');
  return r;
}

// ─── Charts ─────────────────────────────────────────────────
let chartAlloc=null, chartSigs=null, chartVal=null, chartPnl=null, chartNw=null;

function destroyChart(c){if(c){c.destroy();return null;}return null;}

const expandedIds=new Set();
const activeTabs2={};
let currentUserData=null;
let currentUserTab='portfolio';

// ─── Formatting ──────────────────────────────────────────────
// Every server-supplied string (request paths, usernames, scraped titles, LLM text) goes through esc() before innerHTML.
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function fmt(n){if(n==null)return'-';if(n>=1e9)return(n/1e9).toFixed(2)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return''+n}
function fmtINR(n){if(n==null||isNaN(n))return'-';const abs=Math.abs(n);let s;if(abs>=1e7)s=(n/1e7).toFixed(2)+' Cr';else if(abs>=1e5)s=(n/1e5).toFixed(2)+' L';else s=n.toFixed(0).replace(/\\B(?=(\\d{3})+(?!\\d))/g,',');return(n<0?'-₹':'₹')+s.replace('-','')}
function fmtCost(c){if(c==null)return'$-.--';return'$'+c.toFixed(4)}
function ts(iso){if(!iso)return'-';return new Date(iso).toLocaleTimeString('en-IN',{hour12:false})}
function dts(iso){if(!iso)return'-';const d=new Date(iso);return d.toLocaleDateString('en-IN')+' '+d.toLocaleTimeString('en-IN',{hour12:false})}
function ela(iso){if(!iso)return'';const s=Math.floor((Date.now()-new Date(iso))/1000);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';return Math.floor(s/3600)+'h'}
function sig(s){if(!s)return'-';const u=s.toUpperCase();if(u.includes('BUY')||u==='STRONG_BUY'||u==='BULL')return`<span class="badge bull">${esc(s)}</span>`;if(u.includes('SELL')||u==='STRONG_SELL'||u==='BEAR')return`<span class="badge bear">${esc(s)}</span>`;return`<span class="badge hold">${esc(s)}</span>`}
function ctype(t){if(!t)return'-';const u=(t||'').toUpperCase();if(u==='CACHE HIT')return`<span class="badge cache">CACHE</span>`;if(u==='SMART CACHE')return`<span class="badge smart">SMART</span>`;if(u==='FULL AI')return`<span class="badge full">FULL AI</span>`;return`<span class="badge hold">${esc(t)}</span>`}
function stbadge(s){if(!s)return'-';const l=s.toLowerCase();if(l==='completed')return`<span class="badge ok">&#x2713; done</span>`;if(l==='error')return`<span class="badge err">&#x2717; error</span>`;return`<span class="badge hold">${esc(s)}</span>`}
function mbadge(m){return`<span class="badge m${esc(m||'GET')}">${esc(m)}</span>`}
function hbadge(c){if(!c)return'-';const cls=c<300?'ok':c<400?'cache':'err';return`<span class="badge ${cls}">${esc(c)}</span>`}
function fmtParams(p){if(!p||!Object.keys(p).length)return'';const s=JSON.stringify(p).replace(/[{}"]/g,'');return esc(s.length>40?s.slice(0,40)+'...':s)}
function pct(a,b){if(!b)return'0%';return Math.round(a/b*100)+'%'}
function pnlClass(v){return v>=0?'pnl-pos':'pnl-neg'}
function actionClass(a){const m={'BUY':'journal-action-buy','SELL':'journal-action-sell','HOLD':'journal-action-hold','WATCH':'journal-action-watch'};return m[a]||'';}

// ─── Navigation ──────────────────────────────────────────────
function showPage(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  document.querySelectorAll('.nav-tab').forEach(t=>{if(t.textContent.toLowerCase().includes(name.substring(0,4)))t.classList.add('active');});
  // Fix: match nav tab more precisely
  const navMap={overview:0,users:1,ai:2,harvesters:3,archive:4,requests:5};
  const tabs=document.querySelectorAll('.nav-tab');
  if(navMap[name]!==undefined)tabs[navMap[name]].classList.add('active');
}
function showUserTab(name){
  currentUserTab=name;
  document.querySelectorAll('[id^="utab-content-"]').forEach(el=>el.style.display='none');
  document.querySelectorAll('[id^="utab-"]').forEach(btn=>{if(btn.tagName==='BUTTON')btn.classList.remove('active');});
  document.getElementById('utab-content-'+name).style.display='';
  document.getElementById('utab-'+name).classList.add('active');
  if(currentUserData) renderUserTab(currentUserData, name);
}

// ─── Feature errors ──────────────────────────────────────────
function renderFeatureErrors(featureErrors){
  const grid=document.getElementById('feature-error-grid');
  if(!featureErrors||!Object.keys(featureErrors).length){grid.innerHTML='<div class="empty" style="grid-column:1/-1">No data</div>';return;}
  const icons={'News Feed':'&#x1F4F0;','Tech Momentum':'&#x1F4C8;','Screener':'&#x1F50D;','Alerts':'&#x1F514;','Portfolio Calendar':'&#x1F4C5;','Earnings Dashboard':'&#x1F4B0;','Analysis Engine':'&#x1F9E0;','YouTube Harvester':'&#x1F3A5;','Advisor Harvester':'&#x1F4BC;','Macro Impact':'&#x1F30D;','Sector Performance':'&#x1F3D7;'};
  grid.innerHTML=Object.entries(featureErrors).map(([name,errs])=>{
    const hasErrs=errs&&errs.length>0;
    const icon=icons[name]||'&#x1F534;';
    const body=hasErrs?errs.map(e=>`<div class="feat-err-item"><div class="feat-err-path">${esc(e.path||'-')}</div><div class="feat-err-meta">${hbadge(e.status)} &bull; ${ts(e.ts)}</div></div>`).join(''):`<div class="feat-clean-msg">&#x2714; No errors</div>`;
    return`<div class="feature-card ${hasErrs?'has-errors':'clean'}"><div class="feature-header"><span class="feature-name">${icon} ${esc(name)}</span><div class="feat-status-dot"></div></div><div class="feature-body">${body}</div></div>`;
  }).join('');
}

// ─── Harvest ─────────────────────────────────────────────────
function renderHarvestStatus(harvests){
  const grid=document.getElementById('harvest-status-grid');
  if(!harvests){grid.innerHTML='<div class="empty">No data</div>';return;}
  grid.innerHTML=Object.entries(harvests).map(([name,h])=>{
    let color='val-dim',val=h.status||'idle';
    if(h.status==='running'){color='val-blue';val='RUNNING...';}
    else if(h.status==='error'){color='val-red';val='ERROR';}
    else if(h.status==='idle'&&h.last_run){color='val-green';val='IDLE';}
    return`<div class="stat-tile tile-dark"><div class="val ${color}">${esc(val)}</div><div class="lbl">${esc(name.toUpperCase())}</div><div class="ts" style="margin-top:4px">${h.last_run?ts(h.last_run):'Never'}</div></div>`;
  }).join('');
  const map={youtube:'btn-yt-harvest',advisor:'btn-adv-harvest',news:'btn-news-harvest'};
  Object.entries(map).forEach(([key,id])=>{
    const btn=document.getElementById(id);if(!btn)return;
    const h=harvests[key];
    if(h&&h.status==='running'){btn.textContent=key+' Running...';btn.disabled=true;btn.style.opacity='.5';}
    else{btn.textContent=['youtube','advisor','news'].includes(key)?{youtube:'&#x1F3A5; YouTube',advisor:'&#x1F4BC; Advisor',news:'&#x1F4F0; News'}[key]:key;btn.disabled=false;btn.style.opacity='1';}
  });
}

async function triggerHarvest(type){
  const ep={youtube:'harvest-youtube',advisor:'harvest-advisors',news:'harvest-news'};
  const r=await adminFetch('/api/v1/admin/'+ep[type],{method:'POST'});
  if(r.ok)refreshAll();else alert('Failed: '+r.status);
}

function toggleDetails(id){
  const el=document.getElementById('details-'+id);
  if(expandedIds.has(id)){expandedIds.delete(id);el.style.display='none';}
  else{expandedIds.add(id);el.style.display='table-row';}
}

// ─── User selector population ────────────────────────────────
function populateUserList(db_stats_users, analyses){
  // We'll populate from /users endpoint via dashboard-data users list
}

// ─── Load per-user data ──────────────────────────────────────
async function loadUser(userId){
  if(!userId){document.getElementById('user-stat-chips').innerHTML='';currentUserData=null;return;}
  document.getElementById('user-stat-chips').innerHTML='<span style="color:#484f58;font-size:11px">Loading...</span>';
  try{
    const r=await adminFetch('/dashboard-user-data?user_id='+userId);
    if(!r.ok){document.getElementById('user-stat-chips').innerHTML='<span class="badge err">HTTP '+r.status+' '+esc(r.statusText)+'</span>';return;}
    const d=await r.json();
    currentUserData=d;
    // Stat chips
    const u=d.user||{};
    const ps=d.portfolio_summary||{};
    const acc=d.accuracy||{};
    document.getElementById('user-stat-chips').innerHTML=`
      <div class="user-stat-chip">&#x1F464; <span class="chip-val">${esc(u.display_name||u.username)}</span></div>
      <div class="user-stat-chip">Holdings: <span class="chip-val">${ps.holdings_count||0}</span></div>
      <div class="user-stat-chip">Invested: <span class="chip-val">${fmtINR(ps.total_invested||0)}</span></div>
      <div class="user-stat-chip">Analyses: <span class="chip-val">${(d.analyses||[]).length}</span></div>
      <div class="user-stat-chip">Accuracy: <span class="chip-val">${acc.accuracy_pct!=null?acc.accuracy_pct+'%':'N/A'}</span></div>
      <div class="user-stat-chip">Joined: <span class="chip-val">${esc(u.created_at?u.created_at.slice(0,10):'-')}</span></div>
    `;
    renderUserTab(d, currentUserTab);
  }catch(e){document.getElementById('user-stat-chips').innerHTML='<span class="badge err">Error: '+esc(e.message)+'</span>';}
}

function renderUserTab(d, tab){
  if(tab==='portfolio') renderPortfolio(d);
  else if(tab==='analyses') renderAnalyses(d);
  else if(tab==='valuation') renderValuation(d);
  else if(tab==='alerts') renderAlerts(d);
  else if(tab==='journal') renderJournal(d);
  else if(tab==='networth') renderNetWorth(d);
}

// ─── Portfolio ───────────────────────────────────────────────
function renderPortfolio(d){
  const rows=d.portfolio||[];
  const ps=d.portfolio_summary||{};
  document.getElementById('p-holdings').textContent=ps.holdings_count||0;
  document.getElementById('p-invested').textContent=fmtINR(ps.total_invested||0);
  const groups=[...new Set(rows.map(r=>r.group_name||'watchlist'))];
  document.getElementById('p-groups').textContent=groups.length;

  document.getElementById('portfolio-table').innerHTML=rows.length===0?'<tr><td colspan="9" class="empty">No holdings</td></tr>':rows.map((r,i)=>`<tr>
    <td class="ts">${i+1}</td>
    <td style="font-weight:700;color:#f0f6fc">${esc(r.ticker)}</td>
    <td style="color:#8b949e;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.company_name)}</td>
    <td>${esc(r.shares)}</td>
    <td>₹${r.buy_price.toLocaleString('en-IN',{minimumFractionDigits:2})}</td>
    <td style="color:#c9a84c;font-weight:700">${fmtINR(r.invested)}</td>
    <td><span class="badge hold">${esc(r.group_name)}</span></td>
    <td style="color:#6e7681;font-size:10px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.notes||'—')}</td>
    <td class="ts">${esc(r.created_at?r.created_at.slice(0,10):'-')}</td>
  </tr>`).join('');

  // Allocation donut
  chartAlloc=destroyChart(chartAlloc);
  if(rows.length>0){
    const groupMap={};
    rows.forEach(r=>{const g=r.group_name||'watchlist';groupMap[g]=(groupMap[g]||0)+r.invested;});
    const labels=Object.keys(groupMap),vals=Object.values(groupMap);
    const colors=['#c9a84c','#3fb950','#58a6ff','#bc8cff','#f85149','#d29922'];
    chartAlloc=new Chart(document.getElementById('chart-allocation'),{type:'doughnut',data:{labels,datasets:[{data:vals,backgroundColor:colors.slice(0,labels.length),borderColor:'#0a0a0a',borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b949e',font:{size:11}}}}}});
  }

  // Signal distribution pie
  chartSigs=destroyChart(chartSigs);
  const sd=d.signal_distribution||{};
  if(Object.keys(sd).length>0){
    const slabels=Object.keys(sd),svals=Object.values(sd);
    const scolors=slabels.map(l=>{const u=l.toUpperCase();if(u.includes('BUY')||u.includes('BULL'))return'#3fb950';if(u.includes('SELL')||u.includes('BEAR'))return'#f85149';return'#d29922';});
    chartSigs=new Chart(document.getElementById('chart-signals'),{type:'bar',data:{labels:slabels,datasets:[{data:svals,backgroundColor:scolors,borderColor:'#0a0a0a',borderWidth:1}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#6e7681',font:{size:10}},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10}},grid:{color:'#161b22'}}}}});
  }
}

// ─── AI Analysis Reports ─────────────────────────────────────
function renderAnalyses(d){
  const analyses=d.analyses||[];
  const acc=d.accuracy||{};
  document.getElementById('a-total').textContent=analyses.length;
  document.getElementById('a-correct').textContent=acc.correct??'-';
  document.getElementById('a-incorrect').textContent=acc.incorrect??'-';
  document.getElementById('a-accuracy').textContent=acc.accuracy_pct!=null?acc.accuracy_pct+'%':'N/A';

  const container=document.getElementById('analyses-list');
  if(analyses.length===0){container.innerHTML='<div class="empty">No analyses for this user</div>';return;}

  container.innerHTML=analyses.map(a=>{
    const bull=(a.bull_case||[]).slice(0,3);
    const bear=(a.bear_case||[]).slice(0,3);
    const risks=(a.key_risks||[]).slice(0,3);
    const kf=a.key_factors||{};
    const up=a.upside_downside_pct||{};
    const correctBadge=a.was_correct===true?'<span class="badge ok">&#x2713; Correct</span>':a.was_correct===false?'<span class="badge err">&#x2717; Wrong</span>':'<span class="badge hold">Unverified</span>';
    return`<div class="analysis-report">
      <div class="report-header">
        <div>
          <div class="report-ticker">${esc(a.ticker)} ${sig(a.signal)}</div>
          <div class="report-company">${esc(a.company_name)}</div>
        </div>
        <div class="report-meta">
          ${correctBadge}<br>
          Conf: <span style="color:#c9a84c">${a.confidence_pct!=null?a.confidence_pct+'%':'-'}</span><br>
          Price: <span style="color:#f0f6fc">${a.current_price_inr!=null?fmtINR(a.current_price_inr):'-'}</span><br>
          <span class="ts">${esc(a.created_at?a.created_at.slice(0,10):'-')}</span>
        </div>
      </div>
      <div class="target-prices">
        <div class="target-chip"><div class="tv">${a.target_short!=null?fmtINR(a.target_short):'-'}</div><div class="tl">3M Target ${up.short_term!=null?'('+up.short_term.toFixed(1)+'%)':''}</div></div>
        <div class="target-chip"><div class="tv">${a.target_medium!=null?fmtINR(a.target_medium):'-'}</div><div class="tl">12M Target ${up.medium_term!=null?'('+up.medium_term.toFixed(1)+'%)':''}</div></div>
        <div class="target-chip"><div class="tv">${a.target_long!=null?fmtINR(a.target_long):'-'}</div><div class="tl">36M Target ${up.long_term!=null?'('+up.long_term.toFixed(1)+'%)':''}</div></div>
      </div>
      <div class="report-body">
        <div class="report-col">
          <h4>&#x1F7E2; Bull Case</h4>
          <ul class="report-list">${bull.length?bull.map(b=>`<li>${esc(b)}</li>`).join(''):'<li style="color:#484f58">No bull case</li>'}</ul>
          <h4 style="margin-top:10px">&#x1F514; Key Risks</h4>
          <ul class="report-list">${risks.length?risks.map(r=>`<li>${esc(r)}</li>`).join(''):'<li style="color:#484f58">No risks</li>'}</ul>
        </div>
        <div class="report-col">
          <h4>&#x1F534; Bear Case</h4>
          <ul class="report-list">${bear.length?bear.map(b=>`<li>${esc(b)}</li>`).join(''):'<li style="color:#484f58">No bear case</li>'}</ul>
          <h4 style="margin-top:10px">&#x1F4CA; Key Factors</h4>
          <div class="key-factors">
            ${Object.entries(kf).slice(0,6).map(([k,v])=>`<div class="kf-item"><div class="kf-label">${esc(k.replace(/_/g,' '))}</div><div class="kf-val">${esc(String(v||'').slice(0,60))}</div></div>`).join('')}
          </div>
        </div>
      </div>
      ${a.outcome_delta_pct!=null?`<div style="margin-top:8px;font-size:11px;color:#6e7681">Price moved <span class="${a.outcome_delta_pct>=0?'pnl-pos':'pnl-neg'}">${a.outcome_delta_pct>=0?'+':''}${a.outcome_delta_pct.toFixed(2)}%</span> since analysis</div>`:''}
    </div>`;
  }).join('');
}

// ─── Valuation Chart ─────────────────────────────────────────
function renderValuation(d){
  const hist=d.valuation_history||[];
  chartVal=destroyChart(chartVal);
  chartPnl=destroyChart(chartPnl);

  const table=document.getElementById('valuation-table');
  table.innerHTML=hist.length===0?'<tr><td colspan="6" class="empty">No valuation history</td></tr>':hist.map(v=>`<tr>
    <td class="ts">${esc(v.snapshot_date)}</td>
    <td style="color:#c9a84c">${fmtINR(v.total_value)}</td>
    <td>${fmtINR(v.total_invested)}</td>
    <td class="${pnlClass(v.total_pnl)}">${fmtINR(v.total_pnl)}</td>
    <td class="${pnlClass(v.pnl_percent)}">${v.pnl_percent!=null?v.pnl_percent.toFixed(2)+'%':'-'}</td>
    <td class="ts">${v.nifty_close!=null?v.nifty_close.toFixed(0):'-'}</td>
  </tr>`).join('');

  if(hist.length===0)return;
  const labels=hist.map(v=>v.snapshot_date);
  const vals=hist.map(v=>v.total_value);
  const invested=hist.map(v=>v.total_invested);
  const pnlPct=hist.map(v=>v.pnl_percent);

  // Normalised Nifty (to compare trend)
  const niftyRaw=hist.map(v=>v.nifty_close);
  const niftyBase=niftyRaw.find(x=>x!=null);
  const valBase=vals[0]||1;
  const niftyNorm=niftyRaw.map(x=>x!=null?(x/niftyBase)*valBase:null);

  chartVal=new Chart(document.getElementById('chart-valuation'),{type:'line',data:{labels,datasets:[
    {label:'Portfolio Value',data:vals,borderColor:'#c9a84c',backgroundColor:'rgba(201,168,76,.08)',tension:.3,pointRadius:2,fill:true},
    {label:'Cost Basis',data:invested,borderColor:'#58a6ff',backgroundColor:'transparent',tension:.3,pointRadius:1,borderDash:[4,4]},
    {label:'Nifty (norm)',data:niftyNorm,borderColor:'#6e7681',backgroundColor:'transparent',tension:.3,pointRadius:1,borderDash:[2,4]},
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b949e',font:{size:10}}}},scales:{x:{ticks:{color:'#6e7681',font:{size:9},maxRotation:45},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10},callback:v=>fmtINR(v)},grid:{color:'#161b22'}}}}});

  chartPnl=new Chart(document.getElementById('chart-pnl-pct'),{type:'bar',data:{labels,datasets:[{label:'P&L %',data:pnlPct,backgroundColor:pnlPct.map(v=>v>=0?'rgba(63,185,80,.6)':'rgba(248,81,73,.6)'),borderColor:pnlPct.map(v=>v>=0?'#3fb950':'#f85149'),borderWidth:1}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#6e7681',font:{size:9},maxRotation:45},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10},callback:v=>v+'%'},grid:{color:'#161b22'}}}}});
}

// ─── Alerts ──────────────────────────────────────────────────
function renderAlerts(d){
  const alerts=d.alerts||[];
  const container=document.getElementById('alerts-list');
  if(alerts.length===0){container.innerHTML='<div class="empty">No price alerts</div>';return;}
  container.innerHTML=alerts.map(a=>`<div class="alert-item ${a.triggered?'alert-triggered':''}">
    <div>
      <span style="font-weight:700;color:#f0f6fc">${esc(a.ticker)}</span>
      <span class="ts" style="margin-left:8px">${esc(a.created_at?a.created_at.slice(0,10):'-')}</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#c9a84c">₹${a.target_price.toLocaleString('en-IN')}</span>
      <span class="badge ${a.direction==='above'?'bull':'bear'}">${esc(a.direction?.toUpperCase())}</span>
      ${a.triggered?'<span class="badge ok">TRIGGERED</span>':'<span class="badge hold">ACTIVE</span>'}
    </div>
  </div>`).join('');
}

// ─── Trade Journal ───────────────────────────────────────────
function renderJournal(d){
  const journal=d.trade_journal||[];
  const container=document.getElementById('journal-list');
  if(journal.length===0){container.innerHTML='<div class="empty">No journal entries</div>';return;}
  container.innerHTML=journal.map(j=>`<div class="journal-entry ${actionClass(j.action)}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <div>
        <span style="font-weight:700;color:#f0f6fc">${esc(j.ticker)}</span>
        ${j.company_name?`<span class="ts" style="margin-left:6px">${esc(j.company_name)}</span>`:''}
        <span class="badge ${j.action==='BUY'?'bull':j.action==='SELL'?'bear':'hold'}" style="margin-left:8px">${esc(j.action)}</span>
        ${j.mood?`<span class="badge hold" style="margin-left:4px">${esc(j.mood)}</span>`:''}
      </div>
      <div class="ts">${esc(j.created_at?j.created_at.slice(0,10):'-')}</div>
    </div>
    <div style="font-size:11px;color:#8b949e;margin-bottom:4px">&#x1F4B0; Price at time: <span style="color:#c9a84c">₹${j.price_at_time.toLocaleString('en-IN')}</span></div>
    <div style="font-size:11px;color:#8b949e"><strong style="color:#6e7681">Reason:</strong> ${esc(j.reason_text||'—')}</div>
    ${j.outcome_text?`<div style="font-size:11px;color:#6e7681;margin-top:4px;padding-top:4px;border-top:1px solid #21262d"><strong>Outcome:</strong> ${esc(j.outcome_text)}</div>`:''}
  </div>`).join('');
}

// ─── Net Worth ───────────────────────────────────────────────
function renderNetWorth(d){
  const ledger=d.net_worth_ledger||[];
  chartNw=destroyChart(chartNw);
  const table=document.getElementById('networth-table');
  table.innerHTML=ledger.length===0?'<tr><td colspan="7" class="empty">No net worth data</td></tr>':ledger.map(n=>`<tr>
    <td class="ts">${esc(n.snapshot_date)}</td>
    <td style="color:#c9a84c;font-weight:700">${fmtINR(n.total_value_inr)}</td>
    <td class="${pnlClass(n.daily_delta_inr||0)}">${n.daily_delta_inr!=null?fmtINR(n.daily_delta_inr):'-'}</td>
    <td class="${pnlClass(n.daily_delta_pct||0)}">${n.daily_delta_pct!=null?n.daily_delta_pct.toFixed(2)+'%':'-'}</td>
    <td style="color:#6e7681">${n.peak_value_inr!=null?fmtINR(n.peak_value_inr):'-'}</td>
    <td>${n.top_gainer_ticker?`<span class="pnl-pos">${esc(n.top_gainer_ticker)} +${n.top_gainer_pct?.toFixed(1)}%</span>`:'-'}</td>
    <td>${n.top_loser_ticker?`<span class="pnl-neg">${esc(n.top_loser_ticker)} ${n.top_loser_pct?.toFixed(1)}%</span>`:'-'}</td>
  </tr>`).join('');

  if(ledger.length===0)return;
  const labels=ledger.map(n=>n.snapshot_date);
  const vals=ledger.map(n=>n.total_value_inr);
  const peaks=ledger.map(n=>n.peak_value_inr);
  chartNw=new Chart(document.getElementById('chart-networth'),{type:'line',data:{labels,datasets:[
    {label:'Net Worth',data:vals,borderColor:'#c9a84c',backgroundColor:'rgba(201,168,76,.08)',tension:.3,pointRadius:2,fill:true},
    {label:'Peak',data:peaks,borderColor:'#3fb950',backgroundColor:'transparent',tension:.3,pointRadius:1,borderDash:[3,3]},
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b949e',font:{size:10}}}},scales:{x:{ticks:{color:'#6e7681',font:{size:9},maxRotation:45},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10},callback:v=>fmtINR(v)},grid:{color:'#161b22'}}}}});
}

// ─── Main refresh ────────────────────────────────────────────
async function refreshAll(){
  try{
    const r=await adminFetch('/dashboard-data');
    if(!r.ok){document.getElementById('lu').textContent='Auth error '+r.status;return;}
    const d=await r.json();

    document.getElementById('lu').textContent='Updated '+new Date().toLocaleTimeString('en-IN',{hour12:false});
    if(d.uptime_s!=null){
      const h=Math.floor(d.uptime_s/3600),m=Math.floor((d.uptime_s%3600)/60),s=Math.floor(d.uptime_s%60);
      document.getElementById('uptime').textContent=`Up ${h}h ${m}m ${s}s`;
    }

    // Overview stats
    if(d.db_stats){
      document.getElementById('db_u').textContent=d.db_stats.users??0;
      document.getElementById('db_h').textContent=d.db_stats.holdings??0;
      document.getElementById('db_a').textContent=d.db_stats.analyses??0;
      document.getElementById('db_s').textContent=d.db_stats.signal_events??0;
      document.getElementById('db_tj').textContent=d.db_stats.trade_journals??0;
      document.getElementById('db_news').textContent=d.db_stats.news_articles??0;
      document.getElementById('db_yt').textContent=d.db_stats.youtube_videos??0;
    }
    if(d.cache_stats){document.getElementById('c_q').textContent=d.cache_stats.quick_info??0;}

    if(d.ai_health){
      const ok='<span class="val-green">READY</span>',no='<span class="val-red">MISSING</span>';
      document.getElementById('h_ant').innerHTML=d.ai_health.anthropic?ok:no;
      document.getElementById('h_ds').innerHTML=d.ai_health.deepseek?ok:no;
      document.getElementById('h_goog').innerHTML=d.ai_health.google?ok:no;
    }

    renderFeatureErrors(d.feature_errors||{});

    // Active analyses
    const active=d.active_analyses||[];
    document.getElementById('ac').textContent=active.length+' running';
    document.getElementById('ab').innerHTML=active.length===0?'<div class="empty">No active analyses</div>':active.map(a=>`<div class="analysis-item active"><div style="display:flex;justify-content:space-between;align-items:center"><span class="a-ticker">${esc(a.ticker)}</span><span class="ts">${ts(a.start_ts)}</span></div><div class="a-meta">${esc(a.exchange||'NSE')} &bull; User ${esc(a.user_id||'N/A')} &bull; running ${ela(a.start_ts)}</div><div class="a-stage"><span class="s-dot"></span>${esc(a.stage||'Processing...')}</div></div>`).join('');

    // Recent analyses
    const an=d.recent_analyses||[];
    document.getElementById('anc').textContent=an.length+' shown';
    document.getElementById('at').innerHTML=an.length===0?'<tr><td colspan="6" class="empty">No activity</td></tr>':an.slice(0,15).map(a=>`<tr><td class="ts">${ts(a.start_ts||a.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(a.ticker)}</td><td>${ctype(a.cache_type)}</td><td>${sig(a.signal)}</td><td class="ts">${a.duration_s!=null?a.duration_s+'s':'-'}</td><td>${stbadge(a.status)}</td></tr>`).join('');

    // News / videos (overview & harvesters tabs)
    const lnews=d.latest_news||[];
    document.getElementById('lnc').textContent=lnews.length+' recent';
    const newsHtml=lnews.length===0?'<tr><td colspan="4" class="empty">No news</td></tr>':lnews.map(n=>`<tr><td class="ts">${ts(n.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(n.ticker||'—')}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${n.red_flag?'<span class="badge err">&#x1F6A9;</span> ':''}${esc(n.headline)}</td><td>${n.sentiment?`<span class="badge ${esc(n.sentiment.toLowerCase())}">${esc(n.sentiment)}</span>`:'—'}</td></tr>`).join('');
    document.getElementById('lnt').innerHTML=newsHtml;
    document.getElementById('lnt2').innerHTML=newsHtml;

    const lvideos=d.latest_videos||[];
    document.getElementById('lvc').textContent=lvideos.length+' recent';
    const vidHtml=lvideos.length===0?'<tr><td colspan="4" class="empty">No videos</td></tr>':lvideos.map(v=>`<tr><td class="ts">${ts(v.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(v.ticker||'—')}</td><td style="color:#bc8cff">${esc(v.channel)}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(v.title)}</td></tr>`).join('');
    document.getElementById('lvt').innerHTML=vidHtml;
    document.getElementById('lvt2').innerHTML=vidHtml;

    // Harvesters
    renderHarvestStatus(d.harvest_status);
    const hlogs=d.harvest_logs||[];
    document.getElementById('hrc').textContent=hlogs.length+' logged';
    document.getElementById('hrt').innerHTML=hlogs.length===0?'<tr><td colspan="3" class="empty">No logs</td></tr>':hlogs.map(l=>`<tr><td class="ts">${ts(l.ts)}</td><td style="font-weight:700;color:#c9a84c">${esc(l.key.toUpperCase())}</td><td style="font-size:10px;color:#8b949e;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(JSON.stringify(l.result))}</td></tr>`).join('');

    // AI stats
    const cl=d.claude_stats||{},ds=d.deepseek_stats||{},tok=d.token_stats||{};
    document.getElementById('cl_calls').textContent=fmt(cl.calls||0);
    document.getElementById('cl_in').textContent=fmt(cl.input_tokens||0);
    document.getElementById('cl_out').textContent=fmt(cl.output_tokens||0);
    document.getElementById('cl_cost').textContent=fmtCost(cl.cost_usd||0);
    const totalIn=tok.total_input||0,cacheRead=tok.total_cache_read||0;
    document.getElementById('cl_cache_hit').textContent=totalIn>0?pct(cacheRead,totalIn+cacheRead):'0%';
    document.getElementById('ds_calls').textContent=fmt(ds.calls||0);
    document.getElementById('ds_in').textContent=fmt(ds.input_tokens||0);
    document.getElementById('ds_out').textContent=fmt(ds.output_tokens||0);
    document.getElementById('ds_cost').textContent=fmtCost(ds.cost_usd||0);
    const totalCalls=(cl.calls||0)+(ds.calls||0);
    document.getElementById('ds_ratio').textContent=totalCalls>0?pct(ds.calls||0,totalCalls)+' of calls':'0%';
    document.getElementById('ti').textContent=fmt(tok.total_input||0);
    document.getElementById('to').textContent=fmt(tok.total_output||0);
    document.getElementById('tr').textContent=fmt(tok.total_cache_read||0);
    document.getElementById('tw').textContent=fmt(tok.total_cache_write||0);
    const un=d.unknown_stats||{};
    document.getElementById('tc').textContent=(tok.total_calls||0)+' calls this session'+(un.calls?' | '+fmt(un.calls)+' logged calls unpriced (no model)':'');
    const cl2=tok.recent||[];
    document.getElementById('clc').textContent=cl2.length+' recent';
    document.getElementById('ct').innerHTML=cl2.length===0?'<tr><td colspan="6" class="empty">No AI calls</td></tr>':cl2.map(c=>`<tr><td class="ts">${ts(c.ts)}</td><td style="color:#bc8cff;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.endpoint||'-')}</td><td style="color:#f85149">${fmt(c.input)}</td><td style="color:#3fb950">${fmt(c.output)}</td><td style="color:#58a6ff">${fmt(c.cache_read)}</td><td style="color:#d29922">${fmt(c.cache_write)}</td></tr>`).join('');
    if(d.cache_stats){
      const sg=document.getElementById('scraper_status_grid');
      const sdata=d.cache_stats.scraper||{};
      const skeys=Object.keys(sdata);
      sg.innerHTML=skeys.length===0?'<div class="empty" style="grid-column:1/-1">No scraper cache</div>':skeys.map((k,i)=>{const colors=['val-red','val-green','val-blue','val-gold'];return`<div class="stat-tile tile-dark"><div class="val ${colors[i%4]}">${esc(sdata[k].age_s)}s</div><div class="lbl">${esc(k)}</div></div>`;}).join('');
    }

    // Requests
    const reqs=(d.request_log||[]).slice(0,50);
    document.getElementById('rc').textContent=reqs.length+' shown';
    document.getElementById('rt').innerHTML=reqs.length===0?'<tr><td colspan="6" class="empty">No requests</td></tr>':reqs.map(r=>`<tr><td class="ts">${ts(r.ts)}</td><td>${mbadge(r.method)}</td><td class="path" title="${esc(r.path)}">${esc(r.path)}</td><td class="ts">${fmtParams(r.params)}</td><td>${hbadge(r.status)}</td><td class="ts">${r.duration_ms!=null?esc(r.duration_ms)+'ms':'-'}</td></tr>`).join('');

    // Archive
    const hist=d.historical_analyses||[];
    document.getElementById('hnc').textContent=hist.length+' records';
    document.getElementById('ht').innerHTML=hist.length===0?'<tr><td colspan="8" class="empty">No data</td></tr>':hist.map(h=>{
      const isExp=expandedIds.has(h.id);
      let fp='';try{fp=JSON.stringify(JSON.parse(h.full_json),null,2);}catch(e){fp=h.full_json||'';}
      return`<tr><td class="ts">${dts(h.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(h.ticker)}</td><td class="ts">${esc(h.analysis_date||'-')}</td><td>${sig(h.signal)}</td><td style="color:#d29922">${h.confidence!=null?h.confidence+'%':'-'}</td><td class="ts">${esc(h.user_id||'-')}</td><td>${h.full_json&&JSON.parse(h.full_json).was_correct===true?'<span class="badge ok">&#x2713;</span>':h.full_json&&JSON.parse(h.full_json).was_correct===false?'<span class="badge err">&#x2717;</span>':'-'}</td><td><button class="btn-view" onclick="toggleDetails(${Number(h.id)})">View</button></td></tr>
      <tr id="details-${Number(h.id)}" style="display:${isExp?'table-row':'none'}"><td colspan="8"><div class="archive-details" style="display:block"><div class="json-box">${esc(fp)}</div></div></td></tr>`;
    }).join('');

    // Populate user select on first load
    populateUserDropdown();

  }catch(e){
    console.error('Dashboard error:',e);
    document.getElementById('lu').textContent='Error: '+e.message;
  }
}

// ─── User dropdown ──────────────────────────────────────────
let _usersPopulated=false;
async function populateUserDropdown(){
  if(_usersPopulated)return;
  try{
    const r=await adminFetch('/users');
    if(!r.ok){console.warn('Could not load user list: HTTP '+r.status);return;}
    const users=await r.json();
    if(!Array.isArray(users)||users.length===0){
      console.warn('No users returned from /users');return;
    }
    const sel=document.getElementById('user-select');
    sel.innerHTML='<option value="">-- select user --</option>'+users.map(u=>`<option value="${esc(u.id)}">#${esc(u.id)} ${esc(u.display_name||u.username)} (${esc(u.username)})</option>`).join('');
    _usersPopulated=true;
  }catch(e){console.warn('Could not populate user list:',e);}
}

// ─── AI Engine Monitor ────────────────────────────────────────
let _aiMode='running';

function setAIMode(mode,btn){
  _aiMode=mode;
  document.querySelectorAll('.btn-mode').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  document.getElementById('ai-ticker-filter').value='';
  loadAIEngine();
}

async function loadAIEngine(){
  const ticker=document.getElementById('ai-ticker-filter')?.value?.trim()||'';
  const params=new URLSearchParams({mode:_aiMode,limit:'30'});
  if(ticker)params.set('ticker',ticker);
  try{
    const r=await adminFetch('/api/v1/dashboard/ai-engine?'+params);
    if(!r.ok){console.warn('AI engine fetch failed:',r.status);return;}
    const d=await r.json();
    renderAIEngine(d);
  }catch(e){console.warn('AI engine error:',e);}
}

function renderAIEngine(d){
  if(!d)return;
  const s=d.summary||{};
  document.getElementById('ai_running').textContent=s.running??0;
  document.getElementById('ai_queued').textContent=s.queued??0;
  document.getElementById('ai_stuck').textContent=s.stuck??0;
  const jobs=d.jobs||[];
  document.getElementById('ai_total').textContent=jobs.length;
  document.getElementById('ai_updated').textContent=ts(d.generated_at);

  const tbody=document.getElementById('ai-jobs-tbody');
  if(jobs.length===0){
    tbody.innerHTML='<tr><td colspan="9" class="empty">No jobs found</td></tr>';
  }else{
    tbody.innerHTML=jobs.map(j=>{
      const status=j.status||'?';
      const scl=status==='RUNNING'?'active':status==='SUCCEEDED'?'ok':'err';
      const pct=j.progress_pct||0;
      const barCls=status==='SUCCEEDED'?'done':status==='FAILED'?'failed':'running';
      const tl=j.phase_timeline||[];
      const hasTimeline=tl.length>0;
      return `<tr>
        <td style="font-weight:700;color:#f0f6fc">${esc(j.ticker||'-')}${j.is_stuck?' <span class="badge err">STUCK</span>':''}</td>
        <td><span class="badge ${scl}">${esc(status)}</span></td>
        <td style="max-width:180px"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(j.current_phase||j.stage||'-')}</div><div class="phase-bar"><div class="phase-bar-fill ${barCls}" style="width:${Number(pct)||0}%"></div></div></td>
        <td class="ts">${esc(pct)}%</td>
        <td class="ts">${esc(j.age_label||'-')}</td>
        <td class="ts">${esc(j.elapsed_label||'-')}</td>
        <td><span class="badge hold">${esc(j.scan_type||'standard')}</span></td>
        <td class="ts" style="color:#bc8cff">${fmt(j.tokens_used||0)}</td>
        <td style="max-width:110px"><span class="ts" style="font-size:9px">${esc(j.job_id)}</span>${j.is_stuck?` <button class="btn-view err" style="font-size:9px;padding:2px 6px" data-job="${esc(j.job_id)}" onclick="cancelAIMonitorJob(this.dataset.job)">X</button>`:''}</td>
      </tr>
      ${hasTimeline?`<tr><td colspan="9" style="padding:4px 12px 8px">
        <div style="display:flex;gap:4px;flex-wrap:wrap;font-size:10px;color:#6e7681">
          ${tl.map((p,i,a)=>{
            const dc=p.state==='active'?'active':p.state==='done'?'done':p.state==='failed'?'failed':'';
            return `<div style="display:flex;align-items:center;gap:6px;padding:2px 6px;background:#0d1117;border-radius:4px;border:1px solid #21262d;flex:0 0 auto;min-width:100px">
              <div class="timeline-dot ${dc}"></div>
              <div><div style="color:#8b949e;font-weight:600">${esc(p.stage||'-')}</div><div style="font-size:9px;color:#484f58;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(String(p.message||'').slice(0,50))}</div></div>
            </div>`;
          }).join('')}
        </div>
      </td></tr>`:''}`;
    }).join('');
  }

  // Latest by ticker
  const latest=d.latest_success||[];
  const ltbody=document.getElementById('ai-latest-tbody');
  if(latest.length===0){
    ltbody.innerHTML='<tr><td colspan="9" class="empty">No completed analyses</td></tr>';
  }else{
    ltbody.innerHTML=latest.map(l=>`<tr>
      <td style="font-weight:700;color:#f0f6fc">${esc(l.ticker||'-')}</td>
      <td>${sig(l.signal)}</td>
      <td style="color:#d29922">${l.confidence_pct!=null?l.confidence_pct+'%':'-'}</td>
      <td class="ts">${esc(l.analysis_tier||l.scan_type||'-')}</td>
      <td style="color:#c9a84c">${l.current_price_inr!=null?'₹'+l.current_price_inr.toLocaleString('en-IN'):'-'}</td>
      <td style="color:#c9a84c">${l.target_12m!=null?'₹'+l.target_12m.toLocaleString('en-IN'):'-'}</td>
      <td class="${l.upside_12m_pct!=null&&l.upside_12m_pct>0?'pnl-pos':'pnl-neg'}">${l.upside_12m_pct!=null?l.upside_12m_pct.toFixed(1)+'%':'-'}</td>
      <td class="ts">${fmt(l.tokens_used||0)}</td>
      <td class="ts">${esc(l.analysis_date||'-')}</td>
    </tr>`).join('');
  }
}

async function cancelAIMonitorJob(jobId){
  if(!confirm('Cancel job '+jobId+'?'))return;
  try{
    const r=await adminFetch('/analyze/'+jobId+'/cancel',{method:'POST'});
    if(r.ok)loadAIEngine();
    else console.warn('Cancel failed:',r.status);
  }catch(e){console.warn('Cancel error:',e);}
}

// Init
refreshAll();
loadAIEngine();
setInterval(refreshAll, 30000);
setInterval(loadAIEngine, 10000);
</script>
</body>
</html>"""


# ponytail: unsafe-inline for the admin page only; move inline JS to a static file to drop it
_ADMIN_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)


@app.get("/", response_class=HTMLResponse)
def dashboard_html():
    """Return the raw HTML content for the admin dashboard."""
    return HTMLResponse(content=_DASHBOARD_HTML, headers={"Content-Security-Policy": _ADMIN_CSP})


@app.get("/dashboard-data")
def dashboard_data(authorization: str = Header(None)):
    """
    Fetch comprehensive telemetry and state data for the admin dashboard.

    Args:
        authorization: Admin authorization header.

    Returns:
        A dictionary containing system uptime, active jobs, token stats, cache health,
        and database entity counts.
    """
    require_admin(authorization)
    uptime = (datetime.now(timezone.utc) - _ds.SERVER_START).total_seconds()
    
    # Fetch historical analyses and stats from DB
    history = []
    db_stats = {}
    try:
        with get_session() as session:
            rows = session.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).limit(100).all()
            for r in rows:
                history.append({
                    "id": r.id,
                    "ts": r.created_at.isoformat(),
                    "ticker": r.ticker,
                    "analysis_date": r.analysis_date,
                    "signal": r.signal,
                    "confidence": r.confidence_pct,
                    "raw_output": r.raw_output,
                    "full_json": r.full_json,
                    "user_id": r.user_id,
                })
            db_stats = {
                "users": session.query(User).count(),
                "holdings": session.query(Portfolio).count(),
                "analyses": session.query(AnalysisHistory).count(),
                "signal_events": session.query(SignalEvent).count() if 'SignalEvent' in globals() else 0,
                "trade_journals": session.query(TradeJournal).count(),
                "news_articles": session.query(NewsArticle).count(),
                "youtube_videos": session.query(YouTubeVideo).count(),
            }
            # Fetch latest news and videos
            latest_news = []
            for n in session.query(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(10).all():
                latest_news.append({
                    "headline": n.headline,
                    "ticker": n.ticker,
                    "ts": n.published_at.isoformat(),
                    "sentiment": n.sentiment,
                    "red_flag": n.is_red_flag
                })
            latest_videos = []
            for v in session.query(YouTubeVideo).order_by(YouTubeVideo.published_at.desc()).limit(10).all():
                latest_videos.append({
                    "title": v.title,
                    "channel": v.channel_name,
                    "ts": v.published_at.isoformat(),
                    "ticker": v.matched_ticker
                })
    except Exception as e:
        logging.info(f"Error fetching history for dashboard: {e}")

    try:
        import services.scraper as scr
        scraper_cache = {}
        raw_items = None
        try:
            # TTLLRUCache or similar has no items() — convert to dict first
            raw_items = list(scr._CACHE.items())
        except (AttributeError, TypeError):
            # fallback: try dict access
            try:
                raw_items = list(dict(scr._CACHE).items())
            except Exception as _e:
                raw_items = {}
        if raw_items:
            for k, v in raw_items:
                try:
                    # v may be a (value, timestamp) tuple or a {"ts": ...} dict
                    if isinstance(v, dict):
                        ts = v.get("ts", 0)
                    elif isinstance(v, (tuple, list)) and len(v) >= 2:
                        ts = v[1]
                    else:
                        ts = 0
                    scraper_cache[str(k)] = {"age_s": round(time.time() - float(ts))}
                except Exception as _e:
                    continue
    except Exception as _e:
        scraper_cache = {}

    cache_stats = {
        "quick_info": len(_quick_info_cache),  # helpers' live L1 cache the routers fill
        "scraper": scraper_cache
    }

    with _ds._dash_lock:
        active = list(_ds._active_analyses.values())
        completed = list(_ds._completed_analyses)
        reqs = list(_ds._request_log)
        tok = {
            "total_input":       _ds._token_stats["total_input"],
            "total_output":      _ds._token_stats["total_output"],
            "total_cache_read":  _ds._token_stats["total_cache_read"],
            "total_cache_write": _ds._token_stats["total_cache_write"],
            "total_calls":       _ds._token_stats["total_calls"],
            "recent":            list(_ds._token_stats["recent"]),
        }

    # Separate Claude vs DeepSeek stats from token_log.jsonl
    ai_health = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
    }
    # Bucket every token_log.jsonl line by the vendor of its logged model. Lines with no
    # known model (all lines written before the model field existed) are counted but
    # never priced — guessing Sonnet rates misreported DeepSeek-heavy spend.
    stats_by_vendor = {
        "claude":   {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "deepseek": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "unknown":  {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": None},
    }
    try:
        token_log = Path(_ds.TOKEN_LOG_PATH)
        if token_log.exists():
            with open(token_log, "r") as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        inp = e.get("input_tokens", 0) or 0
                        out = e.get("output_tokens", 0) or 0
                        bucket = stats_by_vendor[_ds.model_vendor(e.get("model"))]
                        bucket["calls"] += 1
                        bucket["input_tokens"] += inp
                        bucket["output_tokens"] += out
                        cost = _ds.estimate_cost_usd(e.get("model"), inp, out)
                        if cost is not None and bucket["cost_usd"] is not None:
                            bucket["cost_usd"] += cost
                    except Exception as _e:
                        continue
    except Exception as _e:
        logging.warning(f"[dashboard] token log read failed: {_e}")
    claude_stats = stats_by_vendor["claude"]
    deepseek_stats = stats_by_vendor["deepseek"]
    unknown_stats = stats_by_vendor["unknown"]

    # Per-feature error extraction from request log
    feature_routes = {
        "News Feed":            ["/api/v1/home-feed"],
        "Tech Momentum":        ["/api/v1/market/dashboard-pulse"],
        "Screener":             ["/screener"],
        "Alerts":               ["/alerts/add", "/alerts/"],
        "Portfolio Calendar":   ["/api/v1/portfolio/valuation-history"],
        "Earnings Dashboard":   ["/earnings-calendar", "/api/v1/earnings/"],
        "Analysis Engine":      ["/analyze"],
        "YouTube Harvester":    ["/api/v1/admin/harvest-youtube"],
        "Advisor Harvester":    ["/api/v1/admin/harvest-advisors"],
        "Macro Impact":         ["/api/v1/macro-impact"],
        "Sector Performance":   ["/sector-performance"],
    }
    feature_errors = {}
    with _ds._dash_lock:
        all_reqs = list(_ds._request_log)
        current_harvests = {k: v.copy() for k, v in _ds._harvest_status.items()}
        h_logs = list(_ds._dash_logs)

    for feature, prefixes in feature_routes.items():
        errs = []
        for r in all_reqs:
            path = r.get("path", "")
            if any(path.startswith(p) or path == p for p in prefixes):
                if r.get("status", 200) >= 400:
                    errs.append({
                        "ts": r.get("ts"),
                        "path": path,
                        "status": r.get("status"),
                        "duration_ms": r.get("duration_ms"),
                    })
        feature_errors[feature] = errs[:5]

    # ── v2 engine: merge DB-backed active jobs ───────────────────────────
    db_active_jobs = {}
    try:
        import database
        for j in database.list_active_jobs():
            db_active_jobs[j["job_id"]] = {
                "job_id": j["job_id"], "user_id": j.get("user_id"),
                "ticker": j["ticker"], "scan_type": j.get("scan_type"),
                "status": j["status"], "stage": j.get("stage"),
                "progress_pct": j.get("progress_pct", 0),
                "checkpoints": (j.get("checkpoints") or [])[-5:],
                "tokens_used": j.get("tokens_used"),
                "error": j.get("error"),
            }
    except Exception as e:
        logging.info(f"[dashboard] DB active jobs read failed: {e}")

    merged_active = list({**db_active_jobs, **{a.get("job_id", ""): a for a in active}}.values())

    return {
        "server_start":    _ds.SERVER_START.isoformat(),
        "uptime_s":        round(uptime),
        "active_analyses": merged_active,
        "recent_analyses": completed,
        "historical_analyses": history,
        "request_log":     reqs,
        "token_stats":     tok,
        "db_stats":        db_stats,
        "cache_stats":     cache_stats,
        "claude_stats":    claude_stats,
        "deepseek_stats":  deepseek_stats,
        "unknown_stats":   unknown_stats,
        "feature_errors":  feature_errors,
        "harvest_status":  current_harvests,
        "harvest_logs":    h_logs,
        "latest_news":     latest_news if 'latest_news' in locals() else [],
        "latest_videos":   latest_videos if 'latest_videos' in locals() else [],
        "ai_health":       ai_health,
        "ai_engine":       build_ai_engine_monitor(mode="running"),
    }


@app.get("/dashboard-user-data")
def dashboard_user_data(user_id: int, authorization: str = Header(None)):
    """
    Fetch specific data and metrics for a given user for the admin dashboard.

    Args:
        user_id: Target user's ID.
        authorization: Admin authorization header.

    Returns:
        A dictionary containing the user's details, portfolio holdings, generated
        charts, and recent AI analyses.
    """
    require_admin(authorization)
    result: dict = {"user_id": user_id}
    try:
        with get_session() as session:
            # ── User info ──
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            result["user"] = {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }

            # ── Portfolio ──
            holdings = session.query(Portfolio).filter(Portfolio.user_id == user_id).all()
            portfolio_rows = []
            total_invested = 0.0
            for h in holdings:
                invested = h.shares * h.buy_price
                total_invested += invested
                portfolio_rows.append({
                    "id": h.id,
                    "ticker": h.ticker,
                    "company_name": h.company_name,
                    "shares": h.shares,
                    "buy_price": h.buy_price,
                    "group_name": h.group_name or "watchlist",
                    "notes": h.notes or "",
                    "invested": round(invested, 2),
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                })
            result["portfolio"] = portfolio_rows
            result["portfolio_summary"] = {"total_invested": round(total_invested, 2), "holdings_count": len(portfolio_rows)}

            # ── Analysis History ──
            analyses = session.query(AnalysisHistory).filter(
                AnalysisHistory.user_id == user_id
            ).order_by(AnalysisHistory.created_at.desc()).limit(50).all()
            analysis_rows = []
            for a in analyses:
                parsed_json = {}
                try:
                    parsed_json = json.loads(a.full_json) if a.full_json else {}
                except Exception as _e:
                    pass
                analysis_rows.append({
                    "id": a.id,
                    "ticker": a.ticker,
                    "analysis_date": a.analysis_date,
                    "signal": a.signal,
                    "confidence_pct": a.confidence_pct,
                    "target_short": a.target_short,
                    "target_medium": a.target_medium,
                    "target_long": a.target_long,
                    "promoter_pledged_pct": a.promoter_pledged_pct,
                    "outcome_delta_pct": a.outcome_delta_pct,
                    "was_correct": a.was_correct,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    # Key fields from full_json
                    "company_name": parsed_json.get("company_name", ""),
                    "bull_case": parsed_json.get("bull_case", []),
                    "bear_case": parsed_json.get("bear_case", []),
                    "key_risks": parsed_json.get("key_risks", []),
                    "key_factors": parsed_json.get("key_factors", {}),
                    "current_price_inr": parsed_json.get("current_price_inr"),
                    "upside_downside_pct": parsed_json.get("upside_downside_pct", {}),
                    "management_quality": parsed_json.get("management_quality", ""),
                    "technical_trend": parsed_json.get("technical_trend", ""),
                    "fundamental_score": parsed_json.get("fundamental_score", ""),
                    "disclaimer": parsed_json.get("disclaimer", ""),
                    "raw_output": a.raw_output or "",
                })
            result["analyses"] = analysis_rows

            # Signal distribution
            from collections import Counter
            sig_counts = Counter(a["signal"] for a in analysis_rows)
            result["signal_distribution"] = dict(sig_counts)

            # ── Watchlist / Price Alerts ──
            alerts = session.query(PriceTarget).filter(PriceTarget.user_id == user_id).order_by(PriceTarget.created_at.desc()).all()
            result["alerts"] = [{
                "id": a.id,
                "ticker": a.ticker,
                "target_price": a.target_price,
                "direction": a.direction,
                "triggered": a.triggered,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            } for a in alerts]

            # ── Trade Journal ──
            journal = session.query(TradeJournal).filter(TradeJournal.user_id == user_id).order_by(TradeJournal.created_at.desc()).all()
            result["trade_journal"] = [{
                "id": j.id,
                "ticker": j.ticker,
                "company_name": j.company_name or "",
                "action": j.action,
                "price_at_time": j.price_at_time,
                "reason_text": j.reason_text,
                "outcome_text": j.outcome_text or "",
                "mood": j.mood or "",
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            } for j in journal]

            # ── Portfolio Valuation History ──
            val_hist = session.query(PortfolioValuationHistory).filter(
                PortfolioValuationHistory.user_id == user_id
            ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()
            result["valuation_history"] = [{
                "snapshot_date": v.snapshot_date,
                "total_value": v.total_value,
                "total_invested": v.total_invested,
                "total_pnl": v.total_pnl,
                "pnl_percent": v.pnl_percent,
                "nifty_close": v.nifty_close,
            } for v in val_hist]

            # ── Net Worth Ledger ──
            nw_rows = session.query(NetWorthLedger).filter(
                NetWorthLedger.user_id == user_id
            ).order_by(NetWorthLedger.snapshot_date.asc()).all()
            result["net_worth_ledger"] = [{
                "snapshot_date": n.snapshot_date,
                "total_value_inr": n.total_value_inr,
                "daily_delta_inr": n.daily_delta_inr,
                "daily_delta_pct": n.daily_delta_pct,
                "peak_value_inr": n.peak_value_inr,
                "top_gainer_ticker": n.top_gainer_ticker,
                "top_gainer_pct": n.top_gainer_pct,
                "top_loser_ticker": n.top_loser_ticker,
                "top_loser_pct": n.top_loser_pct,
            } for n in nw_rows]

            # ── Device Tokens ──
            tokens = session.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
            result["device_tokens"] = [{
                "platform": t.platform,
                "token_preview": t.device_token[:20] + "..." if t.device_token else "",
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            } for t in tokens]

            # ── Analysis accuracy stats ──
            correct = sum(1 for a in analysis_rows if a["was_correct"] is True)
            incorrect = sum(1 for a in analysis_rows if a["was_correct"] is False)
            checked = correct + incorrect
            result["accuracy"] = {
                "correct": correct,
                "incorrect": incorrect,
                "checked": checked,
                "accuracy_pct": round(correct / checked * 100, 1) if checked > 0 else None,
            }

    except HTTPException:
        raise
    except Exception:
        logger.exception("[dashboard-user-data] failed for user %s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")

    return result
