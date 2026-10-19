"""
market_service.py — Pure business/data logic extracted from routers/market.py.

Controller-Service-Repository contract (AGENTS.md §3.1):
  - This file contains ONLY pure computation, data-fetching (yfinance), and caching logic.
  - NO get_session() calls.  DB access stays in the router.
  - NO FastAPI / HTTP concerns (no Request, Response, HTTPException, Header).

Imported by routers/market.py to replace inline helper functions.
"""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

import yfinance as yf

from core.timeutil import ist_today
from helpers import _to_ns
from services.cache_service import cached_call
# The single guarded (rate-limited, circuit-broken) info fetcher; re-exported for
# routers that import it from here (ARCH-11).
from services.yfinance_client import _yf_fetch_info, _yf_price, yf_history

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

# ---------------------------------------------------------------------------
# Earnings (CMKT-01): yfinance quarterly results for a fixed large-cap universe.
# Nothing here reads AnalysisHistory, and a figure Yahoo does not report is omitted,
# never estimated.
# ---------------------------------------------------------------------------

# Ticker -> company name (the fallback when Yahoo info is unavailable).
EARNINGS_UNIVERSE: dict[str, str] = {
    "RELIANCE": "Reliance Industries Ltd",
    "TCS": "Tata Consultancy Services Ltd",
    "HDFCBANK": "HDFC Bank Ltd",
    "INFY": "Infosys Ltd",
    "ICICIBANK": "ICICI Bank Ltd",
    "SBIN": "State Bank of India",
    "BAJFINANCE": "Bajaj Finance Ltd",
    "LT": "Larsen & Toubro Ltd",
    "WIPRO": "Wipro Ltd",
    "SUNPHARMA": "Sun Pharmaceutical Industries Ltd",
    "TITAN": "Titan Company Ltd",
    "MARUTI": "Maruti Suzuki India Ltd",
}
_EARNINGS_SNAPSHOT_TTL = 21600  # 6 h
_POST_RESULT_TTL = 1800         # 30 min


def _cell(row, col, scale: float = 1.0) -> float | None:
    """One quarterly_financials value divided by scale, or None when missing or NaN."""
    if row is None or col not in row.index:
        return None
    v = _safe_float(row[col], math.nan)
    return None if math.isnan(v) else round(v / scale, 2)


def _growth_pct(cur: float, prev: float) -> float | None:
    """YoY growth in percent; None when the prior-year figure is not positive."""
    return round((cur - prev) / prev * 100, 2) if prev > 0 else None


def _quarterly_result(ticker: str) -> tuple[dict | None, str | None]:
    """(EarningsResult dict, None) for the latest quarter against the same quarter a
    year earlier, or (None, reason) when yfinance lacks either quarter."""
    full_ticker = _to_ns(ticker)
    _, fin = _get_quarterly_fin(full_ticker)
    if fin is None or fin.empty:
        return None, f"{ticker}: no quarterly financial data from yfinance"
    cols = list(fin.columns)
    # True YoY only: the fifth column must be the same quarter one year earlier.
    if len(cols) < 5 or not 330 <= (cols[0] - cols[4]).days <= 400:
        return None, f"{ticker}: no same-quarter-last-year figures"
    latest, year_ago = cols[0], cols[4]

    def _row(*names: str):
        return next((fin.loc[n] for n in names if n in fin.index), None)

    rev_row, profit_row = _row("Total Revenue"), _row("Net Income")
    revenue, revenue_prev = _cell(rev_row, latest, 1e7), _cell(rev_row, year_ago, 1e7)
    net_profit, net_profit_prev = _cell(profit_row, latest, 1e7), _cell(profit_row, year_ago, 1e7)
    if revenue is None or revenue_prev is None or net_profit is None or net_profit_prev is None:
        return None, f"{ticker}: revenue or net profit missing for a compared quarter"
    eps_row = _row("Diluted EPS", "Basic EPS", "Diluted Earnings Per Share")

    info: dict = {}
    try:
        info = _yf_fetch_info(full_ticker) or {}
    except Exception as e:
        logger.warning("[earnings] quote unavailable for %s: %s", ticker, e)
    ltp = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
    prev_close = _safe_float(info.get("regularMarketPreviousClose") or info.get("previousClose"))
    return {
        "ticker": ticker,
        "company_name": info.get("longName") or info.get("shortName") or EARNINGS_UNIVERSE.get(ticker, ticker),
        "quarter": quarter_label(latest),
        # Period end: yfinance quarterly financials carry no filing date.
        "result_date": str(latest)[:10],
        "market_cap": "large_cap",  # the universe is fixed Nifty large caps
        "revenue": revenue,
        "revenue_prev": revenue_prev,
        "net_profit": net_profit,
        "net_profit_prev": net_profit_prev,
        "gross_profit": None,
        "gross_profit_prev": None,
        "eps": _cell(eps_row, latest),
        "eps_prev": _cell(eps_row, year_ago),
        "ltp": round(ltp, 2),
        "change_percent": round((ltp - prev_close) / prev_close * 100, 2) if ltp > 0 and prev_close > 0 else 0.0,
        "is_consolidated": True,
        "reported_at": None,
        "revenue_growth_pct": _growth_pct(revenue, revenue_prev),
        "net_profit_growth_pct": _growth_pct(net_profit, net_profit_prev),
    }, None


