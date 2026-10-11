from config.settings import get_user_agent
import logging
"""
NSE session bootstrap, ASM/GSM surveillance list fetching, and market indices
retrieval with Redis-backed caching.

Extracted from helpers.py.
"""
import random
import math
import time
from datetime import datetime, timezone

import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import (
    ASM_GSM_CACHE_TTL as _ASM_GSM_CACHE_TTL,
    INDICES_CACHE_TTL as _INDICES_CACHE_TTL,
)
from services.disk_cache import get as _dcache_get, set as _dcache_set


# ---------------------------------------------------------------------------
# NSE Session
# ---------------------------------------------------------------------------

# (connect, read) cap: the bootstrap plus three list calls used to take ~20 s worst case.
_NSE_TIMEOUT = (3, 5)

# Partial/failed ASM/GSM refreshes are cached this long only, so callers stop
# hammering NSE but recover within minutes instead of hours (PERF-18).
_ASM_GSM_DEGRADED_TTL = 120

_ASM_GSM_URLS = (
    ("ASM", "https://www.nseindia.com/api/surveillance-asm-list?index=longTerm"),
    ("ASM", "https://www.nseindia.com/api/surveillance-asm-list?index=shortTerm"),
    ("GSM", "https://www.nseindia.com/api/surveillance-gsm-list"),
)


def _nse_session():
    """Bootstrap a session with NSE cookies, identified by the honest bot UA (REG-10)."""
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": get_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=_NSE_TIMEOUT)
    except Exception: pass
    return s


# ---------------------------------------------------------------------------
# ASM / GSM Surveillance Lists
# ---------------------------------------------------------------------------

def _get_asm_gsm_lists():
    """Fetch and cache ASM/GSM lists from NSE (Redis-backed, shared across workers).

    Full TTL only when all three lists answered 200; a partial or failed refresh
    is cached for _ASM_GSM_DEGRADED_TTL so it is not pinned for hours.
    """
    # Check Redis cache first
    cached = _dcache_get("asm_gsm", "lists")
    if cached is not None:
        return cached

    logging.info("[NSE] Refreshing ASM/GSM lists...")
    data = {"ASM": set(), "GSM": set()}
    ok = True
    try:
        session = _nse_session()
        for section, url in _ASM_GSM_URLS:
            resp = session.get(url, timeout=_NSE_TIMEOUT)
            if resp.status_code != 200:
                ok = False
                continue
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data[section].add(sym.upper())
    except Exception as e:
        ok = False
        logging.info(f"[NSE] ASM/GSM fetch failed: {type(e).__name__}")

    # Store as sorted lists (JSON-safe) in Redis
    redis_data = {"ASM": sorted(data["ASM"]), "GSM": sorted(data["GSM"])}
    _dcache_set("asm_gsm", "lists", redis_data, ttl=_ASM_GSM_CACHE_TTL if ok else _ASM_GSM_DEGRADED_TTL)
    return data


def _evict_asm_gsm_ticker(ticker: str) -> bool:
    """Evict a ticker from ASM/GSM cache by rebuilding without it. Redis-backed."""
    ticker = ticker.upper().strip()
    cached = _dcache_get("asm_gsm", "lists")
    if not cached:
        return False
    removed = False
    for section in ("ASM", "GSM"):
        if ticker in cached.get(section, []):
            cached[section] = [t for t in cached[section] if t != ticker]
            removed = True
    if removed:
        _dcache_set("asm_gsm", "lists", cached, ttl=_ASM_GSM_CACHE_TTL)
    return removed


# ---------------------------------------------------------------------------
# Market Indices
# ---------------------------------------------------------------------------

_INDICES_TICKERS = [
    ("^NSEI",      "Nifty 50"),
    ("^BSESN",     "Sensex"),
    ("^NSEBANK",   "Nifty Bank"),
    ("^CNXIT",     "Nifty IT"),
    ("^NSEMDCP50",  "Nifty Midcap 100"),
    ("USDINR=X",   "USD/INR"),
]


def _fetch_single_index(ticker: str, name: str) -> dict | None:
    """Fetch a single index ticker. Returns dict or None on failure."""
    import random as _random
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
            if attempt < 2:
                time.sleep((1.5 * (2 ** attempt)) + (_random.random() * 0.2))

    if current is None or math.isnan(current):
        return None

    change_abs = round(current - (prev_close or 0), 4)
    change_pct = round((change_abs / prev_close) * 100, 4) if prev_close else 0.0
    return {
        "name": name,
        "ticker": ticker,
        "value": round(float(current), 4),
        "change_pct": change_pct,
        "change_abs": change_abs,
    }


def _get_indices_data() -> dict:
    """Fetch and cache market indices via Redis (shared across all workers).
    Fetches 6 indices in parallel via ThreadPoolExecutor."""
    # Redis-backed cache
    cached = _dcache_get("indices", "all")
    if cached is not None:
        return cached

    # Parallel fetch of all 6 indices
    result = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_single_index, t, n): n for t, n in _INDICES_TICKERS}
        for f in as_completed(futures):
            entry = f.result()
            if entry is not None:
                result.append(entry)

    payload = {
        "indices": result,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _dcache_set("indices", "all", payload, ttl=_INDICES_CACHE_TTL)
    return payload
