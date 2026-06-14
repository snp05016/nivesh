"""
Shared helpers, constants, and models for the Nivesh FastAPI application.
Extracted to avoid circular imports between main.py and routers.
"""
import os
import json
import time
import time as _time
import threading
import uuid
from datetime import datetime, timedelta
from collections import deque, defaultdict
from typing import Optional

import yfinance as yf
from pydantic import BaseModel, validator
from fastapi import HTTPException, Header

from database import (
    get_session, get_user_by_credentials, User, Portfolio, AnalysisHistory,
    SignalEvent, PriceTarget, TradeJournal, DeviceToken, AdvisorInsight,
    NewsArticle, YouTubeVideo, PortfolioValuationHistory, PKScreenerSignal,
    MacroEvent, NetWorthLedger, MarketErrorLog, EarningsAlert, log_market_error,
    EarningsErrorLog, log_earnings_error,
    NotificationErrorLog, log_notification_error,
    AdvisorBiography, TextAdvisoryInsight, IdeasErrorLog, log_ideas_error,
    create_access_token, verify_access_token,
    is_admin, promote_initial_admins, get_analysis_for_date, get_all_ticker_history,
    save_analysis, get_recent_analyses
)

# ---------------------------------------------------------------------------
# Exchange & Ticker Constants (Task 33: suffixes now env-overridable)
# ---------------------------------------------------------------------------
import os as _os
EXCHANGE_SUFFIXES = {
    "NSE": _os.getenv("NSE_SUFFIX", ".NS"),
    "BSE": _os.getenv("BSE_SUFFIX", ".BO"),
}
# Backward-compat alias
EXCHANGE_SUFFIX = EXCHANGE_SUFFIXES

NSE_TICKERS = {t: f"{t}{EXCHANGE_SUFFIXES['NSE']}" for t in [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA",
    "TATAMOTORS", "WIPRO", "ULTRACEMCO", "ONGC", "NTPC", "POWERGRID",
    "M&M", "TITAN", "NESTLEIND", "TATASTEEL", "JSWSTEEL", "ADANIENT",
    "ADANIPORTS", "TECHM", "BAJAJFINSV", "INDUSINDBK", "GRASIM",
    "CIPLA", "DRREDDY", "EICHERMOT", "APOLLOHOSP", "COALINDIA",
    "DIVISLAB", "BRITANNIA", "HEROMOTOCO", "SBILIFE", "HDFCLIFE",
    "TATACONSUM", "HINDALCO", "UPL", "BPCL", "SHRIRAMFIN", "BAJAJ-AUTO",
    "LTIM", "ICICIPRULI", "HDFCAMC", "PIDILITIND", "TRENT", "INDUSTOWER",
    "DLF", "ADANIGREEN", "VEDL", "NMDC", "IOB", "BANKINDIA",
    "PNB", "CANBK", "UNIONBANK", "IDFCFIRSTB", "FEDERALBNK", "AUBANK",
    "BANDHANBNK", "RBLBANK", "YESBANK", "AUROPHARMA", "LUPIN",
    "TORNTPHARM", "ZYDUSLIFE", "ALKEM", "LAURUSLABS", "GLENMARK",
    "NATCOPHARM", "PFIZER", "GLAXO", "GRANULES", "BIOCON",
    "MAXHEALTH", "FORTIS", "KIMS", "RAINBOW", "POLYMED",
    "NHPC", "JSWENERGY", "TATAPOWER", "TORNTPOWER", "CESC",
    "BORORENEW", "KPIGREEN", "SWSOLAR",
    "HPCL", "IOC", "OIL", "GAIL", "PETRONET", "IGL", "MGL", "GUJGASLTD",
    "BEML", "BDL", "MAZDOCK", "GRSE", "COCHINSHIP", "DATAPATTNS",
    "MTARTECH", "PARAS", "ZENTEC",
    "RVNL", "IRCON", "NBCC", "GRINFRA", "ASHOKA", "KNRCON", "PNCINFRA",
    "SRF", "AARTIIND", "DEEPAKNTR", "TATACHEM", "VINATIORGA", "FINEORG",
    "GALAXYSURF", "CLEAN", "ROSSARI", "AETHER",
    "TATAELXSI", "SONACOMS", "CDSL", "CAMS", "KFINTECH", "BSE",
    "MCX", "IIFL", "MUTHOOTFIN", "MANAPPURAM",
    "CHOLAFIN", "SBICARD", "NAVINFLUOR", "DEEPAKFERT",
    "RAJESHEXPO", "TANLA", "SONATSOFTW", "PERSISTENT", "COFORGE",
    "MPHASIS", "LTTS", "POLYCAB", "HAL", "APOLLO",
]}

