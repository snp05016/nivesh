"""Earnings routes: /earnings-calendar and /api/v1/earnings/*.

Split out of routers/market.py (ARCH-14); paths, handler names and tags are unchanged.
"""
from helpers import (
    get_session, _resolve_ticker, _to_ns, _dcache_get, _dcache_set, DataHarvestingError,
    require_auth, AnalysisHistory, log_market_error, log_earnings_error,
)
from services import earnings_alerts_service
from services.market_service import (
    _get_quarterly_fin, _yf_fetch_info, _earnings_result_from_row, _scan_upcoming_earnings,
)
import json
import logging
import asyncio
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException
import yfinance as yf
from services.cache_service import cached_call
from services.scraper import fetch_earnings_sync_ratio, fetch_yoy_aggregate_indicators
from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional
from pydantic import BaseModel as _BaseModelLocal

router = APIRouter(tags=["Market Data"])


def _ticker_earnings_events(ticker_raw: str, today) -> list:
    """Upcoming/recent earnings events for one holding. Logs and returns [] on
    any failure, so one bad ticker never discards the batch (PERF-10)."""
    try:
        full_ticker = _resolve_ticker(ticker_raw, "NSE")
        cal = yf.Ticker(full_ticker).calendar
        earnings_dates = []
        if isinstance(cal, dict) and 'Earnings Date' in cal:
            dates_val = cal['Earnings Date']
            if isinstance(dates_val, list):
                earnings_dates = dates_val
        elif hasattr(cal, 'empty') and not cal.empty and 'Earnings Date' in cal.columns:
            # fallback for older yfinance versions that return DataFrame
            earnings_dates = cal['Earnings Date'].dropna().tolist()

        events = []
        for d in earnings_dates:
            ed = d.date() if hasattr(d, 'date') else d
            days_away = (ed - today).days
            if -7 <= days_away <= 45:
                events.append({
                    "ticker": ticker_raw.upper(),
                    "earnings_date": ed.strftime("%d-%b-%Y"),
                    "days_away": days_away,
                })
        return events
    except Exception as e:
        logging.warning(f"[earnings-calendar] skipping {ticker_raw}: {e}")
        return []


def _holding_tickers() -> list:
    from database import get_session, Portfolio
    with get_session() as session:
        return [t[0] for t in session.query(Portfolio.ticker).filter(
            Portfolio.group_name == "holdings"
        ).distinct().all()]


def _compute_earnings_calendar() -> dict:
    tickers = _holding_tickers()
    today = datetime.now().date()
    with ThreadPoolExecutor(max_workers=8) as ex:
        per_ticker = list(ex.map(lambda t: _ticker_earnings_events(t, today), tickers))
    results = [e for events in per_ticker for e in events]
    results.sort(key=lambda x: x["days_away"])
    return {"events": results}


@router.get("/earnings-calendar")
def earnings_calendar_endpoint():
    """
    Returns upcoming earnings dates for NSE portfolio stocks.

    Single-flight cached for 15 min: concurrent misses compute once (PERF-10).

    Returns:
        Any: The response.
    """
    try:
        return cached_call("market", "earnings_calendar", _compute_earnings_calendar,
                           ttl=900, cache_if=lambda p: p is not None)
    except Exception as e:
        logging.error(f"[earnings-calendar] failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


class EarningsSyncRatioResponseLocal(_BaseModel):
    declared_count: int
    total_expected: int
    sync_ratio_pct: float
    fetched_at: str
    source: str


class YoYAggregateResponseLocal(_BaseModel):
    revenue_yoy_pct: _Optional[float] = None
    net_profit_yoy_pct: _Optional[float] = None
    companies_reported: int
    fetched_at: str
    source: str


@router.get("/api/v1/earnings/sync-ratio", response_model=EarningsSyncRatioResponseLocal)
async def earnings_sync_ratio_endpoint():
    """
    Real-time tracking metric: total companies that have declared quarterly
results vs total statutory listed exchange obligations (e.g. 4432/5042).
Backed by 15-min in-memory TTL cache.

    Args:

    Returns:
        Any: The response.
    """
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            None, fetch_earnings_sync_ratio
        )
    except DataHarvestingError:
        raise
    except Exception as exc:
        raise DataHarvestingError(str(exc)) from exc

    declared = raw.get("declared_count")
    if declared is None:
        raise HTTPException(status_code=503, detail="Results-declared count unavailable")
    total = raw.get("total_expected", 5042)
    ratio = round((declared / total) * 100, 1) if total > 0 else 0.0

    return EarningsSyncRatioResponseLocal(
        declared_count=declared,
        total_expected=total,
        sync_ratio_pct=ratio,
        fetched_at=raw.get("fetched_at", ""),
        source=raw.get("source", "unknown"),
    )


