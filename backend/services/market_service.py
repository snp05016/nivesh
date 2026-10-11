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
# The single guarded (rate-limited, circuit-broken) info fetcher; re-exported for
# routers that import it from here (ARCH-11).
from services.yfinance_client import _yf_fetch_info

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


# NSE sector indices (Yahoo symbol, display name). Used by the sectors route and
# services/sector_rotation, so it lives here rather than in routers/market (ARCH-13).
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


def get_earnings_estimates(ticker: str) -> dict:
    """Body of GET /api/v1/earnings/estimates; also used by services/earnings_surprise.

    Only a genuine quarterly consensus figure counts as an estimate (FAKE-10):
    no TTM-actual (totalRevenue) or 12-month-forward EPS stand-ins, and no
    actuals from LLM analysis snapshots (period never matched the estimate).
    """
    ticker = ticker.upper()
    try:
        info = _yf_fetch_info(_to_ns(ticker))
        rev_est = info.get("revenueEstimate")
        return {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "revenue_estimate": float(rev_est) / 1e7 if rev_est else None,
            "revenue_actual": None,
            "net_profit_estimate": None,
            "net_profit_actual": None,
            "eps_estimate": None,
            "eps_actual": None,
        }
    except Exception:
        logging.exception("[EARNINGS/ESTIMATES] %s failed", ticker)
        return {"ticker": ticker, "company_name": ticker, "revenue_estimate": None, "revenue_actual": None,
                "net_profit_estimate": None, "net_profit_actual": None, "eps_estimate": None, "eps_actual": None,
                "degraded": True}


def _yf_frame(full_ticker: str, attr: str):
    """A yfinance Ticker DataFrame attribute with 3 tries; None when empty or failing."""
    for attempt in range(3):
        try:
            df = getattr(yf.Ticker(full_ticker), attr)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.info(f"[YF] {attr} attempt {attempt+1} failed for {full_ticker}: {e}")
            if attempt < 2:
                time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
    return None


def analyst_ratings(full_ticker: str) -> dict:
    """Yahoo analyst coverage: always {'ratings', 'consensus', 'buy', 'hold', 'sell'} (CMKT-10).

    Counts come from Ticker.recommendations (yfinance >= 0.2.3x columns
    period/strongBuy/buy/hold/sell/strongSell, current month '0m'); the firm list
    comes from Ticker.upgrades_downgrades (Firm/ToGrade). Third-party consensus,
    not a Nivesh call. Missing data yields 0 counts / [] / None.
    """
    buy = hold = sell = 0
    recs = _yf_frame(full_ticker, "recommendations")
    if recs is not None:
        try:
            current = recs[recs["period"] == "0m"] if "period" in recs.columns else recs.iloc[0:0]
            row = (current if not current.empty else recs).iloc[0]

            def _n(*cols: str) -> int:
                return sum(int(_safe_float(row.get(c))) for c in cols)

            buy, hold, sell = _n("strongBuy", "buy"), _n("hold"), _n("sell", "strongSell")
        except Exception as e:
            logger.warning(f"[analyst-ratings] unreadable recommendations for {full_ticker}: {e}")
            buy = hold = sell = 0

    ratings: list[dict] = []
    grades = _yf_frame(full_ticker, "upgrades_downgrades")
    if grades is not None:
        try:
            for when, row in grades.sort_index(ascending=False).head(6).iterrows():
                firm = row.get("Firm", row.get("firm"))
                grade = row.get("ToGrade", row.get("toGrade"))
                if firm and grade:
                    period = when.strftime("%b %Y") if hasattr(when, "strftime") else str(when)[:7]
                    ratings.append({"firm": str(firm), "grade": str(grade), "period": period})
        except Exception as e:
            logger.warning(f"[analyst-ratings] unreadable upgrades_downgrades for {full_ticker}: {e}")
            ratings = []

    if buy > max(hold, sell):
        consensus = "BUY"
    elif sell > max(buy, hold):
        consensus = "SELL"
    elif buy + hold + sell > 0:
        consensus = "HOLD"
    else:
        consensus = None
    return {"ratings": ratings, "consensus": consensus, "buy": buy, "hold": hold, "sell": sell}


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

def quarter_label(col) -> str:
    """Indian fiscal quarter of a quarter-end column: 2025-06-30 -> 'Q1 FY26'.

    yfinance quarterly columns are Timestamps; Timestamp.strftime has no '%q'
    (CMKT-05), so the quarter is computed from the month.
    """
    if not hasattr(col, "month"):
        return str(col)[:7]
    fy = col.year + 1 if col.month >= 4 else col.year
    return f"Q{(col.month - 4) % 12 // 3 + 1} FY{fy % 100:02d}"


def quarterly_rows(fin, limit: int = 8) -> list[dict]:
    """Newest-first {label, revenue, net_profit} rows (crores) from quarterly_financials."""
    if fin is None or fin.empty:
        return []

    def _crores(row: str, col) -> float:
        if row not in fin.index:
            return 0.0
        return round(_safe_float(fin.loc[row, col]) / 1e7, 1)

    return [
        {"label": quarter_label(col), "revenue": _crores("Total Revenue", col),
         "net_profit": _crores("Net Income", col)}
        for col in list(fin.columns)[:limit]
    ]


def holdings_from_info(info: dict) -> dict:
    """Shareholding and D/E from a yfinance info dict, shared by /quick-info and
    /api/v1/stock-profile so both report the same values in the same units (CMKT-08).

    Yahoo's heldPercentInstitutions is FII + DII combined and no source here splits
    it, so FII, DII and the promoter pledge stay None instead of being estimated
    (#256, #304, #306, #462). debtToEquity arrives as a percentage (36.6) and is
    returned as a ratio (0.37).
    """
    def _num(key: str) -> float | None:
        raw = info.get(key)
        if raw is None:
            return None
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(v) or math.isinf(v) else v

    promoter = _num("heldPercentInsiders")
    institutional = _num("heldPercentInstitutions")
    dte = _num("debtToEquity")
    return {
        "promoter_holding_pct": round(promoter * 100, 2) if promoter is not None else None,
        "institutional_holding_pct": round(institutional * 100, 2) if institutional is not None else None,
        "fii_holding_pct": None,
        "dii_holding_pct": None,
        "promoter_pledged_pct": None,
        "debt_to_equity": round(dte / 100, 2) if dte is not None else None,
    }

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
