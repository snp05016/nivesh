"""
portfolio_service.py — Pure business/data logic extracted from routers/portfolio.py.

Controller-Service-Repository contract (AGENTS.md §3.1):
  - This file contains ONLY pure computation, data-fetching, and caching logic.
  - NO get_session() calls.  DB access stays in the router.
  - NO FastAPI / HTTP concerns (no Request, Response, HTTPException, Header).
"""

from __future__ import annotations

import logging
import math
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import yfinance as yf

from config.settings import get_user_agent
from config.settings import INDICES_CACHE_TTL as _INDICES_CACHE_TTL
from config.settings import ASM_GSM_CACHE_TTL as _ASM_GSM_CACHE_TTL
from helpers import _dcache_get, _dcache_set


# ---------------------------------------------------------------------------
# Corporate-actions helpers
# ---------------------------------------------------------------------------

def _adjust_for_splits(ticker: str, buy_price: float, quantity: float, buy_date: str) -> tuple:
    """Fix 2.44: Adjust historical buy_price and quantity for corporate splits.

    Uses yfinance split history. Returns (adjusted_buy_price, adjusted_quantity, split_ratio).
    """
    try:
        t = yf.Ticker(f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker)
        splits = t.splits
        if splits is None or len(splits) == 0:
            return buy_price, quantity, 1.0
        buy_dt = datetime.strptime(buy_date[:10], "%Y-%m-%d")
        cumulative_ratio = 1.0
        for split_date, ratio in splits.items():
            if split_date > buy_dt:
                cumulative_ratio *= ratio
        if cumulative_ratio != 1.0:
            return buy_price / cumulative_ratio, quantity * cumulative_ratio, cumulative_ratio
        return buy_price, quantity, 1.0
    except Exception as e:
        logging.warning(f"[corporate-actions] _adjust_for_splits failed for {ticker}: {e}")
        return buy_price, quantity, 1.0


def _adjust_for_bonus(ticker: str, buy_price: float, quantity: float, buy_date: str) -> tuple:
    """Adjust historical buy_price and quantity for corporate bonus issues.

    Uses yfinance actions DataFrame (Dividends & Stock Splits).
    Returns (adjusted_buy_price, adjusted_quantity, cumulative_ratio).
    """
    try:
        import pandas as pd
        t = yf.Ticker(f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker)
        actions = t.actions
        if actions is None or actions.empty or "Stock Splits" not in actions.columns:
            return buy_price, quantity, 1.0

        buy_dt = pd.to_datetime(buy_date[:10]).tz_localize(None)
        cumulative_ratio = 1.0

        for action_date, row in actions.iterrows():
            dt = action_date
            if hasattr(dt, "tz_localize") and dt.tzinfo is not None:
                dt = dt.tz_localize(None)
            if dt > buy_dt:
                split = float(row.get("Stock Splits", 0.0))
                if split > 0:
                    cumulative_ratio *= split

        if cumulative_ratio != 1.0:
            return buy_price / cumulative_ratio, quantity * cumulative_ratio, cumulative_ratio
        return buy_price, quantity, 1.0
    except Exception as e:
        logging.warning(f"[corporate-actions] _adjust_for_bonus failed for {ticker}: {e}")
        return buy_price, quantity, 1.0


def _apply_corporate_actions(ticker: str, buy_price: float, quantity: float, buy_date: str) -> tuple:
    """Adjustment pipeline that applies both splits and bonus issues."""
    bp1, q1, _ = _adjust_for_splits(ticker, buy_price, quantity, buy_date)
    bp2, q2, _ = _adjust_for_bonus(ticker, bp1, q1, buy_date)
    return bp2, q2, (quantity / q2) if q2 > 0 else 1.0


# ---------------------------------------------------------------------------
# Market-indices data
# ---------------------------------------------------------------------------

_INDICES_TICKERS = [
    ("^NSEI",      "Nifty 50"),
    ("^BSESN",     "Sensex"),
    ("^NSEBANK",   "Nifty Bank"),
    ("^CNXIT",     "Nifty IT"),
    ("^NSEMDCP50", "Nifty Midcap 100"),
    ("USDINR=X",   "USD/INR"),
]


