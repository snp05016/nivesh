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
    try:
        from jugaad_data.nse import stock_df
        test_df = stock_df(
            symbol="RELIANCE",
            from_date=date.today() - timedelta(days=7),
            to_date=date.today(),
            series="EQ",
        )
        _JUGAAD_AVAILABLE = len(test_df) > 0
        logger.info(f"[nse_data_provider] jugaad-data probe: {'OK' if _JUGAAD_AVAILABLE else 'FAILED (empty)'}")
    except Exception as e:
        _JUGAAD_AVAILABLE = False
        logger.info(f"[nse_data_provider] jugaad-data unavailable ({e}). Using yfinance only.")
    return _JUGAAD_AVAILABLE


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
        except Exception:
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
                    "CLOSE": "Close", "TOTTRDQTY": "Volume",
                })
                df = raw[["Open", "High", "Low", "Close", "Volume"]].sort_index()
                logger.info(f"[nse_data_provider] {ticker}: jugaad-data {len(df)} rows")
        except Exception as e:
            logger.warning(f"[nse_data_provider] {ticker}: jugaad-data failed: {e}")

    if df is None or len(df) < 10:
        try:
            import yfinance as yf
            suffix    = ".NS" if exchange == "NSE" else ".BO"
            yf_ticker = f"{ticker}{suffix}" if not ticker.endswith((".NS", ".BO")) else ticker
            df = yf.download(yf_ticker, period=f"{period_days}d", auto_adjust=True, progress=False)
            if (df is None or len(df) < 10) and exchange == "NSE":
                df = yf.download(f"{ticker}.BO", period=f"{period_days}d", auto_adjust=True, progress=False)
            logger.info(f"[nse_data_provider] {ticker}: yfinance {len(df) if df is not None else 0} rows")
        except Exception as e:
            logger.error(f"[nse_data_provider] {ticker}: yfinance also failed: {e}")
            return None

    if df is not None and len(df) > 0:
        cache_set("yfinance", cache_key, df.to_dict())

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
