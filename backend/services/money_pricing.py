"""Prices for money features: current quotes for stocks and funds, and a past day's close.

Stocks use FIX SILENT-01's _yf_price_with_status (live | stale last-good |
unavailable); funds use the AMFI NAV through money_mf_meta (nav when at most 4
weekdays old, stale up to 7 days, else unavailable). close_on() serves the
edit-restart rule of the XIRR flow builder (spec 3.3).
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

import yfinance as yf

from core.timeutil import ist_today
from services import disk_cache, money_mf_meta
from services import yfinance_client as yfc

logger = logging.getLogger(__name__)

_CLOSE_TTL = 30 * 86400


@dataclass(frozen=True)
class PriceQuote:
    price: Optional[float]
    prev_close: Optional[float]
    status: str  # live | stale | nav | unavailable
    as_of: Optional[str]  # ISO timestamp (stocks) or date (NAV)


UNAVAILABLE = PriceQuote(None, None, "unavailable", None)


def _eq_quote(ticker: str) -> PriceQuote:
    try:
        price, prev, status, as_of = yfc._yf_price_with_status(yfc._to_ns(ticker))
    except Exception as e:  # one bad symbol must not fail the batch
        logger.info("[money_pricing] quote failed for %s: %s", ticker, type(e).__name__)
        return UNAVAILABLE
    if not price:
        return UNAVAILABLE
    return PriceQuote(float(price), float(prev) if prev else None, status, as_of)


def _weekdays_between(start: date, end: date) -> int:
    """Weekdays after `start` up to and including `end`."""
    return sum(1 for i in range(1, (end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5)


def nav_status(nav_date: Optional[date], today: Optional[date] = None) -> str:
    if nav_date is None:
        return "unavailable"
    today = today or ist_today()
    if nav_date >= today or _weekdays_between(nav_date, today) <= 4:
        return "nav"
    return "stale" if (today - nav_date).days <= 7 else "unavailable"


def price_quotes(rows: list[tuple[str, str]]) -> dict[str, PriceQuote]:
    """{ticker: PriceQuote} for (ticker, asset_class) rows; MF tickers are ISINs."""
    out: dict[str, PriceQuote] = {}
    eq = sorted({t for t, ac in rows if ac != "MF"})
    mf = sorted({t for t, ac in rows if ac == "MF"})
    if eq:
        with ThreadPoolExecutor(max_workers=min(len(eq), 10)) as pool:
            out.update(zip(eq, pool.map(_eq_quote, eq)))
    if mf:
        info = money_mf_meta.scheme_info(mf)
        today = ist_today()
        for isin in mf:
            s = info.get(isin)
            status = nav_status(s.nav_date, today) if s and s.nav else "unavailable"
            if s is None or s.nav is None or status == "unavailable":
                out[isin] = UNAVAILABLE
            else:
                out[isin] = PriceQuote(s.nav, None, status, s.nav_date.isoformat() if s.nav_date else None)
    return out


def close_on(ticker: str, d: date) -> Optional[float]:
    """Last daily close on or before `d` (within 10 days); None when unknown.

    Past days are cached for 30 days; today's close can still change, so it is not.
    """
    key = f"{ticker.upper()}:{d.isoformat()}"
    cached = disk_cache.get("money_close", key)
    if cached is not None:
        return float(cached)
    try:
        if not yfc._yf_guard():
            return None
        hist: Any = yf.Ticker(yfc._to_ns(ticker)).history(
            start=(d - timedelta(days=10)).isoformat(), end=(d + timedelta(days=1)).isoformat()
        )
        if hist is None or bool(hist.empty):
            return None
        closes = [
            float(c) for ts, c in hist["Close"].items()
            if ts.date() <= d and c is not None and math.isfinite(float(c)) and float(c) > 0
        ]
    except Exception as e:
        logger.info("[money_pricing] close unavailable for %s on %s: %s", ticker, d, type(e).__name__)
        return None
    if not closes:
        return None
    close = closes[-1]
    if d < ist_today():
        disk_cache.set("money_close", key, close, ttl=_CLOSE_TTL)
    return close
