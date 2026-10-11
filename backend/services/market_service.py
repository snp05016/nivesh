"""
market_service.py — Pure business/data logic extracted from routers/market.py.

Controller-Service-Repository contract (AGENTS.md §3.1):
  - This file contains ONLY pure computation, data-fetching (yfinance), and caching logic.
  - NO get_session() calls.  DB access stays in the router.
  - NO FastAPI / HTTP concerns (no Request, Response, HTTPException, Header).

Imported by routers/market.py to replace inline helper functions.
"""

from __future__ import annotations

import json
import logging
import math
import random
import time

import yfinance as yf

from helpers import _to_ns

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# yfinance data-fetching helpers
# ---------------------------------------------------------------------------

def _get_quarterly_fin(full_ticker: str):
    """Fetch quarterly financials with retry, falling back to .BO if .NS returns empty.

    Returns (yf.Ticker, quarterly_financials DataFrame or None).
    """
    def _fetch(sym: str):
        _t = None
        _fin = None
        for attempt in range(3):
            try:
                _t = yf.Ticker(sym)
                _fin = _t.quarterly_financials
                if _fin is not None and not _fin.empty:
                    return _t, _fin
            except Exception as e:
                logger.info(f"[YF] Quarterly fin attempt {attempt+1} failed for {sym}: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
        return _t, _fin

    t, fin = _fetch(full_ticker)
    if (fin is None or fin.empty) and full_ticker.endswith(".NS"):
        alt = full_ticker[:-3] + ".BO"
        logger.info(f"[QF FALLBACK] No data for {full_ticker}, trying {alt}")
        t, fin = _fetch(alt)
    return t, fin


def _yf_fetch_info(full_ticker: str) -> dict:
    """Fetch yfinance Ticker.info with 3 retries. Returns empty dict on failure.

    NOTE: This replaces the helpers._yf_fetch_info import — the market router
    was already shadowing it with a local definition. Consolidated here.
    """
    for attempt in range(3):
        try:
            t = yf.Ticker(full_ticker)
            info = t.info
            if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                return info
        except Exception as _e:
            if attempt < 2:
                time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
    try:
        t = yf.Ticker(full_ticker)
        return t.info or {}
    except Exception as e:
        logger.warning(f"_yf_fetch_info failed for {full_ticker}: {e}")
        return {}


def get_rbi_policy() -> dict:
    """RBI policy reference values from config (no live feed exists).

    Returns rbi_repo_rate_pct / rbi_repo_rate_as_of / rbi_stance / rbi_source.
    Values are None and rbi_source is 'unavailable' when the operator has not
    set RBI_REPO_RATE_PCT, so callers never show a stale hardcoded rate.
    """
    from config import settings as _settings

    rate = _settings.RBI_REPO_RATE_PCT
    if rate is None:
        return {"rbi_repo_rate_pct": None, "rbi_repo_rate_as_of": None,
                "rbi_stance": None, "rbi_source": "unavailable"}
    return {"rbi_repo_rate_pct": rate, "rbi_repo_rate_as_of": _settings.RBI_REPO_RATE_AS_OF,
            "rbi_stance": _settings.RBI_POLICY_STANCE, "rbi_source": "config"}


# ---------------------------------------------------------------------------
# Formatting & utility helpers
# ---------------------------------------------------------------------------

def _fmt_inr_crores(value: float) -> str:
    """Format a raw INR float into Indian Crores string. E.g. 1.25e11 → '₹12,500.00 Cr'"""
    if not value or math.isnan(value) or math.isinf(value):
        return "₹0"
    cr = value / 1e7  # 1 Crore = 10^7
    if cr >= 10000:
        return f"₹{cr:,.0f} Cr"
    elif cr >= 100:
        return f"₹{cr:,.1f} Cr"
    elif cr >= 1:
        return f"₹{cr:,.2f} Cr"
    else:
        lakhs = value / 1e5
        return f"₹{lakhs:,.2f} L"


def _safe_float(v, default: float = 0.0) -> float:
    """Return float, replacing NaN/Inf with default."""
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception as _e:
        return default


# ---------------------------------------------------------------------------
# Data-transformation helpers
# ---------------------------------------------------------------------------

def _earnings_result_from_row(r, now_iso: str) -> dict:
    """Build an EarningsResult dict from an AnalysisHistory row."""
    try:
        fj = json.loads(r.full_json or "{}")
    except Exception as _e:
        fj = {}
    fs = fj.get("fundamentals_snapshot", {})
    revenue = _safe_float(fs.get("revenue_crores") or fs.get("revenue"))
    net_profit = _safe_float(fs.get("net_profit_crores") or fs.get("net_profit"))
    eps_val = fs.get("eps")
    return {
        "ticker": r.ticker,
        "company_name": fj.get("company_name") or r.ticker,
        "quarter": fj.get("quarter") or "Q4FY26",
        "result_date": r.analysis_date or now_iso[:10],
        "market_cap": "large_cap",
        "revenue": revenue,
        "revenue_prev": round(revenue * 0.85, 2),
        "net_profit": net_profit,
        "net_profit_prev": round(net_profit * 0.80, 2),
        "gross_profit": None,
        "gross_profit_prev": None,
        "eps": _safe_float(eps_val) if eps_val is not None else None,
        "eps_prev": None,
        "ltp": 0.0,
        "change_percent": 0.0,
        "is_consolidated": True,
        "reported_at": r.created_at.isoformat() if r.created_at else None,
    }


def _scan_upcoming_earnings(target_date: str) -> list[dict]:
    """Scan yfinance for tickers with earnings on or near target_date. Returns up to 10."""
    from datetime import datetime

    scan_tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
                    "BAJFINANCE", "LT", "AXISBANK", "WIPRO", "SUNPHARMA", "TITAN",
                    "MARUTI", "KOTAKBANK", "ITC", "HINDUNILVR", "BHARTIARTL"]
    results = []
    for ticker in scan_tickers:
        try:
            ns = _to_ns(ticker)
            t = yf.Ticker(ns)
            cal = t.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                if isinstance(dates, list):
                    for d in dates:
                        try:
                            ed = d.date() if hasattr(d, "date") else d
                            if abs((ed - datetime.strptime(target_date, "%Y-%m-%d").date()).days) <= 3:
                                info = t.info
                                results.append({
                                    "ticker": ticker,
                                    "company_name": info.get("longName") or ticker,
                                    "quarter": "Upcoming",
                                    "result_date": ed.strftime("%Y-%m-%d"),
                                    "market_cap": "large_cap",
                                    "revenue": 0, "revenue_prev": 0,
                                    "net_profit": 0, "net_profit_prev": 0,
                                    "eps": info.get("trailingEps"), "eps_prev": None,
                                    "ltp": info.get("regularMarketPrice") or 0,
                                    "change_percent": 0,
                                    "is_consolidated": True,
                                    "sparkline": [],
                                    "price_change_7d_pct": None,
                                    "reported_at": None,
                                })
                                break
                        except Exception as _e:
                            continue
            if len(results) >= 10:
                break
        except Exception as _e:
            continue
    return results
