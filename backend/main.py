import os
import sys
import json
import hashlib
import time
import time as _time
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# v2 engine fix: tradingagents-core must be on the Python path before any imports
# that trigger orchestrator.py → tradingagents.default_config resolution.
_TRADINGAGENTS_PATH = Path(__file__).parent / "tradingagents-core"
if _TRADINGAGENTS_PATH.exists() and str(_TRADINGAGENTS_PATH) not in sys.path:
    sys.path.insert(0, str(_TRADINGAGENTS_PATH))

# ---------------------------------------------------------------------------
# Load environment before any other imports
# ---------------------------------------------------------------------------
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Disk cache — L2 persistent layer (L1 = in-memory _quick_info_cache)
from services.disk_cache import get as _dcache_get, set as _dcache_set, stats as _dcache_stats
from services.error_telemetry import CorrelationIDMiddleware

from dotenv import load_dotenv
import multiprocessing
import asyncio
from fastapi import Request
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from collections import deque
import uuid
from fastapi.responses import StreamingResponse, HTMLResponse
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
    except Exception:
        FPDF2_AVAILABLE = False

from database import init_db, get_session, save_analysis, get_recent_analyses, get_user_by_credentials, Portfolio, User, AnalysisHistory, SignalEvent, get_analysis_for_date, get_all_ticker_history, PriceTarget, TradeJournal, DeviceToken, AdvisorInsight, NewsArticle, YouTubeVideo, PortfolioValuationHistory, PKScreenerSignal, MacroEvent, NetWorthLedger, create_access_token, verify_access_token, is_admin, promote_initial_admins


# ---------------------------------------------------------------------------
# Indian Numbering System — format_indian_currency
# All monetary outputs MUST use Lakhs/Crores. Never Millions/Billions.
# ---------------------------------------------------------------------------

def format_indian_currency(value: float | int | None, *, symbol: str = "₹") -> str:
    """
    Format a numeric INR value using the Indian numbering system.

    Rules:
      - value < 0: prefix a minus sign, then format the absolute value
      - 0 ≤ |value| < 1,00,000   → "₹X" (plain, with Indian commas)
      - 1,00,000 ≤ |value| < 1,00,00,000 (< 1 Cr) → "₹X.XX Lakhs"
      - |value| ≥ 1,00,00,000   → "₹X.XX Crores"

    Examples:
      format_indian_currency(0)           → "₹0"
      format_indian_currency(75000)       → "₹75,000"
      format_indian_currency(150000)      → "₹1.50 Lakhs"
      format_indian_currency(12500000)    → "₹1.25 Crores"
      format_indian_currency(-3750000)    → "-₹37.50 Lakhs"
      format_indian_currency(1e10)        → "₹1,000.00 Crores"
    """
    if value is None:
        return f"{symbol}0"

    value = float(value)
    negative = value < 0
    abs_val = abs(value)

    LAKH = 1_00_000       # 1,00,000
    CRORE = 1_00_00_000   # 1,00,00,000

    if abs_val >= CRORE:
        formatted = f"{symbol}{abs_val / CRORE:,.2f} Crores"
    elif abs_val >= LAKH:
        formatted = f"{symbol}{abs_val / LAKH:,.2f} Lakhs"
    else:
        # Indian comma style for numbers below 1 Lakh:
        # thousands separator only (no sub-lakh grouping difference at this scale)
        formatted = f"{symbol}{abs_val:,.0f}"

    return f"-{formatted}" if negative else formatted


def _ban_western_scale(text: str, company_name: str = "") -> str:
    """
    Guard: raise ValueError if 'Million' or 'Billion' appears in output text.
    Excludes company name from check — legally registered names may contain
    these words (e.g., 'Million Lights Ltd', 'Billion Electric').
    Use in test harness or as a post-processing assertion.
    """
    import re
    check_text = text
    if company_name:
        check_text = check_text.replace(company_name, "[COMPANY_NAME]")
    if re.search(r"\b(million|billion|trillion)\b", check_text, re.IGNORECASE):
        raise ValueError(
            "Western scale (Million/Billion/Trillion) detected in output — "
            "use Lakhs/Crores instead."
        )
    return text


# ---------------------------------------------------------------------------
# Constants: Prompt Caching Blocks
# ---------------------------------------------------------------------------


import logging
import threading

_token_log_lock = threading.Lock()
TOKEN_LOG_PATH = Path(__file__).parent / "token_log.jsonl"

# ---------------------------------------------------------------------------
# Dashboard state (in-memory, main process only)
# ---------------------------------------------------------------------------
_server_start = datetime.now()
_dash_lock = threading.Lock()
_active_analyses: dict = {}          # job_id -> info dict
_completed_analyses: deque = deque(maxlen=50)
_request_log: deque = deque(maxlen=200)
_harvest_logs: deque = deque(maxlen=30)
_token_stats: dict = {
    "total_input": 0,
    "total_output": 0,
    "total_cache_read": 0,
    "total_cache_write": 0,
    "total_calls": 0,
    "recent": deque(maxlen=20),
}
_harvest_status: dict = {
    "youtube": {"status": "idle", "last_run": None, "last_result": None},
    "advisor": {"status": "idle", "last_run": None, "last_result": None},
    "news":    {"status": "idle", "last_run": None, "last_result": None},
    "filings": {"status": "idle", "last_run": None, "last_result": None},
}


def _dash_update_harvest(key: str, status: str, result: dict | None = None) -> None:
    with _dash_lock:
        if key in _harvest_status:
            _harvest_status[key]["status"] = status
            if status == "running":
                _harvest_status[key]["last_run"] = datetime.now().isoformat()
            if result is not None:
                _harvest_status[key]["last_result"] = result
                _harvest_logs.appendleft({
                    "ts": datetime.now().isoformat(),
                    "key": key,
                    "status": status,
                    "result": result
                })

def _dash_start_job(job_id: str, ticker: str, exchange: str, user_id) -> None:
    with _dash_lock:
        _active_analyses[job_id] = {
            "job_id": job_id,
            "ticker": ticker.upper(),
            "exchange": exchange,
            "user_id": user_id,
            "start_ts": datetime.now().isoformat(),
            "stage": "AI agents initializing...",
        }

def _dash_end_job(job_id: str, result: dict | None = None, error: str | None = None, killed: bool = False) -> None:
    with _dash_lock:
        job = _active_analyses.pop(job_id, None)
        if not job:
            return
        duration = (datetime.now() - datetime.fromisoformat(job["start_ts"])).total_seconds()
        entry = {**job, "end_ts": datetime.now().isoformat(), "duration_s": round(duration, 1)}
        if result:
            entry["signal"] = result.get("signal")
            entry["confidence"] = result.get("confidence_pct")
            entry["company_name"] = result.get("company_name", "")
            entry["cache_type"] = result.get("_cache_type", "FULL AI")
            entry["status"] = "completed"
        elif killed:
            entry["status"] = "disconnected"
            entry["cache_type"] = "—"
        else:
            entry["status"] = "error"
            entry["error"] = error or "unknown"
            entry["cache_type"] = "—"
        _completed_analyses.appendleft(entry)

def _dash_log_request(method: str, path: str, params: dict, status: int, duration_ms: float) -> None:
    with _dash_lock:
        _request_log.appendleft({
            "id": str(uuid.uuid4())[:8],
            "ts": datetime.now().isoformat(),
            "method": method,
            "path": path,
            "params": params,
            "status": status,
            "duration_ms": round(duration_ms),
        })


