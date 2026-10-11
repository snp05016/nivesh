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
from core.env import load_backend_env
load_backend_env()  # no-op under pytest (NIVESH_TESTING=1)

# Refuse to boot production with a forgeable JWT secret or wildcard CORS (REL-26).
from core.config_guard import docs_enabled, validate_startup_config
validate_startup_config()

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
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
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
# Lives in core.rate_limiter; the middleware below resolves it at call time.

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
        # Module-attribute lookup: core.rate_limiter._check_rate_limit is the single patch point.
        from core import rate_limiter as _rate_limiter
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse
        
        try:
            _rate_limiter._check_rate_limit(client_ip, endpoint, request.method)
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
        # Fixes #109, GH-695: never cache any response. Legacy user-data routes
        # (/portfolio/{id}, /watchlist/{id}, /alerts/{id}, ...) live outside /api/.
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(_SecurityHeadersMiddleware)
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
        # Routers raise HTTPException(500) inside `except Exception`; log that cause (SILENT-06).
        cause = exc.__cause__ or exc.__context__
        logger.error(
            "HTTP %s at %s %s: %s", exc.status_code, _req.method, _req.url.path, exc.detail,
            exc_info=(type(cause), cause, cause.__traceback__) if cause else None,
        )
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
from routers import auth, portfolio, market, analysis, portfolio_analytics, morning_brief, advisor_consensus, portfolio_exports, trade_journal, earnings, institutional, ideas, admin_errors, alerts, user, dashboard, notifications, brainstorming, strategy, copilot, anomalies, correlation, nl_screener, stress_test, sector_rotation, earnings_surprise, options_strategy, predictions, fundamentals, backtests, ml_signal, preferences, notifications_inbox, search, ipo, mutual_funds, forum, finance, compliance, subscription, kyc, fixed_deposits, account
from routers import harvester as harvester_router
from routers.health import router as health_router  # Task 56
from routers import youtube_summary as youtube_summary_router
from routers import client_telemetry

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


# Handle of the leader's price-alert poller task, cancelled on shutdown.
_price_alert_task = None


def _backfill_preferences():
    """Backfill UserPreferences for existing users without one."""
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


async def _on_startup():
    """
    Execute application startup routines.

    Initializes structured logging in every worker. Only the leader (the worker
    holding the scheduler lock) runs the one-time tasks: database tables, the
    stale-job sweep, harvester/catalog seeding, the price-alert poller and the
    preference backfill (DB-13, ARCH-07). Even with `--workers N` there is one
    alert poller (no duplicate pushes), one job sweep and one backfill.
    """
    global _price_alert_task
    # Wire up structured JSON logging (fixes #83)
    from core.logging_config import configure_logging
    configure_logging()
    # Tests are always leader: the fcntl lock is machine-wide, and another local
    # process (dev server, a parallel pytest run) holding it must not skip seeding.
    is_leader = start_scheduler() or os.environ.get("NIVESH_TESTING") == "1"
    if not is_leader:
        logging.info("[startup] follower worker: skipping one-time tasks")
        return
    # Init DB on startup (fixes #87 — moved from module level)
    init_db()
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
    _price_alert_task = asyncio.create_task(_price_alert_poller())

    # FinBERT loading is deferred to first request (lazy). Pre-warming at startup
    # causes memory spikes during model load, cascading worker death with uvicorn
    # --workers > 1. The 3-5s cost on first sentiment request is acceptable.

    threading.Thread(target=_backfill_preferences, daemon=True).start()

    # RAG ingestion is incremental and runs only in the leader scheduler
    # (harvest_worker job 'rag_ingest'), never per worker at startup.

    # ENABLE_SCHEDULER block removed (fixes #85): start_scheduler() from
    # harvest_worker (called above) already registers all cron jobs including
    # harvest_youtube_metadata, harvest_news, and snapshot_all_users.
    # The duplicate AsyncIOScheduler was causing double job execution.


async def _on_shutdown():
    # Each step runs even if an earlier one fails, so worker processes are always reaped.
    if _price_alert_task is not None:
        _price_alert_task.cancel()
    try:
        stop_scheduler()
    except Exception:
        logging.exception("[shutdown] stop_scheduler failed")
    try:
        from services.job_manager import shutdown_all
        shutdown_all()
    except Exception:
        logging.exception("[shutdown] shutdown_all failed")


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
# Dashboard
# ---------------------------------------------------------------------------

# Markup, CSS and JS live in static/admin so the page CSP can forbid inline script (AUTH-19).
_ADMIN_DIR = Path(__file__).resolve().parent / "static" / "admin"
app.mount("/admin-assets", StaticFiles(directory=_ADMIN_DIR), name="admin-assets")

# ponytail: style-src keeps 'unsafe-inline' for ~100 inline style attributes (CSS-only risk);
# move them into admin.css to drop it.
_ADMIN_CSP = (
    "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)


@app.get("/", response_class=FileResponse)
def dashboard_html():
    """Serve the admin dashboard page with its own CSP (no inline script allowed)."""
    return FileResponse(_ADMIN_DIR / "index.html", headers={"Content-Security-Policy": _ADMIN_CSP})


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
            # Summary rows only; raw_output/full_json come from /dashboard-data/analysis/{id} (GH-689).
            rows = session.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).limit(50).all()
            for r in rows:
                history.append({
                    "id": r.id,
                    "ts": r.created_at.isoformat(),
                    "ticker": r.ticker,
                    "analysis_date": r.analysis_date,
                    "signal": r.signal,
                    "confidence": r.confidence_pct,
                    "was_correct": r.was_correct,
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
    # Per-vendor spend from token_log.jsonl (one reader: core.dashboard_state, LLM-09).
    # Lines with no known model are counted under "unknown" and never priced.
    stats_by_vendor = _ds.token_usage_summary()["by_vendor"]
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
    persisted_harvests = _ds.persisted_harvest_status()  # scheduler runs from any worker (SILENT-13)
    with _ds._dash_lock:
        all_reqs = list(_ds._request_log)
        current_harvests = {k: v.copy() for k, v in _ds._harvest_status.items()}
        h_logs = list(_ds._dash_logs)
    current_harvests.update(persisted_harvests)

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


@app.get("/dashboard-data/analysis/{analysis_id}")
def dashboard_analysis_detail(analysis_id: int, authorization: str = Header(None)):
    """raw_output/full_json for one archive row, fetched when the admin expands it."""
    require_admin(authorization)
    with get_session() as session:
        row = session.query(AnalysisHistory).filter(AnalysisHistory.id == analysis_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return {"id": row.id, "raw_output": row.raw_output, "full_json": row.full_json}


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
            holdings_count = 0
            for h in holdings:
                invested = h.shares * h.buy_price
                # Watchlist rows are exported with their label but are not holdings (DB-19).
                if str(h.group_name or "watchlist") != "watchlist":
                    total_invested += invested
                    holdings_count += 1
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
            result["portfolio_summary"] = {"total_invested": round(total_invested, 2), "holdings_count": holdings_count}

            # ── Analysis History ──
            from sqlalchemy.orm import undefer
            # raw_output is deferred (PERF-08); this export ships it, so load it in the same query.
            analyses = session.query(AnalysisHistory).options(undefer(AnalysisHistory.raw_output)).filter(
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