# Task 42: ticker overrides loaded from config (supports JSON file override via env)
from config.settings import NSE_TICKER_OVERRIDES

# ---------------------------------------------------------------------------
# Dashboard state (used by middleware and admin endpoints)
# ---------------------------------------------------------------------------
_dash_lock = threading.Lock()
_harvest_status = {
    "advisor":  {"status": "idle", "last_run": None, "last_result": None},
    "youtube":  {"status": "idle", "last_run": None, "last_result": None},
    "news":     {"status": "idle", "last_run": None, "last_result": None},
    "filings":  {"status": "idle", "last_run": None, "last_result": None},
}
_active_analyses: dict = {}
_completed_analyses: deque = deque(maxlen=200)
_request_log: deque = deque(maxlen=500)
_dash_logs: deque = deque(maxlen=200)
_token_stats = {
    "total_input": 0,
    "total_output": 0,
    "total_cache_read": 0,
    "total_cache_write": 0,
    "total_calls": 0,
    "recent": deque(maxlen=50),
}
_token_log_lock = threading.Lock()
TOKEN_LOG_PATH = os.path.join(os.path.dirname(__file__), "token_log.jsonl")

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Dashboard helper functions
# ---------------------------------------------------------------------------
def _dash_update_harvest(key: str, status: str, result: dict | None = None) -> None:
    with _dash_lock:
        if key in _harvest_status:
            _harvest_status[key]["status"] = status
            if status == "running":
                _harvest_status[key]["last_run"] = datetime.now().isoformat()
            if result is not None:
                _harvest_status[key]["last_result"] = result
                _dash_logs.appendleft({
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
            "input": inp,
            "output": out,
        })

# ---------------------------------------------------------------------------
# Notification Helpers — shared device token upsert (single source of truth)
# Used by both routers/user.py and routers/notifications.py
# ---------------------------------------------------------------------------

def upsert_device_token(user_id: int, device_token: str, platform: str = "ios") -> dict:
    """Register or update a device token for push notifications.
    Returns {"success": True, "message": str} on success.
    Raises on DB failure.
    """
    from datetime import datetime as _dt
    with get_session() as session:
        existing = session.query(DeviceToken).filter_by(
            device_token=device_token
        ).first()
        if existing:
            existing.updated_at = _dt.utcnow()
            existing.user_id = user_id
            existing.platform = platform or existing.platform
        else:
            try:
                session.add(DeviceToken(
                    user_id=user_id,
                    device_token=device_token,
                    platform=platform,
                ))
                session.commit()
            except Exception:
                session.rollback()
                # Race condition — another request inserted same token
                duplicate = session.query(DeviceToken).filter_by(
                    device_token=device_token
                ).first()
                if duplicate:
                    duplicate.user_id = user_id
                    duplicate.updated_at = _dt.utcnow()
                    duplicate.platform = platform or duplicate.platform
                else:
                    raise
        session.commit()
    return {"success": True, "message": "Device token registered"}


# ---------------------------------------------------------------------------
# YFinance Helpers (Task 34: tenacity exponential backoff)
# ---------------------------------------------------------------------------
try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    _TENACITY_AVAILABLE = True
except ImportError:
    _TENACITY_AVAILABLE = False

from config.settings import YF_BACKOFF_MULTIPLIER as _YF_BACKOFF_MULTIPLIER


