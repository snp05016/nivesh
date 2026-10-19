from config.settings import get_user_agent
"""
Nivesh NSE Data Provider
-------------------------
Unified abstraction layer for NSE/BSE market data.

Source priority:
  1. jugaad-data — Direct NSE access (probed at module load)
  2. yfinance — Fallback. Never removed from codebase.

RULE: Agents should import from this module, not yfinance directly.
      Swapping data sources only requires changes here.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from services.disk_cache import get as cache_get, set as cache_set

logger = logging.getLogger(__name__)

_JUGAAD_AVAILABLE = False


def _probe_jugaad() -> bool:
    global _JUGAAD_AVAILABLE
    _JUGAAD_AVAILABLE = False
    logger.info("[nse_data_provider] jugaad-data is permanently disabled (fixes #449)")
    return False


_probe_jugaad()


def get_price_history(
    ticker: str,
    period_days: int = 365,
    exchange: str = "NSE",
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV price history. Disk-cached. jugaad-data primary, yfinance fallback.
    """
    cache_key = f"{ticker}_history_{period_days}d"
    cached = cache_get("yfinance", cache_key)
    if cached:
        try:
            df = pd.DataFrame(cached)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as _e:
            pass

    df = None

    if _JUGAAD_AVAILABLE and exchange == "NSE":
        try:
            from jugaad_data.nse import stock_df
            end_date   = date.today()
            start_date = end_date - timedelta(days=period_days)
            raw = stock_df(symbol=ticker, from_date=start_date, to_date=end_date, series="EQ")
            if raw is not None and len(raw) > 10:
                raw = raw.rename(columns={
                    "OPEN": "Open", "HIGH": "High", "LOW": "Low",
                    "CLOSE": "Close", "TOTTRDQTY": "Volume", "VOLUME": "Volume"
                })
                df = raw[["Open", "High", "Low", "Close", "Volume"]].sort_index()
                logger.info(f"[nse_data_provider] {ticker}: jugaad-data {len(df)} rows")
        except Exception as e:
            logger.warning(f"[nse_data_provider] {ticker}: jugaad-data failed: {e}")

    data_source = "jugaad-data"  # primary, fresh
    stale_data_flag = False

    if df is None or len(df) < 10:
        # Fix 2.4: jugaad-data may be unavailable on market holidays —
        # yfinance fallback data is flagged as potentially stale
        data_source = "yfinance-fallback"
        stale_data_flag = True
        try:
            import yfinance as yf
            suffix    = ".NS" if exchange == "NSE" else ".BO"
            yf_ticker = f"{ticker}{suffix}" if not ticker.endswith((".NS", ".BO")) else ticker
            df = yf.download(yf_ticker, period=f"{period_days}d", auto_adjust=True, progress=False)
            if (df is None or len(df) < 10) and exchange == "NSE":
                df = yf.download(f"{ticker}.BO", period=f"{period_days}d", auto_adjust=True, progress=False)
            if df is not None and isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            logger.info(f"[nse_data_provider] {ticker}: yfinance {len(df) if df is not None else 0} rows")
        except Exception as e:
            logger.error(f"[nse_data_provider] {ticker}: yfinance also failed: {e}")
            return None

    if df is not None and len(df) > 0:
        df_for_cache = df.copy()
        df_for_cache.index = df_for_cache.index.astype(str)
        cache_set("yfinance", cache_key, df_for_cache.to_dict())

    # Attach metadata for downstream stale-data awareness
    if df is not None:
        df.attrs["data_source"] = data_source
        df.attrs["stale_data_flag"] = stale_data_flag

    return df


def get_fundamentals(ticker: str, exchange: str = "NSE") -> dict:
    """
    Fetch fundamental data. Disk-cached 6h. Returns normalized dict.
    """
    cache_key = f"{ticker}_fundamentals"
    cached = cache_get("yfinance", cache_key)
    if cached:
        return cached

    result = {
        "ticker": ticker,
        "pe_ratio": None,
        "pb_ratio": None,
        "eps_ttm": None,
        "revenue_ttm": None,
        "debt_to_equity": None,
        "roe": None,
        "promoter_pledging_pct": None,
        "market_cap": None,
        "dividend_yield": None,
        "source": "unknown",
    }

    try:
        import yfinance as yf
        suffix    = ".NS" if exchange == "NSE" else ".BO"
        yf_ticker = f"{ticker}{suffix}" if not ticker.endswith((".NS", ".BO")) else ticker
        info = yf.Ticker(yf_ticker).info
        if not info or info.get("regularMarketPrice") is None:
            info = yf.Ticker(f"{ticker}.BO").info
        if info:
            result.update({
                "pe_ratio":       info.get("trailingPE"),
                "pb_ratio":       info.get("priceToBook"),
                "eps_ttm":        info.get("trailingEps"),
                "revenue_ttm":    info.get("totalRevenue"),
                "debt_to_equity": info.get("debtToEquity"),
                "roe":            info.get("returnOnEquity"),
                "market_cap":     info.get("marketCap"),
                "dividend_yield": info.get("dividendYield"),
                "source":         "yfinance",
            })
    except Exception as e:
        logger.warning(f"[nse_data_provider] {ticker}: fundamentals fetch failed: {e}")

    cache_set("yfinance", cache_key, result)
    return result


# ── Low-level yfinance helpers ──────────────────────────────────────────────
# One resolver, one info/price fetcher: re-exported from services.yfinance_client
# so they share its rate limiter, circuit breaker and resolution cache (ARCH-11).
from services.yfinance_client import (  # noqa: E402,F401
    EXCHANGE_SUFFIX,
    _resolve_ticker as resolve_ticker,
    _yf_fetch_info as fetch_info,
    _yf_price as fetch_price,
    _to_ns as to_ns,
)


