"""Earnings routes: /earnings-calendar and /api/v1/earnings/*.

Split out of routers/market.py (ARCH-14); paths, handler names and tags are unchanged.
"""
from helpers import (
    _resolve_ticker, DataHarvestingError,
    require_auth, log_market_error, log_earnings_error,
)
from services import earnings_alerts_service
from services.market_service import (
    _scan_upcoming_earnings, earnings_universe_snapshot, get_earnings_estimates,
    recent_post_result_movers,
)
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


def _ticker_earnings_events(ticker_raw: str, today) -> _Optional[list]:
    """Upcoming/recent earnings events for one holding. Logs and returns None on
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
        return None


def _holding_tickers(user_id: int) -> list:
    from database import get_session, Portfolio
    with get_session() as session:
        return [t[0] for t in session.query(Portfolio.ticker).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings",
        ).distinct().all()]


def _compute_earnings_calendar(user_id: int) -> _Optional[dict]:
    """None when every holding's lookup failed, so the outage is not cached."""
    tickers = _holding_tickers(user_id)
    if not tickers:
        return {"events": []}
    today = datetime.now().date()
    with ThreadPoolExecutor(max_workers=8) as ex:
        per_ticker = list(ex.map(lambda t: _ticker_earnings_events(t, today), tickers))
    if all(events is None for events in per_ticker):
        return None
    results = [e for events in per_ticker if events for e in events]
    results.sort(key=lambda x: x["days_away"])
    return {"events": results}


@router.get("/earnings-calendar")
def earnings_calendar_endpoint(user_id: int = Depends(require_auth)):
    """
    Returns upcoming earnings dates for the caller's NSE holdings (CMKT-12:
    scoped to the token's user, never the union of every user's holdings).

    Single-flight cached per user for 15 min: concurrent misses compute once (PERF-10).

    Returns:
        Any: The response.
    """
    try:
        payload = cached_call("market", f"earnings_calendar_{user_id}",
                              lambda: _compute_earnings_calendar(user_id),
                              ttl=900, cache_if=lambda p: p is not None)
        return payload if payload is not None else {"events": []}
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


@router.get("/api/v1/earnings/feed")
def earnings_feed_endpoint(market_cap: str = "all", sort: str = "latest"):
    """
    Ranked earnings feed — returns results categorized by sort parameter:
  - "latest":      most recent quarter first (default)
  - "best_performer":   highest YoY net-profit growth
  - "worst_performer":  lowest YoY net-profit growth
Each result is a tracked large cap's latest quarter against the same quarter a year
earlier, from yfinance quarterly financials (CMKT-01). AI analyses are never read as
results; a company without a real prior-year quarter is left out.

    Args:
        market_cap (str): The market_cap.
        sort (str): The sort.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    def _profit_growth(item: dict) -> float:
        return item.get("net_profit_growth_pct") or 0

    try:
        snapshot = earnings_universe_snapshot()
        results = list(snapshot["results"])
        diagnostic = None if results else snapshot.get("diagnostic")
        if diagnostic:
            log_earnings_error("earnings_feed", diagnostic)

        # Sort by category
        if sort == "best_performer":
            results.sort(key=_profit_growth, reverse=True)
        elif sort == "worst_performer":
            results.sort(key=_profit_growth)
        # "latest" keeps the snapshot order (newest quarter first)

        response: dict = {
            "sort": sort,
            "latest": results[:30],
            "best_performers": sorted(results, key=_profit_growth, reverse=True)[:10],
            "worst_performers": sorted(results, key=_profit_growth)[:10],
            "results": results[:30],
            "count": len(results[:30]),
            "data_source": "yfinance" if results else "empty",
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
    Earnings calendar — companies whose yfinance earnings date falls within 3 days of
the date (default today). Pass ?ticker=SYM to look up one company. AI analysis dates
are never listed as result dates (CMKT-01).

    Args:
        date (str): The date.
        ticker (str): The ticker.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        results = _scan_upcoming_earnings(target_date, tickers=[ticker.upper()] if ticker else None)
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
    return get_earnings_estimates(ticker)


@router.get("/api/v1/earnings/post-result-movers")
def post_result_movers_endpoint():
    # Tracked large caps that announced results in the last 14 days (yfinance earnings
    # dates), never the tickers someone ran an AI analysis on (CMKT-01).
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        return {"movers": recent_post_result_movers(), "fetched_at": now_iso}
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