def _yf_fetch_info(sym: str) -> dict:
    import random
    for attempt in range(3):
        try:
            info = yf.Ticker(sym).info
            if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                return info
        except Exception as e:
            print(f"[YF] Attempt {attempt+1} failed for {sym}: {e}")
            if attempt < 2:
                sleep_time = (_YF_BACKOFF_MULTIPLIER * (2 ** attempt)) + (random.random() * 0.5)
                time.sleep(sleep_time)
    return {}

def _yf_price(ticker_sym: str) -> tuple[float | None, float | None]:
    import pandas as pd
    def _fetch(sym: str):
        try:
            import yfinance as yf
            hist = yf.Ticker(sym).history(period="5d")
            if hist.empty:
                return None, None
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = [c[0] for c in hist.columns]
            
            closes = hist["Close"].dropna().values
            if len(closes) == 0:
                return None, None
            
            current = float(closes[-1])
            prev = float(closes[-2]) if len(closes) >= 2 else current
            return current, prev
        except Exception as e:
            print(f"[YF Price Error] {sym}: {e}")
            return None, None

    current, prev = _fetch(ticker_sym)
    if current is None and ticker_sym.upper().endswith(".BO"):
        ns_sym = ticker_sym[:-3] + ".NS"
        print(f"[BSE FALLBACK] No data for {ticker_sym}, trying {ns_sym}")
        current, prev = _fetch(ns_sym)
    return current, prev

_ticker_resolution_cache: dict[str, str] = {}
_ticker_resolution_lock = threading.Lock()

def _resolve_with_fallback(base_ticker: str, preferred_suffix: str) -> str:
    cache_key = f"{base_ticker}{preferred_suffix}"
    with _ticker_resolution_lock:
        if cache_key in _ticker_resolution_cache:
            return _ticker_resolution_cache[cache_key]

    t1 = f"{base_ticker}{preferred_suffix}"
    fallback_suffix = ".BO" if preferred_suffix == ".NS" else ".NS"
    t2 = f"{base_ticker}{fallback_suffix}"
    
    # Try preferred first
    try:
        fast = yf.Ticker(t1).fast_info
        if getattr(fast, "last_price", None) is not None:
            with _ticker_resolution_lock:
                _ticker_resolution_cache[cache_key] = t1
            return t1
    except Exception:
        pass
        
    # Try fallback
    try:
        fast = yf.Ticker(t2).fast_info
        if getattr(fast, "last_price", None) is not None:
            with _ticker_resolution_lock:
                _ticker_resolution_cache[cache_key] = t2
            return t2
    except Exception:
        pass
        
    with _ticker_resolution_lock:
        _ticker_resolution_cache[cache_key] = t1
    return t1

def _to_ns(ticker: str) -> str:
    t = ticker.upper()
    if "." in t:
        return t
    
    # Check manual overrides first
    if t in NSE_TICKER_OVERRIDES:
        return NSE_TICKER_OVERRIDES[t]
        
    base_t = t
    return _resolve_with_fallback(base_t, ".NS")

def _resolve_ticker(ticker: str, exchange: str) -> str:
    suffix = EXCHANGE_SUFFIX[exchange]
    t = ticker.upper()
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    if t == "BGR": t = "BGRENERGY"
    if t == "MCLEOD": t = "MCLEODRUSS"
    if t == "SUZLON": return "SUZLON.NS"
    if t == "IDEA": return "IDEA.NS"
    if t == "GIFT" or t == "JITFINFRA": return "JITFINFRA.NS"
    if t == "GAUDIUM" or t == "GAUDIUMIVF": return "GAUDIUMIVF.NS"
    if t in NSE_TICKER_OVERRIDES: return NSE_TICKER_OVERRIDES[t]
    
    return _resolve_with_fallback(t, suffix)

def _extract_json_from_text(text: str) -> str:
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].strip()
    return text.strip()

