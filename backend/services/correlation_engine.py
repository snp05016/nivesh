import numpy as np
import pandas as pd
import yfinance as yf
from collections import defaultdict
import logging
import threading
import time

logger = logging.getLogger(__name__)

SECTOR_PROXIES = {
    "IT": "^CNXIT",
    "Banking": "^NSEBANK",
    "FMCG": "^CNXFMCG",
    "Pharma": "^CNXPHARMA",
    "Auto": "^CNXAUTO",
    "Metal": "^CNXMETAL",
    "Energy": "^CNXENERGY",
    "Realty": "^CNXREALTY",
    "Infra": "^CNXINFRA",
    "Gold": "GOLDBEES.NS",
    "Nifty 50": "^NSEI",
}

_sector_cache: dict = {}
_sector_cache_lock = threading.Lock()
_SECTOR_CACHE_TTL = 3600


def _get_cached_sector(ticker: str) -> str | None:
    now = time.time()
    with _sector_cache_lock:
        entry = _sector_cache.get(ticker)
        if entry is not None:
            cached_value, cached_time = entry
            if now - cached_time < _SECTOR_CACHE_TTL:
                return cached_value
    return None


def _set_cached_sector(ticker: str, sector: str) -> None:
    with _sector_cache_lock:
        _sector_cache[ticker] = (sector, time.time())


def _fetch_sector(ticker: str) -> str:
    cached = _get_cached_sector(ticker)
    if cached is not None:
        return cached
    try:
        info = yf.Ticker(format_ticker_for_yf(ticker)).info
        sector = info.get("sector", "Unknown") or "Unknown"
    except Exception:
        sector = "Unknown"
    _set_cached_sector(ticker, sector)
    return sector


def format_ticker_for_yf(ticker: str) -> str:
    if ticker.startswith("^") or ticker.endswith(".NS"):
        return ticker
    return f"{ticker}.NS"



def _extract_close(
    data: pd.DataFrame, names: list[str], yf_tickers: list[str]
) -> pd.DataFrame:
    prices = pd.DataFrame()
    if data.empty:
        return prices
    for name, yf_t in zip(names, yf_tickers):
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ("Close", yf_t) in data.columns:
                    prices[name] = data[("Close", yf_t)]
            else:
                close_candidate = None
                for col in data.columns:
                    col_str = str(col)
                    if yf_t in col_str and col_str.lower().startswith("close"):
                        close_candidate = col
                        break
                if close_candidate is not None:
                    prices[name] = data[close_candidate]
                elif yf_t in data.columns:
                    prices[name] = data[yf_t]
        except Exception:
            logger.warning("Could not extract Close price for %s (%s)", name, yf_t)
    return prices


def _extract_proxy_close(data: pd.DataFrame) -> pd.DataFrame:
    prices = pd.DataFrame()
    if data.empty:
        return prices
    for proxy_name, proxy_ticker in SECTOR_PROXIES.items():
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ("Close", proxy_ticker) in data.columns:
                    prices[proxy_name] = data[("Close", proxy_ticker)]
            else:
                close_candidate = None
                for col in data.columns:
                    col_str = str(col)
                    if proxy_ticker in col_str and col_str.lower().startswith("close"):
                        close_candidate = col
                        break
                if close_candidate is not None:
                    prices[proxy_name] = data[close_candidate]
                elif proxy_ticker in data.columns:
                    prices[proxy_name] = data[proxy_ticker]
        except Exception:
            logger.warning("Could not extract Close price for proxy %s (%s)", proxy_name, proxy_ticker)
    return prices


def _empty_result() -> dict:
    return {
        "correlation_matrix": [],
        "diversification_score": 0,
        "sector_concentration": [],
        "suggestions": [],
    }