def _get_indices_data() -> dict:
    """Fetch and cache market indices data via Redis (shared across all workers)."""
    cached = _dcache_get("indices", "all")
    if cached is not None:
        return cached

    result = []
    for ticker, name in _INDICES_TICKERS:
        try:
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
                    logging.info(f"[YF] Indices attempt {attempt+1} failed for {ticker}: {e}")
                    if attempt < 2:
                        time.sleep((1.0 * (2 ** attempt)) + (random.random() * 0.2))

            if current is None or math.isnan(current):
                continue

            change_abs = round(current - (prev_close or 0), 4)
            change_pct = round((change_abs / prev_close) * 100, 4) if prev_close else 0.0
            result.append({
                "name": name,
                "ticker": ticker,
                "value": round(float(current), 4),
                "change_pct": change_pct,
                "change_abs": change_abs,
            })
        except Exception as e:
            logging.info(f"[indices] Skipping {ticker}: {e}")
            continue

    payload = {
        "indices": result,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _dcache_set("indices", "all", payload, ttl=_INDICES_CACHE_TTL)
    return payload


# ---------------------------------------------------------------------------
# NSE client helpers
# ---------------------------------------------------------------------------

def _nse_session():
    """Bootstrap a requests.Session with NSE cookies."""
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": get_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=8)
    except Exception as _e:
        pass
    return s


def _get_asm_gsm_lists() -> dict:
    """Fetch and cache ASM/GSM lists from NSE (Redis-backed, shared across workers)."""
    cached = _dcache_get("asm_gsm", "lists")
    if cached is not None:
        return cached

    logging.info("[NSE] Refreshing ASM/GSM lists...")
    data: dict[str, set] = {"ASM": set(), "GSM": set()}
    try:
        session = _nse_session()

        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=longTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym:
                    data["ASM"].add(sym.upper())

        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=shortTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym:
                    data["ASM"].add(sym.upper())

        resp = session.get("https://www.nseindia.com/api/surveillance-gsm-list", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym:
                    data["GSM"].add(sym.upper())

        redis_data = {"ASM": sorted(data["ASM"]), "GSM": sorted(data["GSM"])}
        _dcache_set("asm_gsm", "lists", redis_data, ttl=_ASM_GSM_CACHE_TTL)
        return data  # return sets for in-memory callers
    except Exception as e:
        logging.info(f"[NSE] ASM/GSM fetch failed: {e}")
        return data


# ---------------------------------------------------------------------------
# Risk-label utility
# ---------------------------------------------------------------------------

def _risk_label(score: Optional[int]) -> str:
    """Convert numeric risk score (1–10) to human-readable label."""
    if score is None:
        return "Unknown"
    if score <= 3:
        return "Low"
    if score <= 6:
        return "Moderate"
    if score <= 8:
        return "High"
    return "Very High"


# ---------------------------------------------------------------------------
# SIP calculator (pure financial mathematics)
# ---------------------------------------------------------------------------

def compute_sip(
    monthly_amount: float,
    expected_return_pct: float,
    years: int,
    step_up_pct: float = 0.0,
) -> dict:
    """Run the SIP compounding loop and return summary + yearly projections.

    Args:
        monthly_amount: Starting monthly SIP amount in INR.
        expected_return_pct: Annual expected return percentage (e.g. 12.0 for 12%).
        years: Investment horizon in years.
        step_up_pct: Annual step-up percentage applied at the end of each year.

    Returns:
        dict with keys: inputs, summary, yearly_projections.
    """
    monthly_rate = expected_return_pct / 100.0 / 12.0
    months = years * 12

    total_invested = 0.0
    current_corpus = 0.0
    current_sip = monthly_amount
    yearly_projections = []

    for month in range(1, months + 1):
        total_invested += current_sip
        current_corpus = (current_corpus + current_sip) * (1 + monthly_rate)

        if month % 12 == 0:
            year = month // 12
            yearly_projections.append({
                "year": year,
                "invested_lakhs": round(total_invested / 100000.0, 2),
                "corpus_lakhs": round(current_corpus / 100000.0, 2),
                "gain_lakhs": round((current_corpus - total_invested) / 100000.0, 2),
            })
            current_sip = current_sip * (1 + step_up_pct / 100.0)

    summary = {
        "total_invested_lakhs": round(total_invested / 100000.0, 2),
        "total_corpus_lakhs": round(current_corpus / 100000.0, 2),
        "total_gain_lakhs": round((current_corpus - total_invested) / 100000.0, 2),
    }
    return {
        "summary": summary,
        "yearly_projections": yearly_projections,
    }


# ---------------------------------------------------------------------------
# Stress-test helpers (sector mapping + scenario math)
# ---------------------------------------------------------------------------

def get_stress_sector(company_name: str) -> str:
    """Map a company name to a broad sector for stress-test scenarios."""
    if not company_name:
        return "Other"
    name = company_name.lower()
    if any(x in name for x in ["infosys", "tcs", "wipro", "tech", "software", "hcl"]):
        return "IT"
    if any(x in name for x in ["bank", "hdfc", "icici", "kotak", "sbi"]):
        return "Banking"
    if any(x in name for x in ["fmcg", "itc", "nestle", "brit", "hindustan unilever", "hul"]):
        return "FMCG"
    if any(x in name for x in ["auto", "tata motors", "maruti", "mahindra", "bajaj auto"]):
        return "Auto"
    if any(x in name for x in ["pharma", "sun", "cipla", "dr reddy", "lupin"]):
        return "Pharma"
    if any(x in name for x in ["oil", "gas", "ongc", "reliance", "bpcl"]):
        return "Oil/Gas"
    if any(x in name for x in ["air", "aviation", "indigo"]):
        return "Aviation"
    if any(x in name for x in ["paint", "asian", "berger"]):
        return "Paints"
    if any(x in name for x in ["tyre", "mrf", "apolo"]):
        return "Tyres"
    return "Other"


# Scenario definitions: list of dicts with name, desc, and a callable impact(sector) -> float pct
STRESS_TEST_SCENARIOS = [
    {
        "name": "Nifty -20% Correction",
        "desc": "Market crash scenario",
        "impact": lambda sector: -20.0 * {"IT": 1.2, "Banking": 1.4, "FMCG": 0.6, "Auto": 1.1, "Pharma": 0.7}.get(sector, 1.0),
    },
    {
        "name": "INR Depreciates 10% vs USD",
        "desc": "Weak rupee scenario",
        "impact": lambda sector: +5.0 if sector in ("IT", "Pharma") else (-8.0 if sector == "Oil/Gas" else -1.0),
    },
    {
        "name": "Crude Oil Spikes to $120/bbl",
        "desc": "Energy shock scenario",
        "impact": lambda sector: -15.0 if sector in ("Aviation", "Paints", "Tyres") else (+8.0 if sector == "Oil/Gas" else -2.0),
    },
]


def compute_stress_test_results(holding_data: list[dict]) -> list[dict]:
    """Run all stress-test scenarios over the supplied holding data.

    Args:
        holding_data: List of dicts with keys: ticker, sector, value (float).

    Returns:
        List of scenario result dicts.
    """
    total_portfolio_value = sum(h["value"] for h in holding_data)
    results = []
    for scen in STRESS_TEST_SCENARIOS:
        total_impact_inr = 0.0
        most_exposed = None
        max_impact_pct = 0.0

        for hd in holding_data:
            impact_pct = scen["impact"](hd["sector"])
            impact_inr = hd["value"] * (impact_pct / 100.0)
            total_impact_inr += impact_inr
            if abs(impact_pct) > abs(max_impact_pct):
                max_impact_pct = impact_pct
                most_exposed = hd["ticker"]

        portfolio_impact_pct = (
            (total_impact_inr / total_portfolio_value * 100) if total_portfolio_value > 0 else 0.0
        )
        results.append({
            "scenario_name": scen["name"],
            "scenario_description": scen["desc"],
            "estimated_portfolio_impact_pct": round(portfolio_impact_pct, 2),
            "estimated_pnl_impact_inr": round(total_impact_inr, 2),
            "most_exposed_holding": {
                "ticker": most_exposed,
                "estimated_impact_pct": round(max_impact_pct, 2),
            },
        })
    return results


# ---------------------------------------------------------------------------
# Risk-analysis helpers (pure quant math, no DB)
# ---------------------------------------------------------------------------

def compute_pearson_correlation(
    return_series: dict[str, dict[str, float]],
) -> Optional[dict]:
    """Find the highest-correlated pair from per-ticker daily return series.

    Args:
        return_series: {ticker: {date_str: return_float}}.

    Returns:
        dict with ticker_a, ticker_b, correlation — or None if < 2 tickers.
    """
    ticker_list = list(return_series.keys())
    if len(ticker_list) < 2:
        return None

    max_corr = -999.0
    best_pair = None

    for i in range(len(ticker_list)):
        for j in range(i + 1, len(ticker_list)):
            ta = ticker_list[i]
            tb = ticker_list[j]
            ra_map = return_series[ta]
            rb_map = return_series[tb]
            common = [d for d in ra_map if d in rb_map]
            n = len(common)
            if n < 10:
                continue
            ra = [ra_map[d] for d in common]
            rb = [rb_map[d] for d in common]
            mean_a = sum(ra) / n
            mean_b = sum(rb) / n
            cov = sum((ra[k] - mean_a) * (rb[k] - mean_b) for k in range(n))
            var_a = sum((ra[k] - mean_a) ** 2 for k in range(n))
            var_b = sum((rb[k] - mean_b) ** 2 for k in range(n))
            denom = (var_a * var_b) ** 0.5
            if denom == 0:
                continue
            corr = cov / denom
            if not math.isnan(corr) and corr > max_corr:
                max_corr = corr
                best_pair = (ta, tb)

    if best_pair:
        return {
            "ticker_a": best_pair[0],
            "ticker_b": best_pair[1],
            "correlation": round(max_corr, 4),
        }
    return None


# ---------------------------------------------------------------------------
# Trade-journal analytics (pure Python, no DB)
# ---------------------------------------------------------------------------

_TJ_STOPWORDS = frozenset(
    {"the", "a", "an", "is", "in", "of", "and", "to", "i", "my", "this", "for", "it", "at"}
)


def compute_trade_journal_stats(entries_data: list[dict]) -> dict:
    """Aggregate analytics over trade-journal entries.

    Args:
        entries_data: List of dicts with keys: ticker, action, reason_text, outcome_text.

    Returns:
        dict with most_journalled_ticker, win_loss_ratio, top_keywords, action_breakdown.
    """
    total_entries = len(entries_data)

    ticker_counts: dict[str, int] = {}
    for e in entries_data:
        ticker_counts[e["ticker"]] = ticker_counts.get(e["ticker"], 0) + 1
    most_journalled_ticker = max(ticker_counts, key=lambda k: ticker_counts[k]) if ticker_counts else None

    wins = sum(1 for e in entries_data if "profit" in (e.get("outcome_text") or ""))
    losses = sum(1 for e in entries_data if "loss" in (e.get("outcome_text") or ""))
    ratio = round(wins / losses, 2) if losses > 0 else None
    win_loss_ratio = {"wins": wins, "losses": losses, "ratio": ratio}

    word_freq: dict[str, int] = {}
    for e in entries_data:
        for w in (e.get("reason_text") or "").lower().split():
            cleaned = "".join(c for c in w if c.isalpha())
            if cleaned and cleaned not in _TJ_STOPWORDS and len(cleaned) > 2:
                word_freq[cleaned] = word_freq.get(cleaned, 0) + 1
    top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    top_keywords = [{"word": w, "count": c} for w, c in top_keywords]

    action_breakdown = {"BUY": 0, "SELL": 0, "HOLD": 0, "WATCH": 0}
    for e in entries_data:
        act = (e.get("action") or "").upper()
        if act in action_breakdown:
            action_breakdown[act] += 1

    return {
        "total_entries": total_entries,
        "most_journalled_ticker": most_journalled_ticker,
        "win_loss_ratio": win_loss_ratio,
        "top_keywords": top_keywords,
        "action_breakdown": action_breakdown,
    }


# ---------------------------------------------------------------------------
# P&L computation helper (shared between add/update endpoints)
# ---------------------------------------------------------------------------

def compute_holding_pnl(
    shares: float,
    buy_price: float,
    current_price: Optional[float],
    prev_close: Optional[float],
    price_status: Optional[str] = None,
) -> dict:
    """Compute invested, current_value, P&L and day-change for a single holding.

    A missing (None/0) price is not a ₹0 price: the holding is valued at cost
    (current_value = invested, P&L 0) and flagged price_status='unavailable',
    so a failed quote never shows as a -100% loss or drags totals down.

    Returns dict with invested_inr, current_value_inr, pnl_inr, pnl_pct,
    day_change_pct and price_status ('live' | 'stale' | 'unavailable').
    """
    invested = Decimal(str(shares)) * Decimal(str(buy_price))
    if not current_price:
        current_value = invested
        price_status = "unavailable"
    else:
        current_value = Decimal(str(shares)) * Decimal(str(current_price))
    pnl = current_value - invested
    pnl_pct = pnl / invested * 100 if invested > 0 else Decimal("0")
    day_change_pct = 0.0
    if current_price and prev_close and prev_close > 0:
        day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)
    return {
        "invested_inr": round(float(invested), 2),
        "current_value_inr": round(float(current_value), 2),
        "pnl_inr": round(float(pnl), 2),
        "pnl_pct": round(float(pnl_pct), 2),
        "day_change_pct": day_change_pct,
        "price_status": price_status or "live",
    }