def _log_token_usage(endpoint: str, usage) -> None:
    # Handle both Anthropic (input_tokens) and OpenAI (prompt_tokens)
    inp = getattr(usage, "input_tokens", 0)
    if inp == 0:
        inp = getattr(usage, "prompt_tokens", 0)
        
    out = getattr(usage, "output_tokens", 0)
    if out == 0:
        out = getattr(usage, "completion_tokens", 0)
        
    cr = getattr(usage, "cache_read_input_tokens", 0)
    cw = getattr(usage, "cache_creation_input_tokens", 0)
    try:
        entry = {
            "ts": datetime.now().isoformat(),
            "endpoint": endpoint,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_input_tokens": cw,
            "cache_read_input_tokens": cr,
        }
        with _token_log_lock:
            with open(TOKEN_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    with _dash_lock:
        _token_stats["total_input"]      += inp
        _token_stats["total_output"]     += out
        _token_stats["total_cache_read"] += cr
        _token_stats["total_cache_write"]+= cw
        _token_stats["total_calls"]      += 1
        _token_stats["recent"].appendleft({
            "ts": datetime.now().isoformat(),
            "endpoint": endpoint,
            "input": inp, "output": out, "cache_read": cr, "cache_write": cw,
        })

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

class DataHarvestingError(Exception):
    """Raised when a market data scraping / harvest pipeline fails."""
    pass


app = FastAPI(title="Indian Stock Market Analysis API")

# ---------------------------------------------------------------------------
# CORS — env-configurable for production
# ---------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _RequestLogMiddleware(BaseHTTPMiddleware):
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
        return response

app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(CorrelationIDMiddleware)

# ---------------------------------------------------------------------------
# Financial Error Boundary Handlers
# DataHarvestingError → 503, generic Exception → 500
# ---------------------------------------------------------------------------
from fastapi import Request as _FRequest
from fastapi.responses import JSONResponse as _JSONResponse

@app.exception_handler(DataHarvestingError)
async def _data_harvesting_error_handler(_req: _FRequest, exc: DataHarvestingError):
    return _JSONResponse(
        status_code=503,
        content={"detail": f"Data harvesting service unavailable: {exc}"},
    )


# ---------------------------------------------------------------------------
# Import and register routers
# ---------------------------------------------------------------------------
from routers import auth, portfolio, market, analysis, alerts, user, dashboard, notifications, brainstorming, strategy, copilot, anomalies, correlation, nl_screener, stress_test, sector_rotation, earnings_surprise, options_strategy
from routers import harvester as harvester_router

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
app.include_router(copilot.router)
app.include_router(anomalies.router)
app.include_router(nl_screener.router)
app.include_router(stress_test.router)
app.include_router(sector_rotation.router, prefix="/api/v1")
app.include_router(earnings_surprise.router)
app.include_router(options_strategy.router)

# ---------------------------------------------------------------------------
# Static files — serve generated portfolio charts
# ---------------------------------------------------------------------------
import os as _os
_charts_dir = _os.path.join(_os.path.dirname(__file__), "charts")
_os.makedirs(_charts_dir, exist_ok=True)
app.mount("/charts", StaticFiles(directory=_charts_dir), name="charts")

# ---------------------------------------------------------------------------
# Admin Harvest Endpoints & Scheduler — imported from harvest_worker (Phase 3)
# ---------------------------------------------------------------------------
from services.harvest_worker import router as harvest_router, start_scheduler, stop_scheduler

app.include_router(harvest_router)


@app.on_event("startup")
async def _on_startup():
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
    from routers.alerts import _price_alert_poller
    import asyncio
    asyncio.create_task(_price_alert_poller())

    # Pre-warm FinBERT so first user request doesn't pay the 3-5s model load cost
    def _prewarm_finbert():
        try:
            from services.sentiment_engine import get_classifier
            get_classifier()
            logging.info("FinBERT pre-warmed successfully")
        except Exception as e:
            logging.warning(f"FinBERT pre-warm failed (non-fatal): {e}")
    threading.Thread(target=_prewarm_finbert, daemon=True).start()
    
    # Initial RAG vector ingestion at startup (always runs, regardless of scheduler)
    def _startup_ingest():
        try:
            from services.vector_store import init_store
            if not init_store():
                logging.warning("ChromaDB init failed, skipping RAG ingestion")
                return
            logging.info("Starting initial RAG ingestion...")
            from services.rag_ingestion import ingest_all
            count = ingest_all()
            logging.info("Initial RAG ingestion complete: %d chunks", count)
        except Exception as e:
            logging.warning("Initial RAG ingestion failed (non-blocking): %s", e)
    threading.Thread(target=_startup_ingest, daemon=True).start()
    
    import os
    # NOTE: `logging` is module-level (line ~124). A local `import logging` here
    # made it function-local, breaking earlier logging.* calls (UnboundLocalError).
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from services.harvest_worker import harvest_youtube_metadata, harvest_news
            from services.portfolio_snapshot import snapshot_all_users
            from services.rag_ingestion import ingest_new
            
            scheduler = AsyncIOScheduler()
            scheduler.add_job(harvest_youtube_metadata, "cron", hour=0, minute=30)
            scheduler.add_job(harvest_news, "cron", hour=1, minute=30)
            scheduler.add_job(snapshot_all_users, "cron", hour=16, minute=30)

            # Nightly RAG refresh at 2 AM
            scheduler.add_job(ingest_new, "cron", hour=2, minute=0, id="rag_ingestion")

            scheduler.start()
            logging.info("Main APScheduler started.")
        except ImportError:
            # needs pip install apscheduler
            logging.warning("apscheduler not installed, please run: pip install apscheduler. Skipping scheduler startup.")


@app.on_event("shutdown")
async def _on_shutdown():
    stop_scheduler()


@app.get("/ping")
def ping():
    """Zero-dependency liveness probe — no DB, no yfinance."""
    return {"pong": True}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


# Init DB and seed on startup
init_db()



_quick_info_cache: dict[str, tuple[float, dict]] = {}  # key -> (expiry_timestamp, data)
_QUICK_INFO_TTL = 900  # 15 minutes (extended from 5 — safe for pre/post market)

# NSE Stock Directory and ticker lookups relocated to services/nse_data_provider (Phase 4+5)
_NSE_DIRECTORY = [
    # Nifty 50 / Large Cap
    {"ticker": "RELIANCE",    "company_name": "Reliance Industries Ltd",        "sector": "Oil & Gas"},
    {"ticker": "TCS",         "company_name": "Tata Consultancy Services",       "sector": "IT"},
    {"ticker": "HDFCBANK",    "company_name": "HDFC Bank Ltd",                   "sector": "Banking"},
    {"ticker": "INFY",        "company_name": "Infosys Ltd",                     "sector": "IT"},
    {"ticker": "ICICIBANK",   "company_name": "ICICI Bank Ltd",                  "sector": "Banking"},
    {"ticker": "SBIN",        "company_name": "State Bank of India",             "sector": "Banking"},
    {"ticker": "BHARTIARTL",  "company_name": "Bharti Airtel Ltd",               "sector": "Telecom"},
    {"ticker": "KOTAKBANK",   "company_name": "Kotak Mahindra Bank",             "sector": "Banking"},
    {"ticker": "AXISBANK",    "company_name": "Axis Bank Ltd",                   "sector": "Banking"},
    {"ticker": "LT",          "company_name": "Larsen & Toubro Ltd",             "sector": "Engineering"},
    {"ticker": "HCLTECH",     "company_name": "HCL Technologies Ltd",            "sector": "IT"},
    {"ticker": "WIPRO",       "company_name": "Wipro Ltd",                       "sector": "IT"},
    {"ticker": "NTPC",        "company_name": "NTPC Ltd",                        "sector": "Power"},
    {"ticker": "POWERGRID",   "company_name": "Power Grid Corporation",          "sector": "Power"},
    {"ticker": "MARUTI",      "company_name": "Maruti Suzuki India Ltd",         "sector": "Auto"},
    {"ticker": "SUNPHARMA",   "company_name": "Sun Pharmaceutical Industries",   "sector": "Pharma"},
    {"ticker": "ONGC",        "company_name": "Oil & Natural Gas Corporation",   "sector": "Oil & Gas"},
    {"ticker": "ITC",         "company_name": "ITC Ltd",                         "sector": "FMCG"},
    {"ticker": "TITAN",       "company_name": "Titan Company Ltd",               "sector": "Consumer"},
    {"ticker": "BAJFINANCE",  "company_name": "Bajaj Finance Ltd",               "sector": "Finance"},
    {"ticker": "ASIANPAINT",  "company_name": "Asian Paints Ltd",                "sector": "Paints"},
    {"ticker": "NESTLEIND",   "company_name": "Nestle India Ltd",                "sector": "FMCG"},
    {"ticker": "HINDUNILVR",  "company_name": "Hindustan Unilever Ltd",          "sector": "FMCG"},
    {"ticker": "ULTRACEMCO",  "company_name": "UltraTech Cement Ltd",            "sector": "Cement"},
    {"ticker": "TATAMOTORS",  "company_name": "Tata Motors Ltd",                 "sector": "Auto"},
    {"ticker": "TATASTEEL",   "company_name": "Tata Steel Ltd",                  "sector": "Steel"},
    {"ticker": "M&M",         "company_name": "Mahindra & Mahindra",             "sector": "Auto"},
    {"ticker": "DRREDDY",     "company_name": "Dr Reddy's Laboratories",         "sector": "Pharma"},
    {"ticker": "CIPLA",       "company_name": "Cipla Ltd",                       "sector": "Pharma"},
    {"ticker": "BAJAJ-AUTO",  "company_name": "Bajaj Auto Ltd",                  "sector": "Auto"},
    {"ticker": "EICHERMOT",   "company_name": "Eicher Motors Ltd",               "sector": "Auto"},
    {"ticker": "INDUSINDBK",  "company_name": "IndusInd Bank Ltd",               "sector": "Banking"},
    {"ticker": "HINDALCO",    "company_name": "Hindalco Industries Ltd",         "sector": "Metals"},
    {"ticker": "JSWSTEEL",    "company_name": "JSW Steel Ltd",                   "sector": "Steel"},
    {"ticker": "BPCL",        "company_name": "Bharat Petroleum",                "sector": "Oil & Gas"},
    {"ticker": "TATACONSUM",  "company_name": "Tata Consumer Products",          "sector": "FMCG"},
    {"ticker": "HEROMOTOCO",  "company_name": "Hero MotoCorp Ltd",               "sector": "Auto"},
    {"ticker": "ADANIENT",    "company_name": "Adani Enterprises Ltd",           "sector": "Diversified"},
    {"ticker": "ADANIPOWER",  "company_name": "Adani Power Ltd",                 "sector": "Power"},
    {"ticker": "GRASIM",      "company_name": "Grasim Industries Ltd",           "sector": "Diversified"},
    {"ticker": "COALINDIA",   "company_name": "Coal India Ltd",                  "sector": "Mining"},
    {"ticker": "VEDL",        "company_name": "Vedanta Ltd",                     "sector": "Mining"},
    # Midcap / Portfolio holdings
    {"ticker": "SUZLON",      "company_name": "Suzlon Energy Ltd",               "sector": "Renewable Energy"},
    {"ticker": "HAL",         "company_name": "Hindustan Aeronautics Ltd",       "sector": "Defence"},
    {"ticker": "BEL",         "company_name": "Bharat Electronics Ltd",          "sector": "Defence"},
    {"ticker": "BHEL",        "company_name": "Bharat Heavy Electricals Ltd",    "sector": "Engineering"},
    {"ticker": "IRFC",        "company_name": "Indian Railway Finance Corp",     "sector": "Finance"},
    {"ticker": "CDSL",        "company_name": "Central Depository Services",     "sector": "Finance"},
    {"ticker": "BSE",         "company_name": "BSE Ltd",                         "sector": "Finance"},
    {"ticker": "POLYCAB",     "company_name": "Polycab India Ltd",               "sector": "Electricals"},
    {"ticker": "TATAELXSI",   "company_name": "Tata Elxsi Ltd",                  "sector": "IT"},
    {"ticker": "ZOMATO",      "company_name": "Zomato Ltd",                      "sector": "Consumer Tech"},
    {"ticker": "IRCTC",       "company_name": "Indian Railway Catering & Tourism","sector": "Travel"},
    {"ticker": "DMART",       "company_name": "Avenue Supermarts",               "sector": "Retail"},
    {"ticker": "IDEA",        "company_name": "Vodafone Idea Ltd",               "sector": "Telecom"},
    {"ticker": "ABBOTINDIA",  "company_name": "Abbott India Ltd",                "sector": "Pharma"},
    {"ticker": "AVANTEL",     "company_name": "Avantel Ltd",                     "sector": "Defence"},
    {"ticker": "APOLLO",      "company_name": "Apollo Microsystems Ltd",         "sector": "Defence"},
    {"ticker": "BGRENERGY",   "company_name": "BGR Energy Systems Ltd",          "sector": "Engineering"},
    {"ticker": "MCLEODRUSS",  "company_name": "McLeod Russel India Ltd",         "sector": "Tea"},
    {"ticker": "JITFINFRA",   "company_name": "JITF Infralogistics Ltd",         "sector": "Logistics"},
    {"ticker": "GAUDIUMIVF",  "company_name": "Gaudium IVF and Women Health",    "sector": "Healthcare"},
    {"ticker": "OMPOWER",     "company_name": "OM Power Trans Ltd",              "sector": "Power"},
    # Finance & Markets
    {"ticker": "RECLTD",      "company_name": "REC Ltd",                         "sector": "Finance"},
    {"ticker": "PFC",         "company_name": "Power Finance Corporation",       "sector": "Finance"},
    {"ticker": "LICI",        "company_name": "Life Insurance Corporation",      "sector": "Finance"},
    {"ticker": "JIOFIN",      "company_name": "Jio Financial Services",          "sector": "Finance"},
    {"ticker": "SBICARD",     "company_name": "SBI Cards and Payment Services",  "sector": "Finance"},
    {"ticker": "CHOLAFIN",    "company_name": "Cholamandalam Investment",        "sector": "Finance"},
    {"ticker": "MUTHOOTFIN",  "company_name": "Muthoot Finance Ltd",             "sector": "Finance"},
    {"ticker": "MANAPPURAM",  "company_name": "Manappuram Finance",              "sector": "Finance"},
    {"ticker": "CAMS",        "company_name": "Computer Age Management Services","sector": "Finance"},
    {"ticker": "MCX",         "company_name": "Multi Commodity Exchange",        "sector": "Finance"},
    {"ticker": "IEX",         "company_name": "Indian Energy Exchange",          "sector": "Finance"},
    {"ticker": "ANGELONE",    "company_name": "Angel One Ltd",                   "sector": "Finance"},
    {"ticker": "MOTILALOFS",  "company_name": "Motilal Oswal Financial",         "sector": "Finance"},
    {"ticker": "360ONE",      "company_name": "360 ONE WAM",                     "sector": "Finance"},
    {"ticker": "KFINTECH",    "company_name": "KFin Technologies",               "sector": "Finance"},
    {"ticker": "ABCAPITAL",   "company_name": "Aditya Birla Capital",            "sector": "Finance"},
    {"ticker": "L&TFH",       "company_name": "L&T Finance Holdings",            "sector": "Finance"},
    {"ticker": "EDELWEISS",   "company_name": "Edelweiss Financial",             "sector": "Finance"},
    {"ticker": "PNBHOUSING",  "company_name": "PNB Housing Finance",             "sector": "Finance"},
    {"ticker": "LICHSGFIN",   "company_name": "LIC Housing Finance",             "sector": "Finance"},
    {"ticker": "AAVAS",       "company_name": "Aavas Financiers",                "sector": "Finance"},
    {"ticker": "SUNDARMFIN",  "company_name": "Sundaram Finance",                "sector": "Finance"},
    {"ticker": "CANFINHOME",  "company_name": "Can Fin Homes",                   "sector": "Finance"},
    {"ticker": "CREDITACC",   "company_name": "CreditAccess Grameen",            "sector": "Finance"},
    {"ticker": "FUSION",      "company_name": "Fusion Micro Finance",            "sector": "Finance"},
    {"ticker": "HUDCO",       "company_name": "HUDCO",                           "sector": "Finance"},
    {"ticker": "IREDA",       "company_name": "IREDA Ltd",                       "sector": "Finance"},
    # IT
    {"ticker": "LTIM",        "company_name": "LTIMindtree",                     "sector": "IT"},
    {"ticker": "LTTS",        "company_name": "L&T Technology Services",         "sector": "IT"},
    {"ticker": "MPHASIS",     "company_name": "Mphasis Ltd",                     "sector": "IT"},
    {"ticker": "PERSISTENT",  "company_name": "Persistent Systems",              "sector": "IT"},
    {"ticker": "COFORGE",     "company_name": "Coforge Ltd",                     "sector": "IT"},
    {"ticker": "TECHM",       "company_name": "Tech Mahindra Ltd",               "sector": "IT"},
    {"ticker": "AFFLE",       "company_name": "Affle India",                     "sector": "Consumer Tech"},
    {"ticker": "INDIAMART",   "company_name": "IndiaMART InterMESH",             "sector": "IT"},
    {"ticker": "CEINFO",      "company_name": "CE Info Systems (MapMyIndia)",    "sector": "IT"},
    {"ticker": "NAZARA",      "company_name": "Nazara Technologies",             "sector": "Consumer Tech"},
    {"ticker": "TEJASNET",    "company_name": "Tejas Networks",                  "sector": "Telecom"},
    # Banking (PSU & Private)
    {"ticker": "PNB",         "company_name": "Punjab National Bank",            "sector": "Banking"},
    {"ticker": "CANBK",       "company_name": "Canara Bank",                     "sector": "Banking"},
    {"ticker": "BANKBARODA",  "company_name": "Bank of Baroda",                  "sector": "Banking"},
    {"ticker": "UNIONBANK",   "company_name": "Union Bank of India",             "sector": "Banking"},
    {"ticker": "BANKINDIA",   "company_name": "Bank of India",                   "sector": "Banking"},
    {"ticker": "INDIANB",     "company_name": "Indian Bank",                     "sector": "Banking"},
    {"ticker": "IDFCFIRSTB",  "company_name": "IDFC First Bank",                 "sector": "Banking"},
    {"ticker": "YESBANK",     "company_name": "Yes Bank Ltd",                    "sector": "Banking"},
    {"ticker": "FEDERALBNK",  "company_name": "Federal Bank Ltd",                "sector": "Banking"},
    {"ticker": "AUBANK",      "company_name": "AU Small Finance Bank",           "sector": "Banking"},
    {"ticker": "BANDHANBNK",  "company_name": "Bandhan Bank Ltd",                "sector": "Banking"},
    {"ticker": "EQUITASBNK",  "company_name": "Equitas Small Finance Bank",      "sector": "Banking"},
    {"ticker": "UJJIVANSFB",  "company_name": "Ujjivan Small Finance Bank",      "sector": "Banking"},
    {"ticker": "IDBI",        "company_name": "IDBI Bank Ltd",                   "sector": "Banking"},
    {"ticker": "RBLBANK",     "company_name": "RBL Bank Ltd",                    "sector": "Banking"},
    {"ticker": "KARURVYSYA",  "company_name": "Karur Vysya Bank",                "sector": "Banking"},
    {"ticker": "CUB",         "company_name": "City Union Bank",                 "sector": "Banking"},
    # Pharma
    {"ticker": "LUPIN",       "company_name": "Lupin Ltd",                       "sector": "Pharma"},
    {"ticker": "BIOCON",      "company_name": "Biocon Ltd",                      "sector": "Pharma"},
    {"ticker": "AUROPHARMA",  "company_name": "Aurobindo Pharma",                "sector": "Pharma"},
    {"ticker": "DIVISLAB",    "company_name": "Divis Laboratories",              "sector": "Pharma"},
    {"ticker": "TORNTPHARM",  "company_name": "Torrent Pharma",                  "sector": "Pharma"},
    {"ticker": "ZYDUSLIFE",   "company_name": "Zydus Lifesciences",              "sector": "Pharma"},
    {"ticker": "ALKEM",       "company_name": "Alkem Laboratories",              "sector": "Pharma"},
    {"ticker": "LAURUSLABS",  "company_name": "Laurus Labs Ltd",                 "sector": "Pharma"},
    {"ticker": "SYNGENE",     "company_name": "Syngene International",           "sector": "Pharma"},
    {"ticker": "GLENMARK",    "company_name": "Glenmark Pharma",                 "sector": "Pharma"},
    {"ticker": "APLLTD",      "company_name": "Alembic Pharma",                  "sector": "Pharma"},
    {"ticker": "NATCOPHARM",  "company_name": "Natco Pharma",                    "sector": "Pharma"},
    {"ticker": "PFIZER",      "company_name": "Pfizer Ltd",                      "sector": "Pharma"},
    {"ticker": "GLAXO",       "company_name": "GlaxoSmithKline Pharma",          "sector": "Pharma"},
    {"ticker": "GRANULES",    "company_name": "Granules India",                  "sector": "Pharma"},
    # Healthcare
    {"ticker": "APOLLOHOSP",  "company_name": "Apollo Hospitals",                "sector": "Healthcare"},
    {"ticker": "MAXHEALTH",   "company_name": "Max Healthcare",                  "sector": "Healthcare"},
    {"ticker": "FORTIS",      "company_name": "Fortis Healthcare",               "sector": "Healthcare"},
    {"ticker": "KIMS",        "company_name": "Krishna Institute of Medical Sciences","sector": "Healthcare"},
    {"ticker": "RAINBOW",     "company_name": "Rainbow Childrens Medicare",      "sector": "Healthcare"},
    {"ticker": "MEDANTA",     "company_name": "Global Health (Medanta)",         "sector": "Healthcare"},
    {"ticker": "POLYMED",     "company_name": "Poly Medicure Ltd",               "sector": "Healthcare"},
    # Power & Energy
    {"ticker": "NHPC",        "company_name": "NHPC Ltd",                        "sector": "Power"},
    {"ticker": "JSWENERGY",   "company_name": "JSW Energy Ltd",                  "sector": "Power"},
    {"ticker": "TATAPOWER",   "company_name": "Tata Power Company",              "sector": "Power"},
    {"ticker": "TORNTPOWER",  "company_name": "Torrent Power Ltd",               "sector": "Power"},
    {"ticker": "CESC",        "company_name": "CESC Ltd",                        "sector": "Power"},
    {"ticker": "ADANIGREEN",  "company_name": "Adani Green Energy",              "sector": "Renewable Energy"},
    {"ticker": "BORORENEW",   "company_name": "Borosil Renewables",              "sector": "Renewable Energy"},
    {"ticker": "KPIGREEN",    "company_name": "KPI Green Energy",                "sector": "Renewable Energy"},
    {"ticker": "SWSOLAR",     "company_name": "Sterling & Wilson",               "sector": "Renewable Energy"},
    # Oil & Gas
    {"ticker": "HPCL",        "company_name": "Hindustan Petroleum",             "sector": "Oil & Gas"},
    {"ticker": "IOC",         "company_name": "Indian Oil Corp",                 "sector": "Oil & Gas"},
    {"ticker": "OIL",         "company_name": "Oil India Ltd",                   "sector": "Oil & Gas"},
    {"ticker": "GAIL",        "company_name": "GAIL (India) Ltd",                "sector": "Gas"},
    {"ticker": "PETRONET",    "company_name": "Petronet LNG Ltd",                "sector": "Gas"},
    {"ticker": "IGL",         "company_name": "Indraprastha Gas Ltd",            "sector": "Gas"},
    {"ticker": "MGL",         "company_name": "Mahanagar Gas Ltd",               "sector": "Gas"},
    {"ticker": "GUJGASLTD",   "company_name": "Gujarat Gas Ltd",                 "sector": "Gas"},
    # Defence
    {"ticker": "BEML",        "company_name": "BEML Limited",                    "sector": "Defence"},
    {"ticker": "BDL",         "company_name": "Bharat Dynamics Ltd",             "sector": "Defence"},
    {"ticker": "MAZDOCK",     "company_name": "Mazagon Dock Shipbuilders",       "sector": "Defence"},
    {"ticker": "GRSE",        "company_name": "Garden Reach Shipbuilders",       "sector": "Defence"},
    {"ticker": "COCHINSHIP",  "company_name": "Cochin Shipyard Ltd",             "sector": "Defence"},
    {"ticker": "DATAPATTNS",  "company_name": "Data Patterns",                   "sector": "Defence"},
    {"ticker": "MTARTECH",    "company_name": "MTAR Technologies",               "sector": "Defence"},
    {"ticker": "PARAS",       "company_name": "Paras Defence",                   "sector": "Defence"},
    {"ticker": "ZENTEC",      "company_name": "Zen Technologies",                "sector": "Defence"},
    # Infrastructure
    {"ticker": "RVNL",        "company_name": "Rail Vikas Nigam Ltd",            "sector": "Infrastructure"},
    {"ticker": "IRCON",       "company_name": "Ircon International",             "sector": "Infrastructure"},
    {"ticker": "NBCC",        "company_name": "NBCC (India) Ltd",                "sector": "Infrastructure"},
    {"ticker": "GRINFRA",     "company_name": "G R Infraprojects",               "sector": "Infrastructure"},
    {"ticker": "ASHOKA",      "company_name": "Ashoka Buildcon",                 "sector": "Infrastructure"},
    {"ticker": "KNRCON",      "company_name": "KNR Constructions",               "sector": "Infrastructure"},
    {"ticker": "PNCINFRA",    "company_name": "PNC Infratech Ltd",               "sector": "Infrastructure"},
    # Chemicals
    {"ticker": "PIDILITIND",  "company_name": "Pidilite Industries",             "sector": "Chemicals"},
    {"ticker": "SRF",         "company_name": "SRF Ltd",                         "sector": "Chemicals"},
    {"ticker": "UPL",         "company_name": "UPL Ltd",                         "sector": "Chemicals"},
    {"ticker": "AARTIIND",    "company_name": "Aarti Industries Ltd",            "sector": "Chemicals"},
    {"ticker": "DEEPAKNTR",   "company_name": "Deepak Nitrite Ltd",              "sector": "Chemicals"},
    {"ticker": "TATACHEM",    "company_name": "Tata Chemicals Ltd",              "sector": "Chemicals"},
    {"ticker": "VINATIORGA",  "company_name": "Vinati Organics",                 "sector": "Chemicals"},
    {"ticker": "FINEORG",     "company_name": "Fine Organic Industries",         "sector": "Chemicals"},
    {"ticker": "GALAXYSURF",  "company_name": "Galaxy Surfactants",              "sector": "Chemicals"},
    {"ticker": "CLEAN",       "company_name": "Clean Science & Tech",            "sector": "Chemicals"},
    {"ticker": "ROSSARI",     "company_name": "Rossari Biotech",                 "sector": "Chemicals"},
    {"ticker": "AETHER",      "company_name": "Aether Industries",               "sector": "Chemicals"},
    # Consumer / FMCG / Retail
    {"ticker": "VBL",         "company_name": "Varun Beverages Ltd",             "sector": "FMCG"},
    {"ticker": "BRITANNIA",   "company_name": "Britannia Industries",            "sector": "FMCG"},
    {"ticker": "DABUR",       "company_name": "Dabur India Ltd",                 "sector": "FMCG"},
    {"ticker": "MARICO",      "company_name": "Marico Ltd",                      "sector": "FMCG"},
    {"ticker": "COLPAL",      "company_name": "Colgate-Palmolive India",         "sector": "FMCG"},
    {"ticker": "GODREJCP",    "company_name": "Godrej Consumer Products",        "sector": "FMCG"},
    {"ticker": "AWL",         "company_name": "Adani Wilmar",                    "sector": "FMCG"},
    {"ticker": "PATANJALI",   "company_name": "Patanjali Foods",                 "sector": "FMCG"},
    {"ticker": "BIKAJI",      "company_name": "Bikaji Foods",                    "sector": "FMCG"},
    {"ticker": "TRENT",       "company_name": "Trent Ltd",                       "sector": "Retail"},
    {"ticker": "KALYANKJIL",  "company_name": "Kalyan Jewellers",                "sector": "Consumer"},
    {"ticker": "TITAN",       "company_name": "Titan Company Ltd",               "sector": "Consumer"},
    {"ticker": "MANYAVAR",    "company_name": "Vedant Fashions",                 "sector": "Retail"},
    {"ticker": "METROBRAND",  "company_name": "Metro Brands",                    "sector": "Retail"},
    # Auto
    {"ticker": "ESCORTS",     "company_name": "Escorts Kubota Ltd",              "sector": "Auto"},
    {"ticker": "ASHOKLEY",    "company_name": "Ashok Leyland Ltd",               "sector": "Auto"},
    {"ticker": "TVSMOTOR",    "company_name": "TVS Motor Company",               "sector": "Auto"},
    {"ticker": "MRF",         "company_name": "MRF Ltd",                         "sector": "Tyres"},
    {"ticker": "APOLLOTYRE",  "company_name": "Apollo Tyres Ltd",                "sector": "Tyres"},
    {"ticker": "BALKRISIND",  "company_name": "Balkrishna Industries",           "sector": "Tyres"},
    {"ticker": "CEATLTD",     "company_name": "CEAT Ltd",                        "sector": "Tyres"},
    {"ticker": "BHARATFORG",  "company_name": "Bharat Forge Ltd",                "sector": "Auto Ancillary"},
    {"ticker": "BOSCHLTD",    "company_name": "Bosch Ltd",                       "sector": "Auto Ancillary"},
    {"ticker": "MOTHERSON",   "company_name": "Samvardhana Motherson",           "sector": "Auto Ancillary"},
    {"ticker": "SONACOMS",    "company_name": "Sona BLW Precision",              "sector": "Auto Ancillary"},
    {"ticker": "UNOMINDA",    "company_name": "Uno Minda Ltd",                   "sector": "Auto Ancillary"},
    # Real Estate
    {"ticker": "DLF",         "company_name": "DLF Ltd",                         "sector": "Real Estate"},
    {"ticker": "GODREJPROP",  "company_name": "Godrej Properties",               "sector": "Real Estate"},
    {"ticker": "OBEROIRLTY",  "company_name": "Oberoi Realty Ltd",               "sector": "Real Estate"},
    {"ticker": "LODHA",       "company_name": "Macrotech Developers",            "sector": "Real Estate"},
    {"ticker": "PRESTIGE",    "company_name": "Prestige Estate",                 "sector": "Real Estate"},
    {"ticker": "PHOENIXLTD",  "company_name": "Phoenix Mills Ltd",               "sector": "Real Estate"},
    {"ticker": "BRIGADE",     "company_name": "Brigade Enterprises",             "sector": "Real Estate"},
    # Consumer Tech / Startups
    {"ticker": "NYKAA",       "company_name": "FSN E-Commerce (Nykaa)",          "sector": "Consumer Tech"},
    {"ticker": "PAYTM",       "company_name": "One 97 Communications",           "sector": "Consumer Tech"},
    {"ticker": "POLICYBZR",   "company_name": "PB Fintech (PolicyBazaar)",       "sector": "Consumer Tech"},
    {"ticker": "DELHIVERY",   "company_name": "Delhivery Ltd",                   "sector": "Logistics"},
    {"ticker": "ZEEL",        "company_name": "Zee Entertainment",               "sector": "Media"},
    {"ticker": "SUNTV",       "company_name": "Sun TV Network Ltd",              "sector": "Media"},
    # Cement
    {"ticker": "SHREECEM",    "company_name": "Shree Cement Ltd",                "sector": "Cement"},
    {"ticker": "ACC",         "company_name": "ACC Ltd",                         "sector": "Cement"},
    {"ticker": "AMBUJACEM",   "company_name": "Ambuja Cements Ltd",              "sector": "Cement"},
    {"ticker": "DALBHARAT",   "company_name": "Dalmia Bharat Ltd",               "sector": "Cement"},
    {"ticker": "JKCEMENT",    "company_name": "JK Cement Ltd",                   "sector": "Cement"},
    {"ticker": "RAMCOCEM",    "company_name": "Ramco Cements",                   "sector": "Cement"},
    # Steel / Metals / Mining
    {"ticker": "SAIL",        "company_name": "Steel Authority of India",        "sector": "Steel"},
    {"ticker": "HINDZINC",    "company_name": "Hindustan Zinc Ltd",              "sector": "Metals"},
    {"ticker": "NMDC",        "company_name": "NMDC Ltd",                        "sector": "Mining"},
    # Consumer Durables
    {"ticker": "HAVELLS",     "company_name": "Havells India Ltd",               "sector": "Consumer Durables"},
    {"ticker": "VOLTAS",      "company_name": "Voltas Ltd",                      "sector": "Consumer Durables"},
    {"ticker": "DIXON",       "company_name": "Dixon Technologies",              "sector": "Consumer Durables"},
    {"ticker": "BLUESTARCO",  "company_name": "Blue Star Ltd",                   "sector": "Consumer Durables"},
    {"ticker": "WHIRLPOOL",   "company_name": "Whirlpool of India",              "sector": "Consumer Durables"},
    # Hotels
    {"ticker": "INDHOTEL",    "company_name": "Indian Hotels Co Ltd",            "sector": "Hotels"},
    {"ticker": "EIHOTEL",     "company_name": "EIH Ltd (Oberoi Hotels)",         "sector": "Hotels"},
    {"ticker": "LEMONTREE",   "company_name": "Lemon Tree Hotels",               "sector": "Hotels"},
    # Fertilizers
    {"ticker": "COROMANDEL",  "company_name": "Coromandel International",        "sector": "Fertilizers"},
    {"ticker": "CHAMBLFERT",  "company_name": "Chambal Fertilizers",             "sector": "Fertilizers"},
    {"ticker": "DEEPAKFERT",  "company_name": "Deepak Fertilisers",              "sector": "Fertilizers"},
    # Additional prominent names
    {"ticker": "NAUKRI",      "company_name": "Info Edge (Naukri)",              "sector": "IT"},
    {"ticker": "ZOMATO",      "company_name": "Zomato Ltd",                      "sector": "Consumer Tech"},
    {"ticker": "SWIGGY",      "company_name": "Bundl Technologies (Swiggy)",     "sector": "Consumer Tech"},
    {"ticker": "IXIGO",       "company_name": "Le Travenues Technology (ixigo)", "sector": "Consumer Tech"},
    {"ticker": "KAYNES",      "company_name": "Kaynes Technology",               "sector": "Engineering"},
    {"ticker": "SYRMA",       "company_name": "Syrma SGS Technology",            "sector": "Engineering"},
    {"ticker": "AVALON",      "company_name": "Avalon Technologies",             "sector": "Engineering"},
    {"ticker": "DOMS",        "company_name": "DOMS Industries",                 "sector": "Consumer"},
    {"ticker": "VARUN",       "company_name": "Varun Beverages Ltd",             "sector": "FMCG"},
    {"ticker": "PVRINOX",     "company_name": "PVR INOX Ltd",                    "sector": "Media"},
    {"ticker": "INOXWIND",    "company_name": "Inox Wind Ltd",                   "sector": "Renewable Energy"},
    {"ticker": "WAAREEENER",  "company_name": "Waaree Energies",                 "sector": "Renewable Energy"},
    {"ticker": "PREMIERENE",  "company_name": "Premier Energies",                "sector": "Renewable Energy"},
]

# Pre-process for fast search: lowercase index
_NSE_DIR_INDEX = [
    {
        "ticker": e["ticker"],
        "company_name": e["company_name"],
        "sector": e["sector"],
        "exchange": "NSE",
        "_t": e["ticker"].lower(),
        "_n": e["company_name"].lower(),
        "_s": e["sector"].lower(),
    }
    for e in _NSE_DIRECTORY
]

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
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_endpoint():
    """Lightweight health check for iOS client.
    Swift checkHealth() only inspects HTTP status code — this returns
    a minimal 200 to avoid unnecessary DB/disk/yfinance overhead.
    For rich diagnostics, use GET /health/live (DB check) or
    the admin liveness endpoint.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Liveness probe — Section 16
# Zero-latency, dependency-free. Used by Docker HEALTHCHECK and k8s liveness.
# Confirms DB is reachable; does NOT call yfinance or any external service.
# ---------------------------------------------------------------------------

@app.get("/health/live")
async def liveness_probe():
    """
    Lightweight liveness probe for container orchestration.
    Returns 200 {"status": "alive"} if the DB connection is healthy.
    Returns 503 if the DB is unreachable.
    """
    try:
        with get_session() as _session:
            from sqlalchemy import text as _text
            _session.execute(_text("SELECT 1"))
        return {"status": "alive", "db": True, "ts": datetime.utcnow().isoformat()}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {exc}",
        )


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
// ─── Charts ─────────────────────────────────────────────────
let chartAlloc=null, chartSigs=null, chartVal=null, chartPnl=null, chartNw=null;

function destroyChart(c){if(c){c.destroy();return null;}return null;}

const expandedIds=new Set();
const activeTabs2={};
let currentUserData=null;
let currentUserTab='portfolio';

// ─── Formatting ──────────────────────────────────────────────
function fmt(n){if(n==null)return'-';if(n>=1e9)return(n/1e9).toFixed(2)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return''+n}
function fmtINR(n){if(n==null||isNaN(n))return'-';const abs=Math.abs(n);let s;if(abs>=1e7)s=(n/1e7).toFixed(2)+' Cr';else if(abs>=1e5)s=(n/1e5).toFixed(2)+' L';else s=n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',');return(n<0?'-₹':'₹')+s.replace('-','')}
function fmtCost(c){if(c==null)return'$-.--';return'$'+c.toFixed(4)}
function ts(iso){if(!iso)return'-';return new Date(iso).toLocaleTimeString('en-IN',{hour12:false})}
function dts(iso){if(!iso)return'-';const d=new Date(iso);return d.toLocaleDateString('en-IN')+' '+d.toLocaleTimeString('en-IN',{hour12:false})}
function ela(iso){if(!iso)return'';const s=Math.floor((Date.now()-new Date(iso))/1000);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';return Math.floor(s/3600)+'h'}
function sig(s){if(!s)return'-';const u=s.toUpperCase();if(u.includes('BUY')||u==='STRONG_BUY'||u==='BULL')return`<span class="badge bull">${s}</span>`;if(u.includes('SELL')||u==='STRONG_SELL'||u==='BEAR')return`<span class="badge bear">${s}</span>`;return`<span class="badge hold">${s}</span>`}
function ctype(t){if(!t)return'-';const u=(t||'').toUpperCase();if(u==='CACHE HIT')return`<span class="badge cache">CACHE</span>`;if(u==='SMART CACHE')return`<span class="badge smart">SMART</span>`;if(u==='FULL AI')return`<span class="badge full">FULL AI</span>`;return`<span class="badge hold">${t}</span>`}
function stbadge(s){if(!s)return'-';const l=s.toLowerCase();if(l==='completed')return`<span class="badge ok">&#x2713; done</span>`;if(l==='error')return`<span class="badge err">&#x2717; error</span>`;return`<span class="badge hold">${s}</span>`}
function mbadge(m){return`<span class="badge m${m||'GET'}">${m}</span>`}
function hbadge(c){if(!c)return'-';const cls=c<300?'ok':c<400?'cache':'err';return`<span class="badge ${cls}">${c}</span>`}
function fmtParams(p){if(!p||!Object.keys(p).length)return'';const s=JSON.stringify(p).replace(/[{}"]/g,'');return s.length>40?s.slice(0,40)+'...':s}
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
    const body=hasErrs?errs.map(e=>`<div class="feat-err-item"><div class="feat-err-path">${e.path||'-'}</div><div class="feat-err-meta">${hbadge(e.status)} &bull; ${ts(e.ts)}</div></div>`).join(''):`<div class="feat-clean-msg">&#x2714; No errors</div>`;
    return`<div class="feature-card ${hasErrs?'has-errors':'clean'}"><div class="feature-header"><span class="feature-name">${icon} ${name}</span><div class="feat-status-dot"></div></div><div class="feature-body">${body}</div></div>`;
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
    return`<div class="stat-tile tile-dark"><div class="val ${color}">${val}</div><div class="lbl">${name.toUpperCase()}</div><div class="ts" style="margin-top:4px">${h.last_run?ts(h.last_run):'Never'}</div></div>`;
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
  const r=await fetch('/api/v1/admin/'+ep[type],{method:'POST',headers:{'Authorization':'Bearer admin'}});
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
    const r=await fetch('/dashboard-user-data?user_id='+userId,{headers:{'Authorization':'Bearer admin'}});
    const d=await r.json();
    if(d.error){document.getElementById('user-stat-chips').innerHTML='<span class="badge err">'+d.error+'</span>';return;}
    currentUserData=d;
    // Stat chips
    const u=d.user||{};
    const ps=d.portfolio_summary||{};
    const acc=d.accuracy||{};
    document.getElementById('user-stat-chips').innerHTML=`
      <div class="user-stat-chip">&#x1F464; <span class="chip-val">${u.display_name||u.username}</span></div>
      <div class="user-stat-chip">Holdings: <span class="chip-val">${ps.holdings_count||0}</span></div>
      <div class="user-stat-chip">Invested: <span class="chip-val">${fmtINR(ps.total_invested||0)}</span></div>
      <div class="user-stat-chip">Analyses: <span class="chip-val">${(d.analyses||[]).length}</span></div>
      <div class="user-stat-chip">Accuracy: <span class="chip-val">${acc.accuracy_pct!=null?acc.accuracy_pct+'%':'N/A'}</span></div>
      <div class="user-stat-chip">Joined: <span class="chip-val">${u.created_at?u.created_at.slice(0,10):'-'}</span></div>
    `;
    renderUserTab(d, currentUserTab);
  }catch(e){document.getElementById('user-stat-chips').innerHTML='<span class="badge err">Error: '+e.message+'</span>';}
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
    <td style="font-weight:700;color:#f0f6fc">${r.ticker}</td>
    <td style="color:#8b949e;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.company_name}</td>
    <td>${r.shares}</td>
    <td>₹${r.buy_price.toLocaleString('en-IN',{minimumFractionDigits:2})}</td>
    <td style="color:#c9a84c;font-weight:700">${fmtINR(r.invested)}</td>
    <td><span class="badge hold">${r.group_name}</span></td>
    <td style="color:#6e7681;font-size:10px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.notes||'—'}</td>
    <td class="ts">${r.created_at?r.created_at.slice(0,10):'-'}</td>
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
          <div class="report-ticker">${a.ticker} ${sig(a.signal)}</div>
          <div class="report-company">${a.company_name||''}</div>
        </div>
        <div class="report-meta">
          ${correctBadge}<br>
          Conf: <span style="color:#c9a84c">${a.confidence_pct!=null?a.confidence_pct+'%':'-'}</span><br>
          Price: <span style="color:#f0f6fc">${a.current_price_inr!=null?fmtINR(a.current_price_inr):'-'}</span><br>
          <span class="ts">${a.created_at?a.created_at.slice(0,10):'-'}</span>
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
          <ul class="report-list">${bull.length?bull.map(b=>`<li>${b}</li>`).join(''):'<li style="color:#484f58">No bull case</li>'}</ul>
          <h4 style="margin-top:10px">&#x1F514; Key Risks</h4>
          <ul class="report-list">${risks.length?risks.map(r=>`<li>${r}</li>`).join(''):'<li style="color:#484f58">No risks</li>'}</ul>
        </div>
        <div class="report-col">
          <h4>&#x1F534; Bear Case</h4>
          <ul class="report-list">${bear.length?bear.map(b=>`<li>${b}</li>`).join(''):'<li style="color:#484f58">No bear case</li>'}</ul>
          <h4 style="margin-top:10px">&#x1F4CA; Key Factors</h4>
          <div class="key-factors">
            ${Object.entries(kf).slice(0,6).map(([k,v])=>`<div class="kf-item"><div class="kf-label">${k.replace(/_/g,' ')}</div><div class="kf-val">${(v||'').slice(0,60)}</div></div>`).join('')}
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
    <td class="ts">${v.snapshot_date}</td>
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
      <span style="font-weight:700;color:#f0f6fc">${a.ticker}</span>
      <span class="ts" style="margin-left:8px">${a.created_at?a.created_at.slice(0,10):'-'}</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#c9a84c">₹${a.target_price.toLocaleString('en-IN')}</span>
      <span class="badge ${a.direction==='above'?'bull':'bear'}">${a.direction?.toUpperCase()}</span>
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
        <span style="font-weight:700;color:#f0f6fc">${j.ticker}</span>
        ${j.company_name?`<span class="ts" style="margin-left:6px">${j.company_name}</span>`:''}
        <span class="badge ${j.action==='BUY'?'bull':j.action==='SELL'?'bear':'hold'}" style="margin-left:8px">${j.action}</span>
        ${j.mood?`<span class="badge hold" style="margin-left:4px">${j.mood}</span>`:''}
      </div>
      <div class="ts">${j.created_at?j.created_at.slice(0,10):'-'}</div>
    </div>
    <div style="font-size:11px;color:#8b949e;margin-bottom:4px">&#x1F4B0; Price at time: <span style="color:#c9a84c">₹${j.price_at_time.toLocaleString('en-IN')}</span></div>
    <div style="font-size:11px;color:#8b949e"><strong style="color:#6e7681">Reason:</strong> ${j.reason_text||'—'}</div>
    ${j.outcome_text?`<div style="font-size:11px;color:#6e7681;margin-top:4px;padding-top:4px;border-top:1px solid #21262d"><strong>Outcome:</strong> ${j.outcome_text}</div>`:''}
  </div>`).join('');
}

// ─── Net Worth ───────────────────────────────────────────────
function renderNetWorth(d){
  const ledger=d.net_worth_ledger||[];
  chartNw=destroyChart(chartNw);
  const table=document.getElementById('networth-table');
  table.innerHTML=ledger.length===0?'<tr><td colspan="7" class="empty">No net worth data</td></tr>':ledger.map(n=>`<tr>
    <td class="ts">${n.snapshot_date}</td>
    <td style="color:#c9a84c;font-weight:700">${fmtINR(n.total_value_inr)}</td>
    <td class="${pnlClass(n.daily_delta_inr||0)}">${n.daily_delta_inr!=null?fmtINR(n.daily_delta_inr):'-'}</td>
    <td class="${pnlClass(n.daily_delta_pct||0)}">${n.daily_delta_pct!=null?n.daily_delta_pct.toFixed(2)+'%':'-'}</td>
    <td style="color:#6e7681">${n.peak_value_inr!=null?fmtINR(n.peak_value_inr):'-'}</td>
    <td>${n.top_gainer_ticker?`<span class="pnl-pos">${n.top_gainer_ticker} +${n.top_gainer_pct?.toFixed(1)}%</span>`:'-'}</td>
    <td>${n.top_loser_ticker?`<span class="pnl-neg">${n.top_loser_ticker} ${n.top_loser_pct?.toFixed(1)}%</span>`:'-'}</td>
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
    const r=await fetch('/dashboard-data',{headers:{'Authorization':'Bearer admin'}});
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
    document.getElementById('ab').innerHTML=active.length===0?'<div class="empty">No active analyses</div>':active.map(a=>`<div class="analysis-item active"><div style="display:flex;justify-content:space-between;align-items:center"><span class="a-ticker">${a.ticker}</span><span class="ts">${ts(a.start_ts)}</span></div><div class="a-meta">${a.exchange||'NSE'} &bull; User ${a.user_id||'N/A'} &bull; running ${ela(a.start_ts)}</div><div class="a-stage"><span class="s-dot"></span>${a.stage||'Processing...'}</div></div>`).join('');

    // Recent analyses
    const an=d.recent_analyses||[];
    document.getElementById('anc').textContent=an.length+' shown';
    document.getElementById('at').innerHTML=an.length===0?'<tr><td colspan="6" class="empty">No activity</td></tr>':an.slice(0,15).map(a=>`<tr><td class="ts">${ts(a.start_ts||a.ts)}</td><td style="font-weight:700;color:#f0f6fc">${a.ticker}</td><td>${ctype(a.cache_type)}</td><td>${sig(a.signal)}</td><td class="ts">${a.duration_s!=null?a.duration_s+'s':'-'}</td><td>${stbadge(a.status)}</td></tr>`).join('');

    // News / videos (overview & harvesters tabs)
    const lnews=d.latest_news||[];
    document.getElementById('lnc').textContent=lnews.length+' recent';
    const newsHtml=lnews.length===0?'<tr><td colspan="4" class="empty">No news</td></tr>':lnews.map(n=>`<tr><td class="ts">${ts(n.ts)}</td><td style="font-weight:700;color:#f0f6fc">${n.ticker||'—'}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${n.red_flag?'<span class="badge err">&#x1F6A9;</span> ':''}${n.headline}</td><td>${n.sentiment?`<span class="badge ${n.sentiment.toLowerCase()}">${n.sentiment}</span>`:'—'}</td></tr>`).join('');
    document.getElementById('lnt').innerHTML=newsHtml;
    document.getElementById('lnt2').innerHTML=newsHtml;

    const lvideos=d.latest_videos||[];
    document.getElementById('lvc').textContent=lvideos.length+' recent';
    const vidHtml=lvideos.length===0?'<tr><td colspan="4" class="empty">No videos</td></tr>':lvideos.map(v=>`<tr><td class="ts">${ts(v.ts)}</td><td style="font-weight:700;color:#f0f6fc">${v.ticker||'—'}</td><td style="color:#bc8cff">${v.channel}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${v.title}</td></tr>`).join('');
    document.getElementById('lvt').innerHTML=vidHtml;
    document.getElementById('lvt2').innerHTML=vidHtml;

    // Harvesters
    renderHarvestStatus(d.harvest_status);
    const hlogs=d.harvest_logs||[];
    document.getElementById('hrc').textContent=hlogs.length+' logged';
    document.getElementById('hrt').innerHTML=hlogs.length===0?'<tr><td colspan="3" class="empty">No logs</td></tr>':hlogs.map(l=>`<tr><td class="ts">${ts(l.ts)}</td><td style="font-weight:700;color:#c9a84c">${l.key.toUpperCase()}</td><td style="font-size:10px;color:#8b949e;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${JSON.stringify(l.result)}</td></tr>`).join('');

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
    document.getElementById('tc').textContent=(tok.total_calls||0)+' calls this session';
    const cl2=tok.recent||[];
    document.getElementById('clc').textContent=cl2.length+' recent';
    document.getElementById('ct').innerHTML=cl2.length===0?'<tr><td colspan="6" class="empty">No AI calls</td></tr>':cl2.map(c=>`<tr><td class="ts">${ts(c.ts)}</td><td style="color:#bc8cff;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.endpoint||'-'}</td><td style="color:#f85149">${fmt(c.input)}</td><td style="color:#3fb950">${fmt(c.output)}</td><td style="color:#58a6ff">${fmt(c.cache_read)}</td><td style="color:#d29922">${fmt(c.cache_write)}</td></tr>`).join('');
    if(d.cache_stats){
      const sg=document.getElementById('scraper_status_grid');
      const sdata=d.cache_stats.scraper||{};
      const skeys=Object.keys(sdata);
      sg.innerHTML=skeys.length===0?'<div class="empty" style="grid-column:1/-1">No scraper cache</div>':skeys.map((k,i)=>{const colors=['val-red','val-green','val-blue','val-gold'];return`<div class="stat-tile tile-dark"><div class="val ${colors[i%4]}">${sdata[k].age_s}s</div><div class="lbl">${k}</div></div>`;}).join('');
    }

    // Requests
    const reqs=(d.request_log||[]).slice(0,50);
    document.getElementById('rc').textContent=reqs.length+' shown';
    document.getElementById('rt').innerHTML=reqs.length===0?'<tr><td colspan="6" class="empty">No requests</td></tr>':reqs.map(r=>`<tr><td class="ts">${ts(r.ts)}</td><td>${mbadge(r.method)}</td><td class="path" title="${r.path}">${r.path}</td><td class="ts">${fmtParams(r.params)}</td><td>${hbadge(r.status)}</td><td class="ts">${r.duration_ms!=null?r.duration_ms+'ms':'-'}</td></tr>`).join('');

    // Archive
    const hist=d.historical_analyses||[];
    document.getElementById('hnc').textContent=hist.length+' records';
    document.getElementById('ht').innerHTML=hist.length===0?'<tr><td colspan="8" class="empty">No data</td></tr>':hist.map(h=>{
      const isExp=expandedIds.has(h.id);
      let fp='';try{fp=JSON.stringify(JSON.parse(h.full_json),null,2);}catch(e){fp=h.full_json||'';}
      return`<tr><td class="ts">${dts(h.ts)}</td><td style="font-weight:700;color:#f0f6fc">${h.ticker}</td><td class="ts">${h.analysis_date||'-'}</td><td>${sig(h.signal)}</td><td style="color:#d29922">${h.confidence!=null?h.confidence+'%':'-'}</td><td class="ts">${h.user_id||'-'}</td><td>${h.full_json&&JSON.parse(h.full_json).was_correct===true?'<span class="badge ok">&#x2713;</span>':h.full_json&&JSON.parse(h.full_json).was_correct===false?'<span class="badge err">&#x2717;</span>':'-'}</td><td><button class="btn-view" onclick="toggleDetails(${h.id})">View</button></td></tr>
      <tr id="details-${h.id}" style="display:${isExp?'table-row':'none'}"><td colspan="8"><div class="archive-details" style="display:block"><div class="json-box">${fp}</div></div></td></tr>`;
    }).join('');

    // Populate user select on first load
    populateUserDropdown();

  }catch(e){
    console.error('Dashboard error:',e);
    document.getElementById('lu').textContent='Error: '+e.message;
  }
}

// ─── User dropdown ───────────────────────────────────────────
let _usersPopulated=false;
async function populateUserDropdown(){
  if(_usersPopulated)return;
  try{
    const r=await fetch('/users',{headers:{'Authorization':'Bearer admin'}});
    if(!r.ok){console.warn('Could not load user list: HTTP '+r.status);return;}
    const users=await r.json();
    if(!Array.isArray(users)||users.length===0){
      console.warn('No users returned from /users');return;
    }
    const sel=document.getElementById('user-select');
    sel.innerHTML='<option value="">-- select user --</option>'+users.map(u=>`<option value="${u.id}">#${u.id} ${u.display_name||u.username} (${u.username})</option>`).join('');
    _usersPopulated=true;
  }catch(e){console.warn('Could not populate user list:',e);}
}

// Init
refreshAll();
setInterval(refreshAll, 30000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard_html():
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.get("/dashboard-data")
def dashboard_data(authorization: str = Header(None)):
    require_admin(authorization)
    uptime = (datetime.now() - _server_start).total_seconds()
    
    # Fetch historical analyses and stats from DB
    history = []
    db_stats = {}
    try:
        with get_session() as session:
            rows = session.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).all()
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
        print(f"Error fetching history for dashboard: {e}")

    try:
        import services.scraper as scr
        scraper_cache = {k: {"age_s": round(time.time() - v["ts"])} for k, v in scr._CACHE.items()}
    except Exception:
        scraper_cache = {}

    cache_stats = {
        "quick_info": len(_quick_info_cache),
        "morning_brief": len(_morning_cache),
        "sector_performance": 1 if _sector_cache.get("data") else 0,
        "asm_gsm": 1 if _asm_gsm_cache.get("data") else 0,
        "scraper": scraper_cache
    }

    with _dash_lock:
        active = list(_active_analyses.values())
        completed = list(_completed_analyses)
        reqs = list(_request_log)
        tok = {
            "total_input":       _token_stats["total_input"],
            "total_output":      _token_stats["total_output"],
            "total_cache_read":  _token_stats["total_cache_read"],
            "total_cache_write": _token_stats["total_cache_write"],
            "total_calls":       _token_stats["total_calls"],
            "recent":            list(_token_stats["recent"]),
        }

    # Separate Claude vs DeepSeek stats from token_log.jsonl
    ai_health = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
    }
    claude_stats = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    deepseek_stats = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    try:
        if TOKEN_LOG_PATH.exists():
            HAIKU_INPUT_RATE = 0.001 / 1_000_000
            HAIKU_OUTPUT_RATE = 0.005 / 1_000_000
            SONNET_INPUT_RATE = 0.003 / 1_000_000
            SONNET_OUTPUT_RATE = 0.015 / 1_000_000
            DEEPSEEK_INPUT_RATE = 0.00014 / 1_000_000
            DEEPSEEK_OUTPUT_RATE = 0.00028 / 1_000_000
            with open(TOKEN_LOG_PATH, "r") as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        model = (e.get("model") or "").lower()
                        inp = e.get("input_tokens", 0) or 0
                        out = e.get("output_tokens", 0) or 0
                        if "deepseek" in model:
                            cost = inp * DEEPSEEK_INPUT_RATE + out * DEEPSEEK_OUTPUT_RATE
                            deepseek_stats["calls"] += 1
                            deepseek_stats["input_tokens"] += inp
                            deepseek_stats["output_tokens"] += out
                            deepseek_stats["cost_usd"] += cost
                        else:
                            cost = (inp * HAIKU_INPUT_RATE + out * HAIKU_OUTPUT_RATE) if "haiku" in model else (inp * SONNET_INPUT_RATE + out * SONNET_OUTPUT_RATE)
                            claude_stats["calls"] += 1
                            claude_stats["input_tokens"] += inp
                            claude_stats["output_tokens"] += out
                            claude_stats["cost_usd"] += cost
                    except Exception:
                        continue
    except Exception:
        pass

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
    with _dash_lock:
        all_reqs = list(_request_log)
        current_harvests = {k: v.copy() for k, v in _harvest_status.items()}
        h_logs = list(_harvest_logs)

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
        print(f"[dashboard] DB active jobs read failed: {e}")

    merged_active = list({**db_active_jobs, **{a.get("job_id", ""): a for a in active}}.values())

    return {
        "server_start":    _server_start.isoformat(),
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
        "feature_errors":  feature_errors,
        "harvest_status":  current_harvests,
        "harvest_logs":    h_logs,
        "latest_news":     latest_news if 'latest_news' in locals() else [],
        "latest_videos":   latest_videos if 'latest_videos' in locals() else [],
        "ai_health":       ai_health,
    }


@app.get("/dashboard-user-data")
def dashboard_user_data(user_id: int, authorization: str = Header(None)):
    """Per-user deep data for admin dashboard: portfolio, analyses, watchlist, journal, net worth."""
    require_admin(authorization)
    result: dict = {"user_id": user_id}
    try:
        with get_session() as session:
            # ── User info ──
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "User not found"}
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
                except Exception:
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

    except Exception as e:
        result["error"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()[:500]

    return result


# ---------------------------------------------------------------------------
# Sector Performance
# ---------------------------------------------------------------------------

_sector_cache: dict = {"data": None, "ts": 0.0}
_morning_cache: dict = {}  # {user_id: {"data": {...}, "ts": float}}
_asm_gsm_cache: dict = {"data": {}, "ts": 0}

# Upcoming IPOs (manually tracked)
UPCOMING_IPOS = [
    {"company": "Swiggy Ltd", "open_date": "TBD 2026", "price_band": "₹371-390"},
    {"company": "Bajaj Housing Finance", "open_date": "TBD 2026", "price_band": "₹66-70"},
    {"company": "Hyundai India", "open_date": "TBD 2026", "price_band": "₹1865-1960"},
]

SECTOR_TICKERS = [
    ("^CNXPSUBANK",  "PSU Bank"),
    ("^CNXFMCG",     "FMCG"),
    ("^CNXIT",       "IT"),
    ("^CNXPHARMA",   "Pharma"),
    ("^CNXAUTO",     "Auto"),
    ("^CNXREALTY",   "Realty"),
    ("^CNXENERGY",   "Energy"),
    ("^CNXMETAL",    "Metal"),
]


# ---------------------------------------------------------------------------
# v1 Market Intelligence Routes (Firecrawl + fallback scraping, 15-min cache)
# ---------------------------------------------------------------------------

from services.scraper import (
    fetch_market_pulse,
    fetch_momentum,
    fetch_macro_alternatives,
    fetch_institutional_flow,
    fetch_earnings_sync_ratio,
    fetch_yoy_aggregate_indicators,
)

# ---------------------------------------------------------------------------
# Unified dashboard endpoint — returns all 4 market intelligence feeds in one
# call. Fetchers are cached (15-min TTL) so this is fast after first load.
# ---------------------------------------------------------------------------

from datetime import datetime as _dt
import concurrent.futures as _cf

# ---------------------------------------------------------------------------
# Section 12: FastAPI Routing Layer — new unified endpoints
# All routes: async def, Pydantic schemas, DB dependency injection
# ---------------------------------------------------------------------------

from fastapi import Depends as _Depends


# ── Pydantic response schemas — imported from schemas/ namespace ─────────────

from schemas import (
    IndexSnapshot, BreadthData, MomentumSignal,
    DashboardPulseResponse, MutualFundEntry,
    InstitutionalLeaderboardResponse, NetWorthSnapshotResponse,
)


# ── DB session dependency (thread-safe SQLAlchemy) ───────────────────────────

def _get_db():
    """Yield a SQLAlchemy session; rolls back on error, always closes."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── /api/v1/market/dashboard-pulse ───────────────────────────────────────────

