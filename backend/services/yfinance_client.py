import logging
"""
YFinance wrappers, ticker resolution, exchange suffixes, and L1 in-memory cache.

Extracted from helpers.py.
"""
import os
import re
import time
import threading
import random
from datetime import datetime, timezone

import yfinance as yf
from cachetools import TTLCache

from config.settings import (
    YF_BACKOFF_MULTIPLIER as _YF_BACKOFF_MULTIPLIER,
    QUICK_INFO_TTL as _QUICK_INFO_TTL,
    NSE_TICKER_OVERRIDES,
    YF_CIRCUIT_THRESHOLD as _YF_CIRCUIT_THRESHOLD,
    YF_CIRCUIT_TIMEOUT as _YF_CIRCUIT_TIMEOUT,
)
from services.rate_limiter import yf_acquire

# ---------------------------------------------------------------------------
# Exchange & Ticker Constants (Task 33: suffixes now env-overridable)
# ---------------------------------------------------------------------------
EXCHANGE_SUFFIXES = {
    "NSE": os.getenv("NSE_SUFFIX", ".NS"),
    "BSE": os.getenv("BSE_SUFFIX", ".BO"),
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

# ---------------------------------------------------------------------------
# Shared circuit breaker + token bucket for the wrappers below (REL-14).
# routers/analysis.py (/screener) uses the same breaker.
# ---------------------------------------------------------------------------
_cb_lock = threading.Lock()
_cb_failures = 0
_cb_open_until = 0.0


def yf_circuit_is_open() -> bool:
    global _cb_failures
    with _cb_lock:
        if _cb_failures >= _YF_CIRCUIT_THRESHOLD:
            if time.time() < _cb_open_until:
                return True
            _cb_failures = 0
        return False


def yf_circuit_record_failure() -> None:
    global _cb_failures, _cb_open_until
    with _cb_lock:
        _cb_failures += 1
        if _cb_failures >= _YF_CIRCUIT_THRESHOLD:
            _cb_open_until = time.time() + _YF_CIRCUIT_TIMEOUT


def yf_circuit_record_success() -> None:
    global _cb_failures
    with _cb_lock:
        _cb_failures = 0


def _yf_guard() -> bool:
    """False while the breaker is open; otherwise waits for a rate-limit token."""
    if yf_circuit_is_open():
        return False
    yf_acquire()
    return True

# ---------------------------------------------------------------------------
# YFinance wrappers (Task 34: tenacity exponential backoff)
# ---------------------------------------------------------------------------

def _yf_fetch_info(sym: str) -> dict:
    """Fetches ticker information from yfinance with exponential backoff retries.

    Args:
        sym (str): The ticker symbol to fetch.

    Returns:
        dict: The information dictionary returned by yfinance, or an empty dict if it fails.
    """
    for attempt in range(3):
        if not _yf_guard():
            return {}
        try:
            info = yf.Ticker(sym).info
            if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                yf_circuit_record_success()
                return info
        except Exception as e:
            yf_circuit_record_failure()
            logging.info(f"[YF] Attempt {attempt+1} failed for {sym}: {e}")
            if attempt < 2:
                sleep_time = (_YF_BACKOFF_MULTIPLIER * (2 ** attempt)) + (random.random() * 0.5)
                time.sleep(sleep_time)
    return {}

# ponytail: per-process last-good cache; move to Redis/DB if workers>1 matters
_LAST_GOOD: dict[str, tuple[float, float, float]] = {}  # sym -> (current, prev, epoch)
_last_good_lock = threading.Lock()
_STALE_MAX_AGE_S = 4 * 86400  # covers a weekend plus a market holiday


def _yf_price(ticker_sym: str) -> tuple[float | None, float | None]:
    """Fetches the current and previous closing prices for a ticker.

    Falls back to trying the .NS suffix if .BO returns no data, retries once
    after a short jittered pause, and logs a WARNING when no price is found.
    Successful prices feed the last-good cache used by _yf_price_with_status.

    Args:
        ticker_sym (str): The ticker symbol to fetch prices for.

    Returns:
        tuple[float | None, float | None]: A tuple containing the current price and
            the previous day's closing price. Returns (None, None) on failure.
    """
    import pandas as pd
    def _fetch(sym: str):
        if not _yf_guard():
            return None, None
        try:
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
            yf_circuit_record_success()
            return current, prev
        except Exception as e:
            yf_circuit_record_failure()
            logging.info(f"[YF Price Error] {sym}: {e}")
            return None, None

    current, prev = None, None
    if yf_circuit_is_open():
        return current, prev
    for attempt in range(2):  # one jittered retry: Yahoo 429s / empty frames are often transient
        if attempt:
            time.sleep(0.5 + random.random() * 0.5)
        current, prev = _fetch(ticker_sym)
        if current is None and ticker_sym.upper().endswith(".BO"):
            ns_sym = ticker_sym[:-3] + ".NS"
            logging.info(f"[BSE FALLBACK] No data for {ticker_sym}, trying {ns_sym}")
            current, prev = _fetch(ns_sym)
        if current is not None:
            with _last_good_lock:
                _LAST_GOOD[ticker_sym] = (current, prev if prev is not None else current, time.time())
            return current, prev
    logging.warning(f"[YF Price] no price for {ticker_sym} after retry")
    return current, prev

def _yf_price_with_status(ticker_sym: str) -> tuple[float | None, float | None, str, str | None]:
    """Like _yf_price, but says whether the price is live, a stale last-good
    value, or unavailable: (current, prev, 'live'|'stale'|'unavailable', as_of_iso).

    Display-only. Alert/trading paths keep using _yf_price, which never returns
    a stale price.
    """
    current, prev = _yf_price(ticker_sym)
    if current is not None:
        return current, prev, "live", datetime.now(timezone.utc).isoformat()
    with _last_good_lock:
        cached = _LAST_GOOD.get(ticker_sym)
    if cached is not None and time.time() - cached[2] <= _STALE_MAX_AGE_S:
        return cached[0], cached[1], "stale", datetime.fromtimestamp(cached[2], timezone.utc).isoformat()
    return None, None, "unavailable", None

# ---------------------------------------------------------------------------
# Ticker resolution
# ---------------------------------------------------------------------------
# Positive resolutions live a day; failed ones are retried after 5 min, never
# cached as resolved (REL-14). Both bounded.
_ticker_resolution_cache: TTLCache = TTLCache(maxsize=5000, ttl=86400)
_ticker_unresolved: TTLCache = TTLCache(maxsize=5000, ttl=300)
_ticker_resolution_lock = threading.Lock()
# Exchange symbols: letters/digits plus & and - (M&M, BAJAJ-AUTO). Anything else
# never reaches Yahoo.
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9&\-]{0,19}$")