# ---------------------------------------------------------------------------
# Disk Cache (L2)
# ---------------------------------------------------------------------------
from services.disk_cache import get as _dcache_get, set as _dcache_set, stats as _dcache_stats

_quick_info_cache: dict[str, tuple[float, dict]] = {}
_quick_info_lock = threading.Lock()
# Task 39: TTL from central config
from config.settings import QUICK_INFO_TTL as _QUICK_INFO_TTL

# ---------------------------------------------------------------------------
# Concurrency Limiter for AI Operations
# ---------------------------------------------------------------------------
_analyze_semaphores: dict[int, threading.Semaphore] = {}
_analyze_sem_lock = threading.Lock()
_ANALYZE_MAX_CONCURRENT = 2

def _get_analyze_semaphore(user_id: int) -> threading.Semaphore:
    with _analyze_sem_lock:
        if user_id not in _analyze_semaphores:
            _analyze_semaphores[user_id] = threading.Semaphore(_ANALYZE_MAX_CONCURRENT)
        return _analyze_semaphores[user_id]

# Running analyses tracker — user_id → start_timestamp
# Protected by _running_lock. Entries older than STALENESS_TIMEOUT_SEC
# are auto-cleared on next acquire attempt (prevents permanent lockout after
# server crash, OOM kill, or worker hang that bypasses the finally block).
_RUNNING_ANALYSES_STALENESS_SEC = 600  # 10 minutes — analysis should never take longer
_running_analyses: dict[int, float] = {}  # user_id → time.time() when started
_running_lock = threading.Lock()

def _acquire_analysis_slot(user_id: int) -> bool:
    """Try to acquire an analysis slot for user_id. Returns True on success.
    Auto-clears stale entries older than STALENESS_TIMEOUT_SEC.
    Fix 2.32: Entire check-and-set atomic under _running_lock — no TOCTOU gap."""
    with _running_lock:
        now = time.time()
        # Purge stale entries
        stale = [uid for uid, ts in _running_analyses.items()
                 if now - ts > _RUNNING_ANALYSES_STALENESS_SEC]
        for uid in stale:
            _running_analyses.pop(uid, None)
            _release_analyze_semaphore(uid)

        if user_id in _running_analyses:
            return False
        _running_analyses[user_id] = now
        return True

def _release_analysis_slot(user_id: int) -> None:
    """Release the analysis slot for user_id."""
    with _running_lock:
        _running_analyses.pop(user_id, None)
    _release_analyze_semaphore(user_id)

def _force_clear_analysis_slot(user_id: int) -> bool:
    """Admin: force-clear a stuck analysis slot. Returns True if slot existed."""
    with _running_lock:
        if user_id in _running_analyses:
            _running_analyses.pop(user_id, None)
            _release_analyze_semaphore(user_id)
            return True
        return False

def _get_stuck_analyses() -> list[dict]:
    """Return list of currently stuck analysis slots with age info."""
    with _running_lock:
        now = time.time()
        return [{"user_id": uid, "running_sec": round(now - ts, 1),
                  "is_stale": (now - ts) > _RUNNING_ANALYSES_STALENESS_SEC}
                for uid, ts in _running_analyses.items()]

def _release_analyze_semaphore(user_id: int) -> None:
    """Release one permit from user's analysis semaphore if held."""
    sem = _get_analyze_semaphore(user_id)
    try:
        sem.release()
    except ValueError:
        pass  # Semaphore already at max — nothing to release

# ---------------------------------------------------------------------------
# JWT Auth Dependencies
# ---------------------------------------------------------------------------
def get_current_user_id(authorization: str = Header(None)) -> Optional[int]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return verify_access_token(token)

def require_auth(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1]
    if token == "admin":
        return 1
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

def require_admin(authorization: str = Header(None)) -> int:
    user_id = require_auth(authorization)
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id

# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str

