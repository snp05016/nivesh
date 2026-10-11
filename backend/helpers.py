"""
Shared helpers, constants, and models for the Nivesh FastAPI application.
Re-exports from domain-specific modules. Architecture deepened per Candidate 3.
"""
import os
from datetime import datetime
from typing import Optional
from collections import deque

from pydantic import BaseModel, Field, field_validator
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
    is_admin, get_analysis_for_date, get_all_ticker_history,
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

# Disk cache re-exports (used by routers/portfolio.py, routers/market.py)
from services.disk_cache import get as _dcache_get, set as _dcache_set, stats as _dcache_stats

# Config re-exports (used by routers via helpers)
from config.settings import NSE_TICKER_OVERRIDES, QUICK_INFO_TTL as _QUICK_INFO_TTL

# ---------------------------------------------------------------------------
# Notification Helpers
# ---------------------------------------------------------------------------

def upsert_device_token(user_id: int, device_token: str, platform: str = "ios") -> dict:
    """Register or update a device token for push notifications.

    Security: refuses to silently rebind an existing device token to a
    different user_id without re-verification. If the token already belongs
    to another user, the caller must prove ownership of the prior binding
    (i.e. re-authenticate as that user) or the upsert is rejected.
    
    Args:
        user_id (int): The ID of the user.
        device_token (str): The APNs or FCM device token.
        platform (str): The OS platform (e.g., 'ios', 'android').
        
    Returns:
        dict: Success message if registered.
        
    Raises:
        ValueError: If token format is invalid.
        PermissionError: If token belongs to another user.
    """
    import re

    # Validate token looks like a real APNs hex token (64–256 hex chars)
    if not re.fullmatch(r"[0-9a-fA-F]{64,256}", device_token):
        raise ValueError("Invalid APNs device token format")

    from datetime import datetime as _dt, timezone
    with get_session() as session:
        existing = session.query(DeviceToken).filter_by(device_token=device_token).first()
        if existing:
            if existing.user_id != user_id:
                raise PermissionError(
                    f"Device token already registered to a different user"
                )
            existing.updated_at = _dt.now(timezone.utc)
            existing.platform = platform or existing.platform
        else:
            try:
                session.add(DeviceToken(user_id=user_id, device_token=device_token, platform=platform))
                session.commit()
            except Exception as _e:
                session.rollback()
                duplicate = session.query(DeviceToken).filter_by(device_token=device_token).first()
                if duplicate:
                    if duplicate.user_id != user_id:
                        raise PermissionError(
                            f"Device token already registered to a different user"
                        )
                    duplicate.updated_at = _dt.now(timezone.utc)
                    duplicate.platform = platform or duplicate.platform
                else:
                    raise
        session.commit()
    return {"success": True, "message": "Device token registered"}

# ---------------------------------------------------------------------------
# JWT Auth Dependencies
# ---------------------------------------------------------------------------

def get_current_user_id(authorization: str = Header(None)) -> Optional[int]:
    """Extract user ID from the Authorization header.
    
    Args:
        authorization (str): The Bearer token header.
        
    Returns:
        Optional[int]: User ID if valid, None otherwise.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return verify_access_token(token)

def require_auth(authorization: str = Header(None)) -> int:
    """Require authentication via JWT token.
    
    Args:
        authorization (str): The Bearer token header.
        
    Returns:
        int: The authenticated user ID.
        
    Raises:
        HTTPException: If token is missing, invalid, or expired (401).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1]
    admin_override = os.getenv("ADMIN_TOKEN")
    if admin_override and token == admin_override:
        return 1
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

def require_admin(authorization: str = Header(None)) -> int:
    """Require admin privileges.
    
    Args:
        authorization (str): The Bearer token header.
        
    Returns:
        int: The authenticated admin user ID.
        
    Raises:
        HTTPException: If user is not an admin (403).
    """
    user_id = require_auth(authorization)
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id

# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., description="User's login username")
    password: str = Field(..., description="Plaintext password")

class RegisterRequest(BaseModel):
    username: str = Field(..., description="Desired username for new account")
    password: str = Field(..., description="Plaintext password for new account")
    display_name: str = Field(..., description="Full display name of the user")

class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol to analyze")
    exchange: str = Field("NSE", description="Exchange to fetch data from (NSE or BSE)")
    user_id: Optional[int] = Field(None, description="ID of the user requesting analysis")
    deep_scan: bool = Field(False, description="Whether to perform a deep fundamental scan")
    scan_type: str = Field("standard", description="Type of scan (standard, deep, extreme)")
    language: Optional[str] = Field(None, description="Preferred language for output")
    debate_rounds: Optional[int] = Field(None, description="Number of rounds for AI debate")
    risk_tolerance: Optional[str] = Field(None, description="User's risk tolerance profile")

    @field_validator("ticker")
    def validate_ticker(cls, v):
        import re
        v = v.strip().upper()
        if not re.match(r'^[A-Za-z0-9&\-\.]{1,20}$', v):
            raise ValueError("Ticker contains invalid characters")
        return v

    @field_validator("exchange")
    def validate_exchange(cls, v):
        if v not in ("NSE", "BSE"):
            raise ValueError("Exchange must be NSE or BSE")
        return v

class WatchlistAddRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol")
    exchange: str = Field("NSE", description="Exchange (NSE or BSE)")
    company_name: str = Field(..., description="Name of the company")

class WatchlistRemoveRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol to remove")

class PortfolioAddRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol")
    exchange: str = Field("NSE", description="Exchange (NSE or BSE)")
    company_name: str = Field(..., description="Name of the company")
    shares: float = Field(..., description="Number of shares bought")
    buy_price: float = Field(..., description="Average buy price per share")
    group_name: str = Field("holdings", description="Portfolio group/bucket")
    target_price: Optional[float] = Field(None, description="Target price for the holding")
    purchase_date: Optional[str] = Field(None, description="Date of purchase")
    is_virtual: bool = Field(False, description="True if this is a paper/virtual trade")

class PortfolioRemoveRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol to remove")

class PortfolioUpdateRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol")
    shares: float = Field(..., description="Updated number of shares")
    buy_price: float = Field(..., description="Updated average buy price")

class PortfolioNoteRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol")
    note: str = Field(..., description="User's custom note for the holding")

class AlertAddRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol")
    target_price: float = Field(..., description="Target price threshold")
    direction: str = Field(..., description="Direction of alert (above or below)")
    company_name: str = Field("", description="Name of the company")

class AlertRemoveRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    alert_id: int = Field(..., description="ID of the alert to remove")

class BatchAnalyzeRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=20, description="List of ticker symbols to analyze")
    exchange: str = Field("NSE", description="Exchange to fetch data from")
    user_id: int | None = Field(None, description="Optional user ID")

class TradeJournalAddRequest(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    ticker: str = Field(..., description="Stock ticker symbol")
    action: str = Field(..., description="Action taken (e.g., BUY, SELL)")
    price_at_time: float = Field(..., description="Price at the time of the trade")
    reason_text: str = Field(..., description="Reasoning for the trade")
    outcome_text: Optional[str] = Field(None, description="Outcome or reflection on the trade")
    company_name: Optional[str] = Field(None, description="Name of the company")
    mood: Optional[str] = Field(None, description="Emotional state during the trade")

class TradeJournalUpdateRequest(BaseModel):
    outcome_text: str = Field(..., description="Updated outcome or reflection")
    mood: Optional[str] = Field(None, description="Updated emotional state")

# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------
from pydantic import BaseModel as _BaseModel
from typing import List as _List

class EarningsSyncRatioResponse(_BaseModel):
    declared_count: int = Field(..., description="Number of companies that declared earnings")
    total_expected: int = Field(..., description="Total expected earnings declarations")
    sync_ratio_pct: float = Field(..., description="Percentage of expected earnings declared")
    fetched_at: str = Field(..., description="Timestamp of data fetch")
    source: str = Field(..., description="Source of earnings data")

class YoYAggregateResponse(_BaseModel):
    revenue_yoy_pct: float = Field(..., description="Year-over-year revenue growth percentage")
    net_profit_yoy_pct: float = Field(..., description="Year-over-year net profit growth percentage")
    companies_reported: int = Field(..., description="Number of companies that reported")
    fetched_at: str = Field(..., description="Timestamp of data fetch")
    source: str = Field(..., description="Source of data")

class InstitutionalLeaderboardResponse(_BaseModel):
    leaderboard: _List[dict] = Field(..., description="List of institutional metrics")
    fetched_at: str = Field(..., description="Timestamp of data fetch")

class NetWorthSnapshotResponse(_BaseModel):
    user_id: int = Field(..., description="ID of the user")
    snapshots: _List[dict] = Field(..., description="Historical net worth snapshots")
    fetched_at: str = Field(..., description="Timestamp of data fetch")

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DataHarvestingError(Exception):
    """Raised when a market data scraping / harvest pipeline fails."""
    pass


# ---------------------------------------------------------------------------
# Indian Numbering System (GH #123 — canonical home in helpers.py)
# All monetary outputs MUST use Lakhs/Crores. Never Millions/Billions.
# ---------------------------------------------------------------------------

def format_indian_currency(value, *, symbol="₹"):
    """Format a numeric value into Indian currency format (Lakhs/Crores).
    
    Args:
        value (float|int|None): The monetary value.
        symbol (str): The currency symbol to prepend.
        
    Returns:
        str: Formatted string representing the amount in Indian scale.
    """
    if value is None:
        return f"{symbol}0"
    value = float(value)
    negative = value < 0
    abs_val = abs(value)
    LAKH = 1_00_000
    CRORE = 1_00_00_000
    if abs_val >= CRORE:
        formatted = f"{symbol}{abs_val / CRORE:,.2f} Crores"
    elif abs_val >= LAKH:
        formatted = f"{symbol}{abs_val / LAKH:,.2f} Lakhs"
    else:
        formatted = f"{symbol}{abs_val:,.0f}"
    return f"-{formatted}" if negative else formatted


def _ban_western_scale(text, company_name=""):
    """Detect and forbid Western numbering scales in output text.
    
    Ensures all monetary and numeric outputs use Indian scales (Lakhs/Crores).
    
    Args:
        text (str): The text to check.
        company_name (str): Company name to mask out from checks to avoid false positives.
        
    Returns:
        str: The original text if safe.
        
    Raises:
        ValueError: If words like million/billion/trillion are detected.
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