def _resolve_with_fallback(base_ticker: str, preferred_suffix: str) -> str:
    """Resolves a ticker with a preferred exchange suffix, falling back to the other if needed.

    Args:
        base_ticker (str): The base ticker symbol without a suffix.
        preferred_suffix (str): The preferred suffix (e.g., '.NS' or '.BO').

    Returns:
        str: The resolved ticker symbol with a valid suffix. When neither
        exchange answers, returns the preferred form without caching it as
        resolved (it is retried after the short unresolved TTL).
    """
    cache_key = f"{base_ticker}{preferred_suffix}"
    t1 = cache_key
    if not _TICKER_RE.match(base_ticker):
        return t1
    with _ticker_resolution_lock:
        if cache_key in _ticker_resolution_cache:
            return _ticker_resolution_cache[cache_key]
        if cache_key in _ticker_unresolved:
            return t1

    fallback_suffix = ".BO" if preferred_suffix == ".NS" else ".NS"
    t2 = f"{base_ticker}{fallback_suffix}"

    # Preferred first, then the other exchange. Probe errors are not breaker
    # failures: junk tickers raise here and must not black out real quotes.
    for candidate in (t1, t2):
        if not _yf_guard():
            break
        try:
            fast = yf.Ticker(candidate).fast_info
            if getattr(fast, "last_price", None) is not None:
                with _ticker_resolution_lock:
                    _ticker_resolution_cache[cache_key] = candidate
                return candidate
        except Exception as _e:
            logging.debug(f"[YF Resolve] {candidate}: {_e}")

    with _ticker_resolution_lock:
        _ticker_unresolved[cache_key] = True
    return t1

def _to_ns(ticker: str) -> str:
    """Converts a ticker to its NSE equivalent with a .NS suffix if not already specified.

    Args:
        ticker (str): The input ticker symbol.

    Returns:
        str: The ticker symbol with the .NS suffix, using overrides if applicable.
    """
    t = ticker.upper()
    if "." in t:
        return t
    
    # Check manual overrides first
    if t in NSE_TICKER_OVERRIDES:
        return NSE_TICKER_OVERRIDES[t]
        
    base_t = t
    return _resolve_with_fallback(base_t, ".NS")

def _resolve_ticker(ticker: str, exchange: str) -> str:
    """Resolves a raw ticker symbol to its full format for a specific exchange.

    Applies manual ticker overrides and suffix fallbacks.

    Args:
        ticker (str): The raw ticker symbol.
        exchange (str): The exchange to resolve for ("NSE" or "BSE").

    Returns:
        str: The resolved ticker symbol.
    """
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

# ---------------------------------------------------------------------------
# JSON extraction utility
# ---------------------------------------------------------------------------
from services.llm_utils import extract_json_from_text as _extract_json_from_text  # noqa: E402,F401  (re-exported via helpers)

# ---------------------------------------------------------------------------
# L1 in-memory cache (quick info)
# ---------------------------------------------------------------------------
_quick_info_cache: dict[str, tuple[float, dict]] = {}
_quick_info_lock = threading.Lock()