@router.get("/api/v1/earnings/yoy-aggregate", response_model=YoYAggregateResponseLocal)
async def yoy_aggregate_endpoint():
    """
    Composite market health: aggregate YoY Revenue and Net Profit
expansion/contraction metrics across NSE-listed companies.
Backed by 15-min in-memory TTL cache.

    Args:

    Returns:
        Any: The response.
    """
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            None, fetch_yoy_aggregate_indicators
        )
    except DataHarvestingError:
        raise
    except Exception as exc:
        raise DataHarvestingError(str(exc)) from exc

    return YoYAggregateResponseLocal(
        revenue_yoy_pct=raw.get("revenue_yoy_pct"),
        net_profit_yoy_pct=raw.get("net_profit_yoy_pct"),
        companies_reported=raw.get("companies_reported", 0),
        fetched_at=raw.get("fetched_at", ""),
        source=raw.get("source", "unknown"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Earnings Intelligence Endpoints  (/api/v1/earnings/*)
# iOS EarningsDashboardView tabs: Progress | Calendar | Feed | Screeners | Variance | Post-Result
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/v1/earnings/progress")
def earnings_progress_endpoint():
    # There is no exchange-wide results-filing source. Counting the app's own
    # analyses over a fixed denominator was fabricated progress (FAKE-08).
    raise HTTPException(
        status_code=503,
        detail="Earnings reporting progress unavailable: no exchange-wide results-filing source",
    )


def _build_yfinance_fallback_earnings(tickers: list[str], now_iso: str) -> tuple[list[dict], str]:
    """
    Build earnings-like results from yfinance quarterly financials when no
    AnalysisHistory records exist. For each ticker, fetches quarterly financials
    and computes revenue_growth_pct / net_profit_growth_pct from YoY comparisons
    (current quarter vs same quarter last year).

    Returns (results: list[dict], diagnostic: str).
    diagnostic is non-empty only when yfinance also returned no useful data.
    """
    import math
    import time
    import random

    results: list[dict] = []
    errors: list[str] = []
    known_companies: dict[str, str] = {
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

    import concurrent.futures

    def _fetch_one(ticker: str):
        """Fetch and build earnings result for one ticker. Returns (result_dict_or_None, error_str_or_None)."""
        try:
            full_ticker = _to_ns(ticker)
            t_obj, fin = _get_quarterly_fin(full_ticker)

            if fin is None or fin.empty:
                return None, f"{ticker}: no quarterly financial data from yfinance"

            # Extract key rows
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            profit_row = fin.loc["Net Income"] if "Net Income" in fin.index else None

            if rev_row is None and profit_row is None:
                return None, f"{ticker}: missing Total Revenue and Net Income rows"

            cols = list(fin.columns)
            if len(cols) == 0:
                return None, f"{ticker}: no quarter columns in financials"

            # Most recent quarter
            latest_col = cols[0]
            latest_label = latest_col.strftime("Q%qFY%y") if hasattr(latest_col, 'strftime') else str(latest_col)[:7]
            result_date = latest_col.strftime("%Y-%m-%d") if hasattr(latest_col, 'strftime') else now_iso[:10]

            revenue = float(rev_row[latest_col]) / 1e7 if rev_row is not None and latest_col in rev_row.index else 0.0
            net_profit = float(profit_row[latest_col]) / 1e7 if profit_row is not None and latest_col in profit_row.index else 0.0
            revenue = 0.0 if math.isnan(revenue) or math.isinf(revenue) else round(revenue, 2)
            net_profit = 0.0 if math.isnan(net_profit) or math.isinf(net_profit) else round(net_profit, 2)

            # Same quarter last year (4 quarters back)
            prev_col = cols[4] if len(cols) > 4 else (cols[-1] if len(cols) > 0 else None)
            revenue_prev = 0.0
            net_profit_prev = 0.0
            if prev_col is not None:
                rp = float(rev_row[prev_col]) / 1e7 if rev_row is not None and prev_col in rev_row.index else 0.0
                np = float(profit_row[prev_col]) / 1e7 if profit_row is not None and prev_col in profit_row.index else 0.0
                revenue_prev = 0.0 if math.isnan(rp) or math.isinf(rp) else round(rp, 2)
                net_profit_prev = 0.0 if math.isnan(np) or math.isinf(np) else round(np, 2)

            # YoY growth from quarterly comparison
            revenue_growth_pct = round(((revenue - revenue_prev) / max(abs(revenue_prev), 1)) * 100, 2)
            net_profit_growth_pct = round(((net_profit - net_profit_prev) / max(abs(net_profit_prev), 1)) * 100, 2)

            # LTP from yfinance info
            ltp = 0.0
            company_name = known_companies.get(ticker, ticker)
            try:
                info = _yf_fetch_info(full_ticker)
                if info:
                    cn = info.get("longName") or info.get("shortName")
                    if cn:
                        company_name = cn
                    lp = info.get("regularMarketPrice") or info.get("currentPrice")
                    if lp and not math.isnan(float(lp)):
                        ltp = round(float(lp), 2)
            except Exception as e:
                logging.warning("[earnings-fallback] LTP unavailable for %s: %s", ticker, e)

            # EPS from quarterly data
            eps = None
            eps_prev = None
            try:
                eps_candidates = ["Diluted EPS", "Basic EPS", "Diluted Earnings Per Share"]
                eps_row = None
                for candidate in eps_candidates:
                    if candidate in fin.index:
                        eps_row = fin.loc[candidate]
                        break
                if eps_row is not None:
                    if latest_col in eps_row.index:
                        ev = float(eps_row[latest_col])
                        if not (math.isnan(ev) or math.isinf(ev)):
                            eps = round(ev, 2)
                    if prev_col is not None and prev_col in eps_row.index:
                        pev = float(eps_row[prev_col])
                        if not (math.isnan(pev) or math.isinf(pev)):
                            eps_prev = round(pev, 2)
            except Exception as e:
                logging.warning("[earnings-fallback] EPS unavailable for %s: %s", ticker, e)

            item = {
                "ticker": ticker,
                "company_name": company_name,
                "quarter": latest_label,
                "result_date": result_date,
                "market_cap": "large_cap",
                "revenue": revenue,
                "revenue_prev": revenue_prev,
                "net_profit": net_profit,
                "net_profit_prev": net_profit_prev,
                "gross_profit": None,
                "gross_profit_prev": None,
                "eps": eps,
                "eps_prev": eps_prev,
                "ltp": ltp,
                "change_percent": 0.0,
                "is_consolidated": True,
                "reported_at": None,
                "revenue_growth_pct": revenue_growth_pct,
                "net_profit_growth_pct": net_profit_growth_pct,
            }
            return item, None

        except Exception as e:
            log_earnings_error("earnings_feed_yfinance_fallback", str(e), failed_ticker=ticker)
            return None, f"{ticker}: {str(e)[:120]}"

    # Parallel fetch with 45-second overall timeout (12 tickers * 3 retries each = 36+ yfinance calls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in tickers}
        for fut in concurrent.futures.as_completed(futures, timeout=45):
            ticker = futures[fut]
            try:
                item, err = fut.result(timeout=0)
                if item:
                    results.append(item)
                if err:
                    errors.append(err)
            except Exception as e:
                logging.warning(f"Caught exception: {e}")
                errors.append(f"{ticker}: timed out or executor error (yfinance slow)")

    diagnostic = ""
    if not results:
        ticker_list_preview = ", ".join(tickers[:6])
        if errors:
            error_list = "; ".join(errors[:3])
            diagnostic = (
                f"No analysis records in database and yfinance fallback also returned no data. "
                f"Tried {len(tickers)} tickers ({ticker_list_preview}...). "
                f"Errors: {error_list}. Run an analysis first to populate earnings data."
            )
        else:
            diagnostic = (
                f"No analysis records in database and yfinance fallback also returned no data. "
                f"Tried {len(tickers)} tickers ({ticker_list_preview}...). "
                f"Run an analysis first to populate earnings data."
            )

    return results, diagnostic


@router.get("/api/v1/earnings/feed")
def earnings_feed_endpoint(market_cap: str = "all", sort: str = "latest"):
    """
    Ranked earnings feed — returns results categorized by sort parameter:
  - "latest":      most recently reported (default)
  - "best_performer":   highest positive profit variance
  - "worst_performer":  highest negative profit variance
Each result includes revenue_growth_pct and net_profit_growth_pct for sorting.
Falls back to yfinance quarterly data when no AnalysisHistory records exist.
Adds data_source and diagnostic fields for transparency.

    Args:
        market_cap (str): The market_cap.
        sort (str): The sort.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    data_source = "database"
    diagnostic = None

    try:
        with get_session() as session:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
            rows = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date >= cutoff
            ).order_by(AnalysisHistory.created_at.desc()).all()
            seen: set = set()
            results = []
            for r in rows:
                if r.ticker in seen:
                    continue
                seen.add(r.ticker)
                item = _earnings_result_from_row(r, now_iso)
                if item["revenue"] == 0 and item["net_profit"] == 0:
                    continue
                # Compute growth metrics for sorting
                rev_growth = round(((item["revenue"] - item["revenue_prev"]) / max(abs(item["revenue_prev"]), 1)) * 100, 2)
                profit_growth = round(((item["net_profit"] - item["net_profit_prev"]) / max(abs(item["net_profit_prev"]), 1)) * 100, 2)
                item["revenue_growth_pct"] = rev_growth
                item["net_profit_growth_pct"] = profit_growth
                results.append(item)

        # Fallback: when no DB results, build sample data from yfinance
        if not results:
            fallback_tickers = [
                "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
                "SBIN", "BAJFINANCE", "LT", "WIPRO", "SUNPHARMA",
                "TITAN", "MARUTI"
            ]
            results, fb_diagnostic = _build_yfinance_fallback_earnings(fallback_tickers, now_iso)
            if results:
                data_source = "yfinance_fallback"
            else:
                data_source = "empty"
                diagnostic = fb_diagnostic

        # Sort by category
        if sort == "best_performer":
            results.sort(key=lambda x: x.get("net_profit_growth_pct", 0), reverse=True)
        elif sort == "worst_performer":
            results.sort(key=lambda x: x.get("net_profit_growth_pct", 0))
        # "latest" keeps default order (most recent first)

        response: dict = {
            "sort": sort,
            "latest": results[:30],
            "best_performers": sorted(results, key=lambda x: x.get("net_profit_growth_pct", 0), reverse=True)[:10],
            "worst_performers": sorted(results, key=lambda x: x.get("net_profit_growth_pct", 0))[:10],
            "results": results[:30],
            "count": len(results[:30]),
            "data_source": data_source,
            "fetched_at": now_iso,
        }
        if diagnostic:
            response["diagnostic"] = diagnostic
        return response

    except Exception as e:
        log_earnings_error("earnings_feed", str(e))
        logging.exception("[EARNINGS/FEED] failed")
        return {
            "sort": sort, "latest": [], "best_performers": [], "worst_performers": [],
            "results": [], "count": 0, "data_source": "empty",
            "error": "Earnings feed temporarily unavailable",
            "diagnostic": "Earnings feed failed to load. Please retry shortly.",
            "fetched_at": now_iso, "degraded": True,
        }


@router.get("/api/v1/earnings/calendar")
def earnings_calendar_day_endpoint(date: str = None, ticker: str = None):
    """
    Historical earnings calendar — returns results for a date with 7-day
price-action sparkline data per ticker. Pass ?ticker=SYM to filter.

Each result includes:
  - earnings metadata (ticker, revenue, profit, eps, etc.)
  - sparkline: list of 7 closing prices preceding the result date
  - price_change_7d_pct: % change over the 7-day window

    Args:
        date (str): The date.
        ticker (str): The ticker.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with get_session() as session:
            query = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date == target_date
            )
            if ticker:
                query = query.filter(AnalysisHistory.ticker == ticker.upper())
            rows = query.all()

            results = []
            for r in rows:
                item = _earnings_result_from_row(r, now_iso)
                # Fetch 7-day price history for sparkline
                sparkline: list[float] = []
                price_change_7d: float | None = None
                try:
                    from services.nse_data_provider import get_price_history
                    df = get_price_history(r.ticker, period_days=14)  # extra buffer
                    if df is not None and len(df) >= 2:
                        closes = df["Close"].dropna().tail(7).tolist()
                        sparkline = [round(float(c), 2) for c in closes]
                        if len(sparkline) >= 2:
                            price_change_7d = round((sparkline[-1] - sparkline[0]) / sparkline[0] * 100, 2)
                except Exception as price_err:
                    log_earnings_error("earnings_calendar_price", str(price_err), failed_ticker=r.ticker)

                item["sparkline"] = sparkline
                item["price_change_7d_pct"] = price_change_7d
                results.append(item)

        # Also scan upcoming earnings from yfinance for tickers without DB entries
        if not ticker and len(results) < 5:
            try:
                upcoming = _scan_upcoming_earnings(target_date)
                results.extend(upcoming)
            except Exception as scan_err:
                log_earnings_error("earnings_calendar_scan", str(scan_err))

        return {
            "date": target_date,
            "results": results,
            "count": len(results),
            "fetched_at": now_iso,
        }
    except Exception as e:
        log_earnings_error("earnings_calendar", str(e))
        logging.exception("[EARNINGS/CALENDAR] failed")
        return {"date": target_date, "results": [], "count": 0,
                "error": "Earnings calendar temporarily unavailable", "fetched_at": now_iso,
                "degraded": True}


@router.get("/api/v1/earnings/estimates")
def earnings_estimates_endpoint(ticker: str):
    # Only a genuine quarterly consensus figure counts as an estimate (FAKE-10):
    # no TTM-actual (totalRevenue) or 12-month-forward EPS stand-ins, and no
    # actuals from LLM analysis snapshots (period never matched the estimate).
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


@router.get("/api/v1/earnings/post-result-movers")
def post_result_movers_endpoint():
    now_iso = datetime.now(timezone.utc).isoformat()
    movers = []
    try:
        with get_session() as session:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
            rows = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date >= cutoff
            ).order_by(AnalysisHistory.created_at.desc()).all()
            seen: set = set()
            for r in rows:
                if r.ticker in seen or len(movers) >= 15:
                    continue
                seen.add(r.ticker)
                try:
                    ns = _to_ns(r.ticker)
                    t_obj = yf.Ticker(ns)
                    hist = t_obj.history(period="5d")
                    if hist.empty or len(hist) < 2:
                        continue
                    ltp = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[0])
                    change_pct = round((ltp - prev) / prev * 100, 2) if prev > 0 else 0.0
                    vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None
                    fj = json.loads(r.full_json or "{}")
                    movers.append({
                        "ticker": r.ticker,
                        "company_name": fj.get("company_name") or r.ticker,
                        "result_date": r.analysis_date or now_iso[:10],
                        "ltp": ltp,
                        "change_percent": change_pct,
                        "volume": vol,
                    })
                except Exception as e:
                    logging.warning(f"Caught exception: {e}")
                    continue
        movers.sort(key=lambda x: abs(x["change_percent"]), reverse=True)
        return {"movers": movers, "fetched_at": now_iso}
    except Exception:
        logging.exception("[EARNINGS/POST-RESULT-MOVERS] failed")
        return {"movers": [], "fetched_at": now_iso, "degraded": True}


class EarningsAlertCreateRequest(_BaseModelLocal):
    user_id: int
    ticker: str
    earnings_date: str


@router.get("/api/v1/earnings/alerts")
def earnings_alerts_get_endpoint(user_id: int = Depends(require_auth)):
    """
    Return the caller's earnings alerts (AUTH-10: bearer only, never another
    user's rows; ?user_id= is ignored). Returns empty list if none.

    Args:
        user_id (int): The authenticated user_id.

    Returns:
        Any: The response.
    """
    try:
        alerts = earnings_alerts_service.list_alerts(user_id)
        return {
            "alerts": alerts,
            "count": len(alerts),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log_market_error("earnings_alerts_get", str(e))
        logging.exception("[EARNINGS/ALERTS] list failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/v1/earnings/alerts")
def earnings_alerts_post_endpoint(body: EarningsAlertCreateRequest, user_id: int = Depends(require_auth)):
    """
    Create an earnings date alert for a user+ticker combination.
Deduplicates — if same user/ticker/date already exists, returns 200 with existing.

    Args:
        body (EarningsAlertCreateRequest): The body.
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    ticker = body.ticker.upper().strip()
    try:
        alert = earnings_alerts_service.create_alert(user_id, ticker, body.earnings_date)
        return {**alert, "fetched_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        log_market_error("earnings_alerts_post", str(e), context_ticker=ticker)
        logging.exception("[EARNINGS/ALERTS] create failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/v1/earnings/alerts/{alert_id}")
def earnings_alerts_delete_endpoint(alert_id: int, user_id: int = Depends(require_auth)):
    """
    Delete a specific earnings alert by ID. Verifies alert belongs to authenticated user.

    Args:
        alert_id (int): The alert_id.
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        if not earnings_alerts_service.delete_alert(user_id, alert_id):
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"deleted": True, "alert_id": alert_id, "fetched_at": datetime.now(timezone.utc).isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        log_market_error("earnings_alerts_delete", str(e))
        logging.exception("[EARNINGS/ALERTS] delete failed")
        raise HTTPException(status_code=500, detail="Internal server error")