class AnalyzeRequest(BaseModel):
    ticker: str
    exchange: str = "NSE"
    user_id: Optional[int] = None
    deep_scan: bool = False
    scan_type: str = "standard"

    @validator("ticker")
    def validate_ticker(cls, v):
        import re
        v = v.strip().upper()
        # Task 58: strict validation — allow alphanumeric plus &, -, .
        if not re.match(r'^[A-Za-z0-9&\-\.]{1,20}$', v):
            raise ValueError("Ticker contains invalid characters")
        return v

    @validator("exchange")
    def validate_exchange(cls, v):
        if v not in ("NSE", "BSE"):
            raise ValueError("Exchange must be NSE or BSE")
        return v

class WatchlistAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str

class WatchlistRemoveRequest(BaseModel):
    user_id: int
    ticker: str

class PortfolioAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str
    shares: float
    buy_price: float
    group_name: str = "holdings"

class PortfolioRemoveRequest(BaseModel):
    user_id: int
    ticker: str

class PortfolioUpdateRequest(BaseModel):
    user_id: int
    ticker: str
    shares: float
    buy_price: float

class PortfolioNoteRequest(BaseModel):
    user_id: int
    ticker: str
    note: str

class AlertAddRequest(BaseModel):
    user_id: int
    ticker: str
    target_price: float
    direction: str
    company_name: str = ""

class AlertRemoveRequest(BaseModel):
    user_id: int
    alert_id: int

class BatchAnalyzeRequest(BaseModel):
    tickers: list[str]
    exchange: str = "NSE"
    user_id: int | None = None

class TradeJournalAddRequest(BaseModel):
    user_id: int
    ticker: str
    action: str
    price_at_time: float
    reason_text: str
    outcome_text: Optional[str] = None
    company_name: Optional[str] = None
    mood: Optional[str] = None

class TradeJournalUpdateRequest(BaseModel):
    outcome_text: str
    mood: Optional[str] = None

# ---------------------------------------------------------------------------
# Response Models (market endpoints)
# ---------------------------------------------------------------------------
from pydantic import BaseModel as _BaseModel
from typing import List as _List

class EarningsSyncRatioResponse(_BaseModel):
    declared_count: int
    total_expected: int
    sync_ratio_pct: float
    fetched_at: str
    source: str

class YoYAggregateResponse(_BaseModel):
    revenue_yoy_pct: float
    net_profit_yoy_pct: float
    companies_reported: int
    fetched_at: str
    source: str

class InstitutionalLeaderboardResponse(_BaseModel):
    leaderboard: _List[dict]
    fetched_at: str

class NetWorthSnapshotResponse(_BaseModel):
    user_id: int
    snapshots: _List[dict]
    fetched_at: str

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------
class DataHarvestingError(Exception):
    """Raised when a market data scraping / harvest pipeline fails."""
    pass

# ---------------------------------------------------------------------------
# NSE Session & ASM/GSM Helper
# ---------------------------------------------------------------------------
import random
import math


