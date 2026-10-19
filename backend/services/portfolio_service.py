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
from bisect import bisect_right
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

import yfinance as yf

# NSE helpers live once in services.nse_client (quality-aware TTL, honest UA);
# re-exported because routers import these names from portfolio_service.
from services.nse_client import (  # noqa: F401
    _nse_session, _get_asm_gsm_lists, _INDICES_TICKERS, _get_indices_data,
)


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

# _INDICES_TICKERS / _get_indices_data: re-exported from services.nse_client (ARCH-11).


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


# ---------------------------------------------------------------------------
# Portfolio vs Nifty benchmark (money-weighted, MATH-04)
# ---------------------------------------------------------------------------

def holding_cashflows(transactions: list, shares: float, buy_price: float, fallback_date: date) -> list[tuple[date, float]]:
    """Cash flows of one holding by trade date: money in < 0, money out > 0.

    From the date-ordered ledger: BUY -(qty*price + fees), SELL +(qty*price - fees);
    an ADJUST restates the position, so flows restart there as a BUY of qty @ price.
    SPLIT/BONUS move no cash, DIVIDEND income is left out. A ledger-less holding
    is one BUY of shares @ buy_price on fallback_date.
    """
    if not transactions:
        return [(fallback_date, -shares * buy_price)] if shares > 0 else []
    flows: list[tuple[date, float]] = []
    for tx in transactions:
        kind = str(tx.transaction_type).upper()
        qty, prc, fee = float(tx.quantity or 0), float(tx.price or 0), float(tx.fees or 0)
        when = tx.date.date() if tx.date is not None else fallback_date
        if kind == "BUY":
            flows.append((when, -(qty * prc + fee)))
        elif kind == "SELL":
            flows.append((when, qty * prc - fee))
        elif kind == "ADJUST":
            flows = [(when, -qty * prc)] if qty > 0 else []
    return flows


def _period_return_pct(flows: list[tuple[date, float]], terminal_value: float, as_of: date, annualize: bool) -> float:
    """Absolute return (money out + terminal over money in) or annualized XIRR, in %."""
    if annualize:
        from services.math_engines.xirr_calculator import xirr
        return xirr(flows + [(as_of, terminal_value)]).value * 100
    invested = -sum(cf for _, cf in flows if cf < 0)
    withdrawn = sum(cf for _, cf in flows if cf > 0)
    return (terminal_value + withdrawn) / invested * 100 - 100


def compute_benchmark(
    cashflows: list[tuple[date, float]],
    terminal_value: float,
    nifty_closes: Optional[list[tuple[date, float]]],
    as_of: date,
) -> dict:
    """Portfolio return vs the same cash flows invested in the Nifty 50 (PME).

    Under a year the return is absolute (SEBI/AMFI convention: never annualize a
    sub-year period); from a year on it is the money-weighted XIRR. nifty_closes
    are date-sorted (date, close); None/empty -> Nifty and alpha are None.
    Nifty and alpha are also None when the PME is undefined: SELL flows that
    exceed what the same money bought in Nifty leave net-negative units (a
    negative terminal value has no XIRR).
    Keys keep their *_cagr_pct names for clients; return_basis says which it is.
    """
    if not any(cf < 0 for _, cf in cashflows):
        raise ValueError("benchmark needs at least one investment cash flow")
    period_days = (as_of - min(d for d, _ in cashflows)).days
    annualize = period_days >= 365
    port_pct = _period_return_pct(cashflows, terminal_value, as_of, annualize)

    nifty_pct: Optional[float] = None
    if nifty_closes:
        dates = [d for d, _ in nifty_closes]

        def close_on(d: date) -> float:
            # Last close on or before d; a flow before the series starts takes the first close.
            return nifty_closes[max(bisect_right(dates, d) - 1, 0)][1]

        units = sum(-cf / close_on(d) for d, cf in cashflows)
        if units > 0:
            try:
                nifty_pct = _period_return_pct(cashflows, units * nifty_closes[-1][1], as_of, annualize)
            except ValueError:  # XIRR found no root
                nifty_pct = None

    return {
        "portfolio_cagr_pct": round(port_pct, 2),
        "nifty_cagr_pct": round(nifty_pct, 2) if nifty_pct is not None else None,
        "alpha_pct": round(port_pct - nifty_pct, 2) if nifty_pct is not None else None,
        "return_basis": "annualized_xirr" if annualize else "absolute",
        "period_days": period_days,
    }


# ---------------------------------------------------------------------------
# Sector attribution (MATH-15)
# ---------------------------------------------------------------------------

def compute_sector_attribution(rows: list[tuple[str, float, float]]) -> dict:
    """Per-sector P&L attribution from (sector, invested, current_value) rows.

    Contribution is in percentage points of the portfolio's invested base
    (sector_pnl / total_invested * 100), so the sectors sum to the portfolio
    return and keep their sign whatever the total P&L is.
    """
    agg: dict[str, dict[str, float]] = {}
    for sector, invested, value in rows:
        d = agg.setdefault(sector, {"invested": 0.0, "value": 0.0})
        d["invested"] += invested
        d["value"] += value

    total_invested = sum(d["invested"] for d in agg.values())
    total_value = sum(d["value"] for d in agg.values())
    sectors = []
    for sector, d in agg.items():
        pnl = d["value"] - d["invested"]
        contribution = pnl / total_invested * 100 if total_invested > 0 else 0.0
        sectors.append({
            "sector": sector,
            "weight_pct": round(d["value"] / total_value * 100, 2) if total_value > 0 else 0.0,
            "total_value": round(d["value"], 2),
            "total_pnl": round(pnl, 2),
            "contribution_pp": round(contribution, 2),
            # Legacy key, same value (it used to be a share of total P&L).
            "contribution_to_total_pnl_pct": round(contribution, 2),
            "sector_return_pct": round(pnl / d["invested"] * 100, 2) if d["invested"] > 0 else 0.0,
        })
    sectors.sort(key=lambda s: abs(s["contribution_pp"]), reverse=True)
    portfolio_pnl = total_value - total_invested
    return {
        "sectors": sectors,
        "portfolio_return_pct": round(portfolio_pnl / total_invested * 100, 2) if total_invested > 0 else 0.0,
    }