def build_quarterly_earnings(tickers: list[str]) -> tuple[list[dict], str]:
    """Quarterly YoY results for tickers, newest period first, and a diagnostic that is
    non-empty only when no ticker produced a result."""
    results: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_quarterly_result, t): t for t in tickers}
        try:
            for fut in as_completed(futures, timeout=45):
                try:
                    item, err = fut.result()
                except Exception as e:
                    item, err = None, f"{futures[fut]}: {str(e)[:120]}"
                if item:
                    results.append(item)
                if err:
                    errors.append(err)
        except FuturesTimeout:
            errors.append("yfinance timed out")
    diagnostic = ""
    if not results:
        detail = f" Errors: {'; '.join(errors[:3])}." if errors else ""
        diagnostic = (f"Quarterly results unavailable from yfinance for the {len(tickers)} "
                      f"tracked large caps.{detail} Please retry shortly.")
    results.sort(key=lambda r: (r["result_date"], r["ticker"]), reverse=True)
    return results, diagnostic


def earnings_universe_snapshot() -> dict:
    """{'results', 'diagnostic'} for EARNINGS_UNIVERSE, cached 6 h; an empty build is not cached."""
    def _build() -> dict:
        results, diagnostic = build_quarterly_earnings(list(EARNINGS_UNIVERSE))
        return {"results": results, "diagnostic": diagnostic}
    return cached_call("market", "earnings_universe_v2", _build,
                       ttl=_EARNINGS_SNAPSHOT_TTL, cache_if=lambda snap: bool(snap["results"]))


def _post_result_move(ticker: str, today) -> dict | None:
    """Move from the last close before a results announcement in the last 14 days to the
    latest price, else None."""
    full_ticker = _to_ns(ticker)
    dates = _yf_frame(full_ticker, "earnings_dates")  # announcement dates, newest first
    if dates is None:
        return None
    recent = [d.date() for d in dates.index if 0 <= (today - d.date()).days <= 14]
    if not recent:
        return None
    result_day = max(recent)
    hist: Any = yf_history(full_ticker, "1mo")  # DatetimeIndex rows; pandas stubs type the index as int
    if hist.empty:
        return None
    closes = hist["Close"].dropna()
    before = closes[[d.date() < result_day for d in closes.index]]
    if before.empty:
        return None
    base = float(before.iloc[-1])
    ltp = _yf_price(full_ticker)[0] or float(closes.iloc[-1])
    vol = _safe_float(hist["Volume"].iloc[-1], math.nan) if "Volume" in hist.columns else math.nan
    return {
        "ticker": ticker,
        "company_name": EARNINGS_UNIVERSE.get(ticker, ticker),
        "result_date": result_day.strftime("%Y-%m-%d"),
        "ltp": round(ltp, 2),
        "change_percent": round((ltp - base) / base * 100, 2) if base > 0 else 0.0,
        "volume": None if math.isnan(vol) else int(vol),
    }


def post_result_movers(tickers: list[str]) -> list[dict]:
    """Tickers that announced results (yfinance earnings dates) in the last 14 days, by
    absolute price move since the pre-announcement close. One bad ticker is skipped."""
    today = ist_today()

    def _one(ticker: str) -> dict | None:
        try:
            return _post_result_move(ticker, today)
        except Exception as e:
            logger.warning("[post-result-movers] skipping %s: %s", ticker, e)
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        movers = [m for m in ex.map(_one, tickers) if m]
    movers.sort(key=lambda m: abs(m["change_percent"]), reverse=True)
    return movers


def recent_post_result_movers() -> list[dict]:
    """post_result_movers(EARNINGS_UNIVERSE), cached 30 min (an empty list for 5 min)."""
    return cached_call("market", "post_result_movers_v2", lambda: post_result_movers(list(EARNINGS_UNIVERSE)),
                       ttl=_POST_RESULT_TTL, negative_ttl=300)


def _scan_upcoming_earnings(target_date: str, tickers: list[str] | None = None) -> list[dict]:
    """Scan yfinance for tickers (default: a large-cap list) with earnings within 3 days
    of target_date. Returns up to 10."""
    from datetime import datetime

    scan_tickers = tickers or ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
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