def get_delivery_data(symbol: str, days: int = 10) -> dict:
    """
    Fetch NSE delivery percentage for a symbol — GAP 3 signal.
    Tries NSE quote-equity API first; falls back to jugaad-data bhavcopy.
    Returns delivery signal with confidence modifier.
    """
    import requests

    headers = {
        "User-Agent": get_user_agent(),
        "Referer": "https://www.nseindia.com",
    }

    delivery_pct_latest = None
    delivery_pct_5d_avg = None

    # ── Attempt 1: NSE quote-equity API ───────────────────────────────────────
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}&section=trade_info"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            security_info = data.get("securityInfo", {})
            delivery_pct_latest = security_info.get("deliveryPercentage")
            weekly = data.get("weeklyDeliveryData", {})
            if weekly and "deliveryPercentage" in weekly:
                values = weekly["deliveryPercentage"]
                if isinstance(values, list) and len(values) >= 5:
                    delivery_pct_5d_avg = sum(float(v or 0) for v in values[-5:]) / 5
            elif delivery_pct_latest is not None:
                delivery_pct_5d_avg = delivery_pct_latest
    except Exception as e:
        logger.warning(f"[nse_data_provider] NSE quote-equity API failed for {symbol}: {e}")

    # ── Attempt 2: jugaad-data bhavcopy ──────────────────────────────────────
    if delivery_pct_latest is None and _JUGAAD_AVAILABLE:
        try:
            from jugaad_data.nse import stock_df
            from datetime import date, timedelta

            end_date = date.today()
            start_date = end_date - timedelta(days=days * 2)
            df = stock_df(symbol=symbol, from_date=start_date, to_date=end_date, series="EQ")
            if df is not None and len(df) > 0:
                if "DELIVERY_PERC" in df.columns:
                    values = df["DELIVERY_PERC"].dropna().tail(days)
                    if len(values) > 0:
                        delivery_pct_latest = float(values.iloc[-1])
                        window = values.tail(min(5, len(values)))
                        delivery_pct_5d_avg = float(window.mean())
                elif "DELIVERY_QTY" in df.columns and "TOTTRDQTY" in df.columns:
                    recent = df.tail(days)
                    pcts = []
                    for _, row in recent.iterrows():
                        tot = row.get("TOTTRDQTY", 0) or 0
                        dq = row.get("DELIVERY_QTY", 0) or 0
                        if tot > 0:
                            pcts.append(float(dq) / float(tot) * 100)
                    if pcts:
                        delivery_pct_latest = pcts[-1]
                        window = pcts[-5:] if len(pcts) >= 5 else pcts
                        delivery_pct_5d_avg = sum(window) / len(window)
        except Exception as e:
            logger.warning(f"[nse_data_provider] jugaad-data delivery failed for {symbol}: {e}")

    # ── Determine price trend ────────────────────────────────────────────────
    price_rising = None
    try:
        hist = get_price_history(symbol, period_days=20)
        if hist is not None and len(hist) >= 5:
            price_rising = float(hist["Close"].iloc[-1]) > float(hist["Close"].iloc[-5])
    except Exception as e:
        logger.warning(f"[nse_data_provider] price trend check failed for {symbol}: {e}")

    # ── Apply signal rules ──────────────────────────────────────────────────
    delivery_signal = "NEUTRAL"
    delivery_confidence_modifier = 0.0

    if delivery_pct_latest is not None and price_rising is not None:
        if delivery_pct_latest > 60 and price_rising:
            delivery_signal = "ACCUMULATION"
            delivery_confidence_modifier = 5.0
        elif delivery_pct_latest < 25 and price_rising:
            delivery_signal = "DISTRIBUTION"
            delivery_confidence_modifier = -10.0

    return {
        "delivery_pct_latest": delivery_pct_latest,
        "delivery_pct_5d_avg": delivery_pct_5d_avg,
        "delivery_signal": delivery_signal,
        "delivery_confidence_modifier": delivery_confidence_modifier,
    }


# ── Concurrency utility: batch fetch price_history + fundamentals + delivery ────

def batch_fetch_all(ticker: str, exchange: str = "NSE", period_days: int = 365) -> dict:
    """
    Fetch price_history, fundamentals, and delivery_data in parallel.
    Collapses ~12s of sequential yfinance/jugaad calls into ~4s (the slowest fetch).

    Returns a dict with keys: ticker, exchange, price_history, fundamentals, delivery.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result = {"ticker": ticker, "exchange": exchange}

    def _history():
        return get_price_history(ticker, period_days, exchange)

    def _fundamentals():
        return get_fundamentals(ticker, exchange)

    def _delivery():
        return get_delivery_data(ticker, days=10)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_history): "price_history",
            pool.submit(_fundamentals): "fundamentals",
            pool.submit(_delivery): "delivery",
        }
        for f in as_completed(futures):
            result[futures[f]] = f.result()

    return result


def batch_fetch_history_only(tickers: list[str], period_days: int = 365, exchange: str = "NSE") -> dict[str, any]:
    """
    Fetch price history for multiple tickers in parallel.
    Useful for portfolio views that need N stocks' charts simultaneously.

    Returns dict keyed by ticker.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(tickers), 16)) as pool:
        futures = {pool.submit(get_price_history, t, period_days, exchange): t for t in tickers}
        for f in as_completed(futures):
            ticker_key = futures[f]
            results[ticker_key] = f.result()
    return results