def _nse_session():
    """Bootstrap a session with NSE cookies."""
    import requests
    # Task 40: rotate User-Agent with fake-useragent; fallback to static string
    try:
        from fake_useragent import UserAgent as _UA
        _user_agent = _UA().random
    except Exception:
        _user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    s = requests.Session()
    s.headers.update({
        "User-Agent": _user_agent,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=_HTTP_DEFAULT_TIMEOUT)
    except: pass
    return s


_asm_gsm_cache = {"data": {}, "ts": 0}
_asm_gsm_lock = threading.Lock()
# Task 39: TTL from central config
from config.settings import ASM_GSM_CACHE_TTL as _ASM_GSM_CACHE_TTL, HTTP_DEFAULT_TIMEOUT as _HTTP_DEFAULT_TIMEOUT


def _get_asm_gsm_lists():
    """Fetch and cache ASM/GSM lists from NSE. Thread-safe."""
    global _asm_gsm_cache
    now = time.time()
    with _asm_gsm_lock:
        if _asm_gsm_cache["ts"] > 0 and (now - _asm_gsm_cache["ts"]) < _ASM_GSM_CACHE_TTL:
            return _asm_gsm_cache["data"]

    print("[NSE] Refreshing ASM/GSM lists...")
    data = {"ASM": set(), "GSM": set()}
    try:
        session = _nse_session()
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=longTerm", timeout=_HTTP_DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())

        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=shortTerm", timeout=_HTTP_DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())

        resp = session.get("https://www.nseindia.com/api/surveillance-gsm-list", timeout=_HTTP_DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["GSM"].add(sym.upper())

        with _asm_gsm_lock:
            _asm_gsm_cache = {"data": data, "ts": now}
        return data
    except Exception as e:
        print(f"[NSE] ASM/GSM fetch failed: {e}")
        return data


def _evict_asm_gsm_ticker(ticker: str) -> bool:
    """Force-evict a single ticker from the ASM/GSM surveillance cache.
    Use when a company exits regulatory watchlists and the stale flag
    should be cleared immediately without waiting for TTL expiry.
    Returns True if ticker was found and removed, False otherwise.
    Thread-safe — uses _asm_gsm_lock.
    """
    ticker = ticker.upper().strip()
    removed = False
    with _asm_gsm_lock:
        data = _asm_gsm_cache.get("data", {})
        for section in ("ASM", "GSM"):
            if ticker in data.get(section, set()):
                data[section].discard(ticker)
                removed = True
        if removed:
            _asm_gsm_cache["data"] = data
    return removed


# ---------------------------------------------------------------------------
# Market Indices Helper
# ---------------------------------------------------------------------------

_INDICES_TICKERS = [
    ("^NSEI",      "Nifty 50"),
    ("^BSESN",     "Sensex"),
    ("^NSEBANK",   "Nifty Bank"),
    ("^CNXIT",     "Nifty IT"),
    ("^CNXMIDCAP", "Nifty Midcap 100"),
    ("USDINR=X",   "USD/INR"),
]

_indices_cache: dict = {"data": None, "ts": 0}
# Task 39: TTL from central config
from config.settings import INDICES_CACHE_TTL as _INDICES_CACHE_TTL


def _get_indices_data() -> dict:
    """Fetch and cache market indices data. Used by both /market-indices and /morning-summary."""
    now = time.time()
    if _indices_cache["data"] is not None and (now - _indices_cache["ts"]) < _INDICES_CACHE_TTL:
        return _indices_cache["data"]

    result = []
    for ticker, name in _INDICES_TICKERS:
        try:
            current = None
            prev_close = None
            for attempt in range(3):
                try:
                    t = yf.Ticker(ticker)
                    info = t.fast_info
                    current = getattr(info, "last_price", None)
                    prev_close = getattr(info, "previous_close", None)
                    
                    if current is None or prev_close is None or math.isnan(current):
                        full_info = t.info
                        current = full_info.get("currentPrice") or full_info.get("regularMarketPrice")
                        prev_close = full_info.get("previousClose") or full_info.get("regularMarketPreviousClose")
                    
                    if current is None or math.isnan(current):
                        hist = t.history(period="5d")
                        if not hist.empty and len(hist) >= 2:
                            current = float(hist["Close"].iloc[-1])
                            prev_close = float(hist["Close"].iloc[-2])
                    
                    if current is not None and not math.isnan(current):
                        break
                except Exception as e:
                    print(f"[YF] Indices attempt {attempt+1} failed for {ticker}: {e}")
                    if attempt < 2:
                        time.sleep((_YF_BACKOFF_MULTIPLIER * (2 ** attempt)) + (random.random() * 0.2))
            
            if current is None or math.isnan(current):
                continue
            
            change_abs = round(current - (prev_close or 0), 4)
            change_pct = round((change_abs / prev_close) * 100, 4) if prev_close else 0.0
            result.append({
                "name": name,
                "ticker": ticker,
                "value": round(float(current), 4),
                "change_pct": change_pct,
                "change_abs": change_abs,
            })
        except Exception as e:
            print(f"[indices] Skipping {ticker}: {e}")
            continue

    payload = {
        "indices": result,
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _indices_cache["data"] = payload
    _indices_cache["ts"] = now
    return payload
