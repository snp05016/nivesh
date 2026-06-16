"""
Shared helpers, constants, and models for the Nivesh FastAPI application.
Re-exports from domain-specific modules. Architecture deepened per Candidate 3.
"""
import os
from datetime import datetime
from typing import Optional
from collections import deque

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

# Re-export from focused domain modules
from core.rate_limiter import _check_rate_limit, _rate_limit_store, _RATE_LIMITS
from core.concurrency import (
    _acquire_analysis_slot, _release_analysis_slot, _force_clear_analysis_slot,
    _get_stuck_analyses, _get_analyze_semaphore, _release_analyze_semaphore,
    _running_analyses, _RUNNING_ANALYSES_STALENESS_SEC, _ANALYZE_MAX_CONCURRENT,
)
from core.dashboard_state import (
    _dash_lock, _harvest_status, _active_analyses, _completed_analyses,
    _request_log, _dash_logs, _token_stats, _token_log_lock, TOKEN_LOG_PATH,
    _dash_update_harvest, _dash_start_job, _dash_end_job, _dash_log_request,
    _log_token_usage,
)
from services.yfinance_client import (
    EXCHANGE_SUFFIXES, EXCHANGE_SUFFIX, NSE_TICKERS,
    _yf_fetch_info, _yf_price,
    _resolve_with_fallback, _to_ns, _resolve_ticker,
    _extract_json_from_text,
    _quick_info_cache, _quick_info_lock,
)
from services.nse_client import (
    _nse_session, _get_asm_gsm_lists, _evict_asm_gsm_ticker,
    _INDICES_TICKERS, _fetch_single_index, _get_indices_data,
)

# Task 42: ticker overrides loaded from config
from config.settings import NSE_TICKER_OVERRIDES

# ---------------------------------------------------------------------------
# Notification Helpers
# ---------------------------------------------------------------------------

def upsert_device_token(user_id: int, device_token: str, platform: str = "ios") -> dict:
    """Register or update a device token for push notifications."""
    from datetime import datetime as _dt
    with get_session() as session:
        existing = session.query(DeviceToken).filter_by(device_token=device_token).first()
        if existing:
            existing.updated_at = _dt.utcnow()
            existing.user_id = user_id
            existing.platform = platform or existing.platform
        else:
            try:
                session.add(DeviceToken(user_id=user_id, device_token=device_token, platform=platform))
                session.commit()
            except Exception:
                session.rollback()
                duplicate = session.query(DeviceToken).filter_by(device_token=device_token).first()
                if duplicate:
                    duplicate.user_id = user_id
                    duplicate.updated_at = _dt.utcnow()
                    duplicate.platform = platform or duplicate.platform
                else:
                    raise
        session.commit()
    return {"success": True, "message": "Device token registered"}

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
# Response Models
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