def compute_portfolio_correlation(holdings: list) -> dict:
    if not holdings:
        return _empty_result()

    tickers = list(set(h.ticker for h in holdings))
    all_ticker_names = tickers + ["^NSEI"]
    all_yf_tickers = [format_ticker_for_yf(t) for t in all_ticker_names]

    proxy_yf_tickers = list(SECTOR_PROXIES.values())

    try:
        data = yf.download(
            all_yf_tickers, period="6mo", interval="1d",
            threads=True, progress=False
        )
    except Exception as e:
        logger.error("Error fetching holding data: %s", e)
        raise

    try:
        proxy_data = yf.download(
            proxy_yf_tickers, period="6mo", interval="1d",
            threads=True, progress=False
        )
    except Exception as e:
        logger.warning("Error fetching proxy data: %s", e)
        proxy_data = pd.DataFrame()

    prices = _extract_close(data, all_ticker_names, all_yf_tickers)
    proxy_prices = _extract_proxy_close(proxy_data)

    portfolio_tickers = [t for t in tickers if t in prices.columns]
    if not portfolio_tickers:
        return _empty_result()

    holding_returns = pd.DataFrame(index=prices.index)
    total_val = sum(h.shares * h.buy_price for h in holdings)

    ticker_weights: dict[str, float] = defaultdict(float)
    for h in holdings:
        if total_val > 0:
            ticker_weights[h.ticker] += (h.shares * h.buy_price) / total_val

    for t in portfolio_tickers:
        holding_returns[t] = prices[t].pct_change()

    portfolio_return = pd.Series(0.0, index=holding_returns.index)
    for t in portfolio_tickers:
        if t in ticker_weights:
            portfolio_return += ticker_weights[t] * holding_returns[t]

    returns = prices.pct_change()
    corr_df = returns.corr()

    correlation_list = []
    cols = prices.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            corr_val = corr_df.iloc[i, j]
            if not np.isnan(corr_val):
                correlation_list.append([cols[i], cols[j], round(float(corr_val), 3)])

    ticker_sectors: dict[str, str] = {}
    for t in tickers:
        ticker_sectors[t] = _fetch_sector(t)

    sector_weights: dict[str, float] = defaultdict(float)
    sector_holdings: dict[str, list] = defaultdict(list)
    for h in holdings:
        sec = ticker_sectors.get(h.ticker, "Unknown")
        w = (h.shares * h.buy_price) / total_val if total_val > 0 else 0
        sector_weights[sec] += w
        sector_holdings[sec].append(h.ticker)

    sector_concentration = []
    for sec, w in sector_weights.items():
        sector_concentration.append({
            "sector": sec,
            "weight_pct": round(w * 100, 2),
            "holdings": list(set(sector_holdings[sec])),
        })
    sector_concentration.sort(key=lambda x: x["weight_pct"], reverse=True)

    holding_corrs = []
    for item in correlation_list:
        t1, t2, corr = item
        if t1 != "^NSEI" and t2 != "^NSEI":
            holding_corrs.append(corr)

    avg_corr = np.mean(holding_corrs) if holding_corrs else 0.0
    if np.isnan(avg_corr):
        avg_corr = 0.0

    unique_sectors = len([s for s in sector_weights if s != "Unknown"])
    sector_diversity_bonus = min(1.0, 0.5 + (unique_sectors * 0.1))
    corr_factor = 1.0 - max(0.0, avg_corr)
    div_score = round(corr_factor * sector_diversity_bonus * 100)
    div_score = max(0, min(100, div_score))

    suggestions: list[dict] = []
    portfolio_clean = portfolio_return.dropna()
    if len(portfolio_clean) < 10 or proxy_prices.empty:
        return {
            "correlation_matrix": correlation_list,
            "diversification_score": div_score,
            "sector_concentration": sector_concentration,
            "suggestions": suggestions,
        }

    proxy_returns = proxy_prices.pct_change()

    portfolio_vol_daily = float(np.std(portfolio_clean))
    portfolio_vol_pct = portfolio_vol_daily * np.sqrt(252) * 100

    suggestions_raw = []
    for proxy_name in proxy_returns.columns:
        proxy_col = proxy_returns[proxy_name].dropna()
        if len(proxy_col) < 10:
            continue

        combined = pd.concat([portfolio_return, proxy_returns[proxy_name]], axis=1)
        combined.columns = ["portfolio", "proxy"]
        corr = combined.corr().iloc[0, 1]
        if np.isnan(corr):
            continue

        var_portfolio = float(np.var(portfolio_clean))
        var_proxy = float(np.var(proxy_col))
        cov = float(corr * np.std(portfolio_clean) * np.std(proxy_col))

        var_new = 0.81 * var_portfolio + 0.01 * var_proxy + 0.18 * cov
        if var_new <= 0:
            continue

        new_vol_daily = float(np.sqrt(var_new))
        new_vol_pct = new_vol_daily * np.sqrt(252) * 100
        vol_reduction = portfolio_vol_pct - new_vol_pct

        suggestions_raw.append({
            "proxy_name": proxy_name,
            "vol_reduction": vol_reduction,
            "correlation": float(corr),
            "new_volatility": float(new_vol_pct),
        })

    suggestions_raw.sort(key=lambda x: x["vol_reduction"], reverse=True)

    for s in suggestions_raw[:3]:
        suggestions.append({
            "sector": s["proxy_name"],
            "reason": (
                f"Based on covariance math, your portfolio has {portfolio_vol_pct:.1f}% "
                f"volatility. Adding {s['proxy_name']} (correlation: {s['correlation']:.2f}) "
                f"would reduce total volatility to {s['new_volatility']:.1f}%."
            ),
            "improvement_score": round(max(0, min(100, 50 + s["vol_reduction"] * 10))),
        })

    return {
        "correlation_matrix": correlation_list,
        "diversification_score": div_score,
        "sector_concentration": sector_concentration,
        "suggestions": suggestions,
    }
