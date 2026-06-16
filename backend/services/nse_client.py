"""
NSE session bootstrap, ASM/GSM surveillance list fetching, and market indices
retrieval with Redis-backed caching.

Extracted from helpers.py.
"""
import random
import math
import time
from datetime import datetime

import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import (
    ASM_GSM_CACHE_TTL as _ASM_GSM_CACHE_TTL,
    HTTP_DEFAULT_TIMEOUT as _HTTP_DEFAULT_TIMEOUT,
    INDICES_CACHE_TTL as _INDICES_CACHE_TTL,
)
from services.disk_cache import get as _dcache_get, set as _dcache_set


# ---------------------------------------------------------------------------
# NSE Session
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ASM / GSM Surveillance Lists
# ---------------------------------------------------------------------------

def _get_asm_gsm_lists():
    """Fetch and cache ASM/GSM lists from NSE (Redis-backed, shared across workers)."""
    # Check Redis cache first
    cached = _dcache_get("asm_gsm", "lists")
    if cached is not None:
        return cached

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

        # Store as sorted lists (JSON-safe) in Redis
        redis_data = {"ASM": sorted(data["ASM"]), "GSM": sorted(data["GSM"])}
        _dcache_set("asm_gsm", "lists", redis_data, ttl=_ASM_GSM_CACHE_TTL)
        return data
    except Exception as e:
        print(f"[NSE] ASM/GSM fetch failed: {e}")
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
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _dcache_set("indices", "all", payload, ttl=_INDICES_CACHE_TTL)
    return payload
