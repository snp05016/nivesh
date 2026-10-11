from config.settings import get_user_agent
import logging
"""
Portfolio-related endpoints extracted from main.py.
"""
import json
import time
import math
import random
import re
import threading
from datetime import datetime, date, timedelta, timezone
from typing import Any, Optional
from collections import Counter, defaultdict
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import FileResponse, StreamingResponse
import yfinance as yf

from services.disk_cache import invalidate as _cache_invalidate
from services.ledger_service import record_transaction, get_or_create_default_group, adjust_position, close_position
from services.yfinance_client import _yf_price_with_status

from helpers import (
    get_session, verify_access_token, EXCHANGE_SUFFIX, _resolve_ticker,
    _to_ns, _yf_price, _yf_fetch_info, _dcache_get, _dcache_set,
    _quick_info_cache, _QUICK_INFO_TTL, DataHarvestingError,
    User, Portfolio, AnalysisHistory, SignalEvent, PriceTarget,
    TradeJournal, PortfolioValuationHistory, PKScreenerSignal,
    MacroEvent, NetWorthLedger, AdvisorInsight,
    PortfolioAddRequest, PortfolioRemoveRequest, PortfolioUpdateRequest,
    PortfolioNoteRequest, TradeJournalAddRequest, TradeJournalUpdateRequest,
    _check_rate_limit, _get_analyze_semaphore, _acquire_analysis_slot, _release_analysis_slot,
    _dash_start_job, _dash_end_job, _dash_update_harvest,
    _extract_json_from_text, _log_token_usage,
    require_auth, format_indian_currency,
)

import importlib.util as _importlib_util
FPDF2_AVAILABLE = _importlib_util.find_spec("fpdf") is not None  # fpdf2 installs the `fpdf` package
if FPDF2_AVAILABLE:
    from fpdf import FPDF

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font as XLFont, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

import os
from decimal import Decimal

from services.staleness import compute_staleness
from services.piotroski import compute_piotroski
from services.llm_utils import contains_devanagari


# _adjust_for_splits, _adjust_for_bonus, _apply_corporate_actions
# imported from services.portfolio_service

from services.llm_utils import deepseek_chat as _deepseek_chat
from services.portfolio_service import (
    _adjust_for_splits,
    _adjust_for_bonus,
    _apply_corporate_actions,
    _get_indices_data,
    _nse_session,
    _get_asm_gsm_lists,
    _risk_label,
    compute_sip,
    get_stress_sector,
    compute_stress_test_results,
    compute_pearson_correlation,
    compute_trade_journal_stats,
    compute_holding_pnl,
    STRESS_TEST_SCENARIOS,
    _INDICES_TICKERS,
)


from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional

class NetWorthSnapshotResponse(_BaseModel):
    user_id: int
    snapshot_date: str
    total_value_formatted: str          # e.g. "₹12.50 Crores"
    daily_delta_formatted: _Optional[str]
    daily_delta_pct: _Optional[float]
    peak_value_formatted: _Optional[str]
    top_gainer_ticker: _Optional[str]
    top_gainer_pct: _Optional[float]
    top_loser_ticker: _Optional[str]
    top_loser_pct: _Optional[float]


# _INDICES_TICKERS, _get_indices_data imported from services.portfolio_service


router = APIRouter(tags=["Portfolio"])

# ── Item 35: SIP Calculator ───────────────────────────────────────────
class SIPCalculatorRequest(_BaseModel):
    monthly_amount: float
    expected_return_pct: float
    years: int
    step_up_pct: float = 0.0

@router.post("/portfolio/sip-calculator")
def sip_calculator(req: SIPCalculatorRequest):
    result = compute_sip(
        monthly_amount=req.monthly_amount,
        expected_return_pct=req.expected_return_pct,
        years=req.years,
        step_up_pct=req.step_up_pct,
    )
    return {"inputs": req.model_dump(), **result}

# ── Item 44: Portfolio vs Nifty CAGR ──────────────────────────────────
@router.get("/portfolio/benchmark")
def portfolio_benchmark(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with get_session() as db:
        holdings = db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name != "watchlist",
            Portfolio.is_virtual == False,  # noqa: E712
        ).all()

    if not holdings:
        raise HTTPException(status_code=404, detail="No holdings to benchmark")
        
    earliest_date = None
    for h in holdings:
        # Fallback to current date if missing
        h_date = getattr(h, "created_at", None)
        if h_date is None:
            continue
        if earliest_date is None or h_date < earliest_date:
            earliest_date = h_date
            
    if earliest_date is None:
        earliest_date = datetime.now() - timedelta(days=365) # fallback 1 year
        
    # period in days
    period_days = (datetime.now() - earliest_date).days
    if period_days < 1:
        period_days = 1
        
    years = period_days / 365.25
    
    # Get Nifty price — no data means no benchmark (never a fake flat 1.0 → 1.0)
    try:
        t = yf.Ticker("^NSEI")
        hist = t.history(start=earliest_date.strftime("%Y-%m-%d"))
        if hist.empty:
            raise ValueError("empty ^NSEI history")
        nifty_start = float(hist["Close"].iloc[0])
        nifty_end = float(hist["Close"].iloc[-1])
    except Exception as e:
        logging.warning(f"[benchmark] NIFTY history unavailable: {e}")
        raise HTTPException(status_code=503, detail="Benchmark data unavailable")

    nifty_cagr_pct = (((nifty_end / nifty_start) ** (1 / years)) - 1) * 100 if nifty_start > 0 and years > 0 else 0.0

    # Portfolio value — unpriced holdings are excluded from both sides (not valued at cost)
    total_invested = 0.0
    total_current = 0.0
    unpriced: list[str] = []
    for h in holdings:
        ticker = str(h.ticker)
        cp = _yf_price(_to_ns(ticker))[0]
        if not cp:
            unpriced.append(ticker)
            continue
        total_invested += float(h.buy_price) * float(h.shares)  # type: ignore[arg-type]
        total_current += cp * float(h.shares)  # type: ignore[arg-type]
    if total_invested <= 0:
        logging.warning(f"[benchmark] no live price for any holding of user {user_id}: {unpriced}")
        raise HTTPException(status_code=503, detail="Benchmark data unavailable")

    port_cagr_pct = (((total_current / total_invested) ** (1 / years)) - 1) * 100 if total_invested > 0 and years > 0 else 0.0
    
    return {
        "portfolio_cagr_pct": round(port_cagr_pct, 2),
        "nifty_cagr_pct": round(nifty_cagr_pct, 2),
        "alpha_pct": round(port_cagr_pct - nifty_cagr_pct, 2),
        "period_days": period_days,
        "earliest_holding_date": earliest_date.isoformat(),
        "current_portfolio_value": total_current,
        "unpriced_tickers": unpriced,
    }

# ── Item 50: Portfolio Stress Test ────────────────────────────────────
@router.get("/portfolio/stress-test")
def portfolio_stress_test(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with get_session() as db:
        holdings = db.query(Portfolio).filter(
            Portfolio.user_id == user_id, Portfolio.group_name != "watchlist"
        ).all()

    if not holdings:
        return []

    holding_data = []
    for h in holdings:
        cp = _yf_price(_to_ns(str(h.ticker)))[0]
        if not cp:
            logging.warning(f"[stress-test] no price for {h.ticker}; excluded instead of valued at cost")
            continue

        val = cp * float(h.shares)  # type: ignore[arg-type]
        holding_data.append({
            "ticker": h.ticker,
            "sector": get_stress_sector(h.company_name),
            "value": val,
        })
    if not holding_data:
        raise HTTPException(status_code=503, detail="Price data unavailable")

    return compute_stress_test_results(holding_data)

# ---------------------------------------------------------------------------
# Local caches & helpers needed by endpoints
# ---------------------------------------------------------------------------
from config.settings import MORNING_BRIEF_TTL as _MORNING_CACHE_TTL
_MACRO_IMPACT_TTL = 7200  # 2 hours

# _nse_session, _get_asm_gsm_lists, _risk_label imported from services.portfolio_service


# ---------------------------------------------------------------------------
# 0. GET /portfolio/signal-warnings  (MUST be before /portfolio/{user_id})
# ---------------------------------------------------------------------------
@router.get("/portfolio/signal-warnings")
def portfolio_signal_warnings(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    warnings = []
    with get_session() as session:
        holdings = session.query(Portfolio).filter(Portfolio.user_id == user_id, Portfolio.group_name == "holdings").all()
        for h in holdings:
            rows = session.query(AnalysisHistory).filter(AnalysisHistory.ticker == h.ticker).order_by(AnalysisHistory.created_at.desc()).limit(2).all()
            if not rows: continue
            latest, prev = rows[0], rows[1] if len(rows) > 1 else None
            signal_flipped = prev is not None and prev.signal != latest.signal
            confidence_dropped = prev is not None and latest.confidence_pct is not None and prev.confidence_pct is not None and (prev.confidence_pct - latest.confidence_pct) > 20
            is_bearish = latest.signal in ("BEARISH", "CAUTIOUSLY BEARISH")
            if signal_flipped or confidence_dropped or is_bearish:
                warnings.append({"ticker": h.ticker, "current_signal": latest.signal, "previous_signal": prev.signal if prev else None, "signal_flipped": signal_flipped, "confidence_dropped": confidence_dropped, "is_bearish": is_bearish, "analysis_date": latest.analysis_date})
    return {"warnings": warnings}


# ---------------------------------------------------------------------------
# 1. GET /portfolio/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/{user_id}")
async def portfolio_endpoint(user_id: int, authorization: str = Header(None), is_virtual: bool = False):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")

            holdings = session.query(Portfolio).filter(
                Portfolio.user_id == user_id,
                Portfolio.group_name != "watchlist",
                Portfolio.is_virtual == is_virtual,
            ).all()
            if not holdings:
                return {"user": user.display_name, "holdings": [], "total_invested": 0, "total_current": 0, "total_pnl": 0}

            tickers = [h.ticker for h in holdings]
            last_analyses = {}
            last_signals = {}
            for row in session.query(AnalysisHistory).filter(
                AnalysisHistory.user_id == user_id,
                AnalysisHistory.ticker.in_(tickers),
            ).order_by(AnalysisHistory.created_at.desc()).all():
                if row.ticker not in last_analyses:
                    last_analyses[row.ticker] = row.created_at
                    last_signals[row.ticker] = row.signal or "HOLD"

        # Fetch all prices in parallel — 10x faster than sequential yfinance calls
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=min(len(holdings), 10)) as pool:
            price_results = await asyncio.gather(
                *[loop.run_in_executor(pool, _yf_price_with_status, _to_ns(h.ticker)) for h in holdings],
                return_exceptions=True
            )
        prices = {
            h.ticker: (r if not isinstance(r, Exception) else (None, None, "unavailable", None))
            for h, r in zip(holdings, price_results)
        }

        rows = []
        unpriced: list[str] = []
        total_invested = Decimal("0")
        total_current = Decimal("0")

        for h in holdings:
            current_price, prev_close, price_status, price_as_of = prices.get(
                h.ticker, (None, None, "unavailable", None)
            )
            shares = float(h.shares or 0)  # type: ignore[arg-type]
            buy_price = float(h.buy_price or 0)  # type: ignore[arg-type]
            # An unpriced holding is valued at cost (P&L 0), never at a fake ₹0 price.
            pnl_data = compute_holding_pnl(shares, buy_price, current_price, prev_close, price_status)
            if pnl_data["price_status"] == "unavailable":
                unpriced.append(str(h.ticker))

            total_invested += Decimal(str(pnl_data["invested_inr"]))
            total_current += Decimal(str(pnl_data["current_value_inr"]))

            rows.append({
                "ticker": h.ticker,
                "company_name": h.company_name,
                "group": h.group_name,
                "shares": shares,
                "buy_price": buy_price,
                "purchase_date": getattr(h, "purchase_date", "N/A"),
                "notes": getattr(h, "notes", ""),
                "target_price": float(getattr(h, "target_price", 0.0) or 0.0),
                "current_price": current_price or buy_price,
                "price_status": pnl_data["price_status"],
                "price_as_of": price_as_of,
                "day_change_pct": pnl_data["day_change_pct"],
                "invested_inr": pnl_data["invested_inr"],
                "current_value_inr": pnl_data["current_value_inr"],
                "pnl_inr": pnl_data["pnl_inr"],
                "pnl_pct": pnl_data["pnl_pct"],
                "notes": h.notes or "",
                "staleness": compute_staleness(
                    last_analyses.get(h.ticker),
                    pnl_data["day_change_pct"],
                    last_signals.get(h.ticker, "HOLD"),
                ),
            })

        total_pnl = total_current - total_invested

        return {
            "user": user.display_name,
            "user_id": user_id,
            "as_of": datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC"),
            "total_invested_inr": round(float(total_invested), 2),
            "total_current_inr": round(float(total_current), 2),
            "total_pnl_inr": round(float(total_pnl), 2),
            "total_pnl_pct": round(float(total_pnl / total_invested * Decimal("100")), 2) if total_invested > 0 else 0,
            "unpriced_tickers": unpriced,
            "holdings": sorted(rows, key=lambda x: (x["pnl_pct"] or 0), reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. GET /portfolio/history/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/history/{user_id}")
def portfolio_history_endpoint(user_id: int, days: int = 30, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_session() as session:
        rows = session.query(PortfolioValuationHistory).filter(
            PortfolioValuationHistory.user_id == user_id,
            PortfolioValuationHistory.snapshot_date >= cutoff,
        ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()
        return {
            "user_id": user_id,
            "days": days,
            "snapshots": [
                {
                    "date": r.snapshot_date,
                    "total_value": r.total_value,
                    "total_invested": r.total_invested,
                    "total_pnl": r.total_pnl,
                    "pnl_pct": r.pnl_percent,
                    "nifty_close": r.nifty_close,
                }
                for r in rows
            ],
        }


# ---------------------------------------------------------------------------
# 3. GET /fundamentals/piotroski/{ticker}
# ---------------------------------------------------------------------------
@router.get("/fundamentals/piotroski/{ticker}")
def piotroski_endpoint(ticker: str):
    ticker = ticker.upper()
    cached = _dcache_get("piotroski", ticker)
    if cached:
        return cached
    result = compute_piotroski(ticker)
    result["ticker"] = ticker
    _dcache_set("piotroski", ticker, result)
    return result


# ---------------------------------------------------------------------------
# 4. GET /morning-summary/{user_id}
# ---------------------------------------------------------------------------
@router.get("/morning-summary/{user_id}")
def morning_summary_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    now = time.time()

    # Check in-memory cache first
    # Redis-backed shared cache (works across all 12 workers)
    cached = _dcache_get("morning_brief", str(user_id))
    if cached and isinstance(cached, dict):
        if not contains_devanagari(cached.get("summary", "")):
            return cached

    generated_at = datetime.now(timezone.utc).strftime("%H:%M")

    fallback = {
        "summary": "• Market data loaded. AI brief unavailable at this time.",
        "movers": [],
        "mood": "cautious",
        "generated_at": generated_at,
    }

    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()

            # Get last known signal for each ticker from analysis_history (single IN query)
            last_signals: dict[str, str] = {}
            tickers = [h.ticker.upper() for h in holdings]
            rows = (
                session.query(AnalysisHistory)
                .filter(AnalysisHistory.user_id == user_id, AnalysisHistory.ticker.in_(tickers))
                .order_by(AnalysisHistory.created_at.desc())
                .all()
            )
            for r in rows:
                if r.ticker not in last_signals:
                    last_signals[r.ticker] = r.signal

        # Fetch prices and compute movers
        holding_lines = []
        mover_tickers = []
        significant_movers_lines = []

        for h in holdings:
            ns = _to_ns(h.ticker)
            try:
                current_price, prev_close = _yf_price(ns)
            except Exception as e:
                import logging
                logging.warning(f"Caught exception: {e}")
                current_price, prev_close = None, None

            day_pct = None
            if current_price and prev_close and prev_close > 0:
                day_pct = round((current_price - prev_close) / prev_close * 100, 2)

            invested = h.shares * h.buy_price
            current_value = h.shares * current_price if current_price else None
            pnl_inr = (current_value - invested) if current_value else None
            pnl_pct = ((current_value - invested) / invested * 100) if current_value and invested > 0 else None

            price_str = f"₹{current_price:.2f}" if current_price else "N/A"
            day_str = (f"+{day_pct:.1f}%" if day_pct and day_pct >= 0 else f"{day_pct:.1f}%") if day_pct is not None else "N/A"
            pnl_str = ""
            if pnl_inr is not None and pnl_pct is not None:
                pnl_sign = "+" if pnl_inr >= 0 else ""
                pnl_str = f", overall P&L: {pnl_sign}₹{pnl_inr:.0f} ({pnl_sign}{pnl_pct:.1f}%)"

            company = h.company_name or h.ticker
            holding_lines.append(f"{h.ticker} ({company}): {price_str}, day change: {day_str}{pnl_str}")

            if day_pct is not None and abs(day_pct) >= 2.0:
                mover_tickers.append(h.ticker)
                direction = "UP" if day_pct > 0 else "DOWN"
                significant_movers_lines.append(f"{h.ticker}: {day_str} ({direction})")

        # Get signals text
        signal_lines = []
        for h in holdings:
            sig = last_signals.get(h.ticker, "No analysis yet")
            signal_lines.append(f"{h.ticker}: {sig}")

        # Get market indices
        indices_lines = []
        try:
            indices_data = _get_indices_data()
            for idx in indices_data.get("indices", []):
                if idx["name"] in ("Nifty 50", "Sensex"):
                    chg = idx["change_pct"]
                    chg_str = (f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%")
                    indices_lines.append(f"{idx['name']}: {idx['value']:.2f} ({chg_str})")
        except Exception as e:
            import logging
            logging.error(f"Error occurred: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

        portfolio_text = "\n".join(holding_lines) if holding_lines else "No holdings found."
        movers_text = "\n".join(significant_movers_lines) if significant_movers_lines else "None today"
        signals_text = "\n".join(signal_lines) if signal_lines else "No analysis available."
        indices_text = "\n".join(indices_lines) if indices_lines else "Data unavailable."

        prompt = f"""You are a friendly Indian stock market advisor. Write a short morning brief (4-6 bullet points) for an investor based on their portfolio data. Write ONLY in English — never use Hindi or any other language. Be specific about which stocks to watch and why. Mention any big movers. Flag anything concerning. End with one sentence on overall market mood. Use Indian number format (lakhs/crores). Be warm and helpful.

Portfolio holdings today:
{portfolio_text}

Significant movers (±2%+):
{movers_text}

Last AI signals:
{signals_text}

Market indices:
{indices_text}

Return ONLY a JSON object (no markdown):
{{"summary": "• Point 1\\n• Point 2\\n• Point 3\\n• Point 4", "movers": ["TICKER1", "TICKER2"], "mood": "positive"}}

mood must be exactly: "positive", "cautious", or "negative"
"""
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        HAIKU_MODEL = "claude-haiku-4-5-20251001"
        if not api_key or api_key == "placeholder":
            _dcache_set("morning_brief", str(user_id), fallback, ttl=_MORNING_CACHE_TTL)
            return fallback

        client = anthropic.Anthropic(api_key=api_key)
        for attempt in range(3):
            try:
                response = client.messages.create(
                    model=HAIKU_MODEL,
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                logging.info(f"[Anthropic] Morning summary attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))
        _log_token_usage("morning_summary", response.usage, HAIKU_MODEL)

        raw = _extract_json_from_text(response.content[0].text)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.info(f"[ERROR] Failed to parse morning summary JSON: {e}")
            parsed = fallback

        raw_summary = parsed.get("summary", fallback["summary"])
        if contains_devanagari(raw_summary):
            logging.info("[MORNING] Rejected Hindi morning brief output; using English fallback.")
            parsed = fallback
            raw_summary = fallback["summary"]

        # Normalize inline bullets ("• A • B • C") to newline-separated ("• A\n• B\n• C")
        if raw_summary and "\n" not in raw_summary and raw_summary.count("•") > 1:
            parts = [p.strip() for p in raw_summary.split("•") if p.strip()]
            raw_summary = "\n".join(f"• {p}" for p in parts)

        result = {
            "summary": raw_summary,
            "movers": parsed.get("movers", mover_tickers),
            "mood": parsed.get("mood", "cautious"),
            "generated_at": generated_at,
        }

        # Validate mood value
        if result["mood"] not in ("positive", "cautious", "negative"):
            result["mood"] = "cautious"

        # Build prioritised action list for today
        # Fix 2.36: Signal flips (BULL→BEAR, BEAR→BULL) take TOP priority
        # over minor percentage movement alerts. Trend changes matter more.
        priority_items = []

        # Priority 1: Signal flips in last 24h for held stocks
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            with get_session() as session:
                held_tickers = {h.ticker for h in session.query(Portfolio).filter(
                    Portfolio.user_id == user_id,
                    Portfolio.group_name == "holdings"
                ).all()}
                flips = session.query(SignalEvent).filter(
                    SignalEvent.created_at >= cutoff,
                    SignalEvent.ticker.in_(held_tickers)
                ).all()
                for f in flips:
                    is_trend_flip = (
                        (f.from_signal in ("BULLISH", "BUY") and f.to_signal in ("BEARISH", "SELL")) or
                        (f.from_signal in ("BEARISH", "SELL") and f.to_signal in ("BULLISH", "BUY"))
                    )
                    priority_items.append({
                        "priority": 1 if is_trend_flip else 2,
                        "type": "trend_flip" if is_trend_flip else "signal_change",
                        "ticker": f.ticker,
                        "message": f"Signal changed: {f.ticker} {f.from_signal} → {f.to_signal}",
                    })
        except Exception as e:
            logging.info(f"[MORNING] Signal flip check failed: {e}")

        # Priority 2: Triggered price alerts
        try:
            with get_session() as session:
                triggered = session.query(PriceTarget).filter(
                    PriceTarget.user_id == user_id,
                    PriceTarget.triggered == True
                ).all()
                for a in triggered:
                    priority_items.append({
                        "priority": 2,
                        "type": "alert_triggered",
                        "ticker": a.ticker,
                        "message": f"Price alert triggered: {a.ticker} {a.direction} ₹{a.target_price:.0f}",
                    })
        except Exception as e:
            logging.info(f"[MORNING] Alert priority check failed: {e}")

        priority_items.sort(key=lambda x: x["priority"])
        result["priority_items"] = priority_items

        _dcache_set("morning_brief", str(user_id), result, ttl=_MORNING_CACHE_TTL)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logging.info(f"[morning-summary] Error: {e}")
        _dcache_set("morning_brief", str(user_id), fallback, ttl=_MORNING_CACHE_TTL)
        return fallback


# ---------------------------------------------------------------------------
# 5. POST /portfolio & 6. POST /portfolio/add
# ---------------------------------------------------------------------------
@router.post("/portfolio")
@router.post("/portfolio/add")
def portfolio_add_endpoint(req: PortfolioAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not req.ticker or not req.ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker cannot be empty.")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        record_transaction(
            user_id=req.user_id,
            ticker=ticker,
            transaction_type=req.transaction_type.upper(),
            quantity=req.shares,
            price=req.buy_price,
            fees=0.0,
            notes=req.notes,
            company_name=req.company_name,
            target_price=req.target_price,
            purchase_date=req.purchase_date,
            is_virtual=getattr(req, "is_virtual", False),
        )
        _cache_invalidate("morning_brief", str(req.user_id))

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        pnl_data = compute_holding_pnl(req.shares, req.buy_price, current_price, prev_close)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": req.company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or req.buy_price,
            **pnl_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 7. DELETE /portfolio/remove
# ---------------------------------------------------------------------------
@router.delete("/portfolio/remove")
def portfolio_remove_endpoint(req: PortfolioRemoveRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ticker = req.ticker.upper().strip()
    try:
        # Through the ledger, so a later BUY cannot resurrect the removed lots.
        if not close_position(req.user_id, ticker):
            raise HTTPException(status_code=404, detail="Holding not found.")
        _cache_invalidate("morning_brief", str(req.user_id))
        return {"success": True, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 8. PUT /portfolio/update
# ---------------------------------------------------------------------------
@router.put("/portfolio/update")
def portfolio_update_endpoint(req: PortfolioUpdateRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        # Through the ledger (ADJUST entry), so the next BUY/SELL keeps this edit.
        company_name = adjust_position(
            req.user_id, ticker, req.shares, req.buy_price,
            target_price=req.target_price, purchase_date=req.purchase_date,
        )
        if company_name is None:
            raise HTTPException(status_code=404, detail="Holding not found.")
        _cache_invalidate("morning_brief", str(req.user_id))

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        pnl_data = compute_holding_pnl(req.shares, req.buy_price, current_price, prev_close)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or req.buy_price,
            **pnl_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 9. GET /portfolio/transactions/{ticker}
# ---------------------------------------------------------------------------
@router.get("/portfolio/transactions/{ticker}")
def portfolio_transactions_endpoint(ticker: str, user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ticker = ticker.upper().strip()
    try:
        from services.ledger_service import get_transactions_for_ticker
        return get_transactions_for_ticker(user_id=user_id, ticker=ticker)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 10. PUT /portfolio/note
# ---------------------------------------------------------------------------
@router.put("/portfolio/note")
def portfolio_note_endpoint(req: PortfolioNoteRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Stock not found in portfolio or watchlist")
            holding.notes = req.note.strip()
            session.commit()
            _cache_invalidate("morning_brief", str(req.user_id))
        return {"success": True, "ticker": ticker, "note": req.note.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 11. GET /api/v1/portfolio/advisor-consensus
# ---------------------------------------------------------------------------
from services import stock_universe  # single NSE/BSE directory (ARCH-10)

@router.get("/api/v1/portfolio/advisor-consensus")
def portfolio_advisor_consensus(user_id: int, days: int = 7):
    """
    Aggregate AdvisorInsight rows into sector signals and trending tickers.

    Args:
        user_id (int): The user_id.
        days (int): The days.

    Returns:
        Any: The response.
    """

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        with get_session() as session:
            # ── Fetch all insights in the window ────────────────────────────
            rows = (
                session.query(AdvisorInsight)
                .filter(AdvisorInsight.published_at >= cutoff)
                .all()
            )

            # ── last_harvest_at: most recent created_at across entire table ─
            last_row = (
                session.query(AdvisorInsight)
                .order_by(AdvisorInsight.created_at.desc())
                .first()
            )
            last_harvest_at = (
                last_row.created_at.isoformat() + "Z"
                if last_row and last_row.created_at
                else None
            )

            # ── Company names: prefer AnalysisHistory (most recent) ─────────
            company_from_history: dict[str, str] = {}
            try:
                ah_rows = (
                    session.query(AnalysisHistory.ticker, AnalysisHistory.created_at)
                    .order_by(AnalysisHistory.created_at.desc())
                    .all()
                )
                seen: set[str] = set()
                for ah in ah_rows:
                    if ah.ticker not in seen:
                        seen.add(ah.ticker)
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

        # ── total_videos_processed ──────────────────────────────────────────
        total_videos_processed = len({r.video_id for r in rows})

        # ── trending_tickers ─────────────────────────────────────────────────
        ticker_data: dict[str, dict] = {}
        for r in rows:
            tk = r.ticker.upper().strip()
            if tk not in ticker_data:
                ticker_data[tk] = {
                    "mention_count": 0,
                    "view_count_sum": 0,
                    "stances": [],
                    "advisors": set(),
                }
            ticker_data[tk]["mention_count"] += 1
            ticker_data[tk]["view_count_sum"] += r.view_count or 0
            ticker_data[tk]["stances"].append((r.stance or "").upper())
            ticker_data[tk]["advisors"].add(r.advisor_name)

        def _dominant_stance(stances: list[str]) -> str:
            counts = Counter(s for s in stances if s in ("BULLISH", "NEUTRAL", "BEARISH"))
            if not counts:
                return "NEUTRAL"
            return counts.most_common(1)[0][0]

        sorted_tickers = sorted(
            ticker_data.items(),
            key=lambda kv: kv[1]["mention_count"],
            reverse=True,
        )[:5]

        trending_tickers = []
        for tk, td in sorted_tickers:
            company_name = (
                (stock_universe.by_ticker(tk) or {}).get("company_name")
                or company_from_history.get(tk)
                or tk
            )
            trending_tickers.append({
                "ticker": tk,
                "company_name": company_name,
                "mention_count": td["mention_count"],
                "dominant_stance": _dominant_stance(td["stances"]),
                "total_view_count": td["view_count_sum"],
                "advisors": sorted(td["advisors"]),
            })

        # ── sector_signals ───────────────────────────────────────────────────
        sector_data: dict[str, dict] = defaultdict(lambda: {
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "advisors": set(),
            "mention_count": 0,
        })
        for r in rows:
            tk = r.ticker.upper().strip()
            sector = stock_universe.sector_for(tk)
            stance = (r.stance or "").upper()
            sector_data[sector]["mention_count"] += 1
            if stance == "BULLISH":
                sector_data[sector]["bullish_count"] += 1
            elif stance == "BEARISH":
                sector_data[sector]["bearish_count"] += 1
            else:
                sector_data[sector]["neutral_count"] += 1
            sector_data[sector]["advisors"].add(r.advisor_name)

        sector_signals = []
        for theme, sd in sector_data.items():
            if sd["mention_count"] < 2:
                continue
            sector_signals.append({
                "theme": theme,
                "bullish_count": sd["bullish_count"],
                "bearish_count": sd["bearish_count"],
                "neutral_count": sd["neutral_count"],
                "top_advisors": sorted(sd["advisors"]),
            })

        sector_signals.sort(key=lambda x: x["bullish_count"], reverse=True)
        sector_signals = sector_signals[:3]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "window_days": days,
            "sector_signals": sector_signals,
            "trending_tickers": trending_tickers,
            "total_videos_processed": total_videos_processed,
            "last_harvest_at": last_harvest_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 12. GET /portfolio/export/excel/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/export/excel/{user_id}")
def export_portfolio_excel(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not OPENPYXL_AVAILABLE:
        raise HTTPException(status_code=501, detail="openpyxl not installed on server")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()

            last_signals: dict[str, str] = {}
            last_confidence: dict[str, float | None] = {}
            for h in holdings:
                row = session.query(AnalysisHistory)\
                    .filter(AnalysisHistory.ticker == h.ticker)\
                    .order_by(AnalysisHistory.created_at.desc()).first()
                if row:
                    last_signals[h.ticker] = row.signal
                    last_confidence[h.ticker] = row.confidence_pct

            history_rows = session.query(AnalysisHistory)\
                .order_by(AnalysisHistory.created_at.desc()).limit(100).all()
            # Detach data before session closes
            history_data = [(r.analysis_date, r.ticker, r.signal, r.confidence_pct,
                             r.target_short, r.target_medium, r.target_long) for r in history_rows]
            holdings_data = [(h.ticker, h.company_name, h.shares, h.buy_price,
                              h.notes or "") for h in holdings]

        wb = openpyxl.Workbook()

        # ── Sheet 1: Portfolio ──────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Portfolio"

        headers = ["Ticker", "Company", "Shares", "Buy Price (Rs)", "Current Price (Rs)",
                   "Current Value (Rs)", "Invested (Rs)", "P&L (Rs)", "P&L %",
                   "Signal", "Confidence %", "Notes"]

        header_fill = PatternFill(start_color="2C2C2C", end_color="2C2C2C", fill_type="solid")
        header_font = XLFont(color="F5F0E8", bold=True, size=11)

        for col, header in enumerate(headers, 1):
            cell = ws1.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws1.row_dimensions[1].height = 22

        col_widths = [12, 32, 10, 18, 20, 20, 18, 16, 10, 20, 14, 40]
        for i, w in enumerate(col_widths, 1):
            ws1.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        green_fill = PatternFill(start_color="D6F5E3", end_color="D6F5E3", fill_type="solid")
        red_fill   = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")

        for row_num, (ticker, company, shares, buy_price, notes) in enumerate(holdings_data, 2):
            ns = _to_ns(ticker)
            current_price, _ = _yf_price(ns)
            if not current_price:
                current_price = 0.0
            invested       = round(shares * buy_price, 2)
            current_value  = round(shares * current_price, 2)
            pnl            = round(current_value - invested, 2)
            pnl_pct        = round((pnl / invested * 100) if invested > 0 else 0, 2)
            signal         = last_signals.get(ticker, "—")
            confidence     = last_confidence.get(ticker, "—")

            row_data = [ticker, company, shares, buy_price, current_price,
                        current_value, invested, pnl, pnl_pct, signal, confidence, notes]
            for col, value in enumerate(row_data, 1):
                cell = ws1.cell(row=row_num, column=col, value=value)
                cell.alignment = Alignment(
                    horizontal="center" if col in (1, 3, 10, 11) else "right"
                )
                if col in (8, 9):
                    cell.fill = green_fill if pnl >= 0 else red_fill

        # ── Sheet 2: Analysis History ───────────────────────────────
        ws2 = wb.create_sheet("Analysis History")
        hist_headers = ["Date", "Ticker", "Signal", "Confidence %",
                        "Target 3M (Rs)", "Target 12M (Rs)", "Target 3Y (Rs)"]
        for col, h in enumerate(hist_headers, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for w, col in zip([14, 14, 22, 14, 18, 18, 18], range(1, 8)):
            ws2.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w

        for idx, (adate, aticker, signal, conf, t3m, t12m, t36m) in enumerate(history_data, 2):
            ws2.cell(row=idx, column=1, value=adate)
            ws2.cell(row=idx, column=2, value=aticker)
            ws2.cell(row=idx, column=3, value=signal)
            ws2.cell(row=idx, column=4, value=conf)
            ws2.cell(row=idx, column=5, value=t3m)
            ws2.cell(row=idx, column=6, value=t12m)
            ws2.cell(row=idx, column=7, value=t36m)

        import io
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        today = date.today().strftime("%Y%m%d")
        filename = f"nivesh_portfolio_{today}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 13. GET /api/v1/portfolio/valuation-history
# ---------------------------------------------------------------------------
@router.get("/api/v1/portfolio/valuation-history")
async def get_valuation_history(user_id: int, days: int = 90, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with get_session() as session:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

        snapshots: list[Any] = session.query(PortfolioValuationHistory).filter(
            PortfolioValuationHistory.user_id == user_id,
            PortfolioValuationHistory.snapshot_date >= cutoff_date
        ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()

        estimated_points: list[Any] = []
        if not snapshots:
            holdings = session.query(Portfolio).filter(
                Portfolio.user_id == user_id,
                Portfolio.group_name == "holdings"
            ).all()
            if holdings:
                try:
                    ticker_shares = {}
                    for h in holdings:
                        t = h.ticker.upper()
                        ticker_shares[t] = ticker_shares.get(t, 0.0) + h.shares

                    all_closes = {}
                    for t in ticker_shares:
                        try:
                            tk = yf.Ticker(f"{t}.NS")
                            hist = tk.history(period="35d")
                            if not hist.empty:
                                closes = hist["Close"].dropna()
                                all_closes[t] = {d.strftime("%Y-%m-%d"): float(c) for d, c in closes.items()}
                        except Exception as e:
                            import logging
                            logging.warning(f"Caught exception: {e}")
                            continue

                    if all_closes:
                        all_dates = set()
                        for closes in all_closes.values():
                            all_dates.update(closes.keys())
                        sorted_dates = sorted(all_dates)[-30:]

                        total_invested = sum(h.buy_price * h.shares for h in holdings)

                        for date_str in sorted_dates:
                            total_value = 0.0
                            missing = False
                            for t, shares in ticker_shares.items():
                                if t in all_closes and date_str in all_closes[t]:
                                    total_value += all_closes[t][date_str] * shares
                                else:
                                    missing = True
                                    break
                            if missing:
                                continue

                            pnl = total_value - total_invested
                            pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0.0

                            # REL-10: back-filled from TODAY's shares and cost, so it is an
                            # estimate. Return it flagged, never persist it as real history.
                            estimated_points.append(SimpleNamespace(
                                snapshot_date=date_str,
                                total_value=round(total_value, 2),
                                total_invested=round(total_invested, 2),
                                total_pnl=round(pnl, 2),
                                pnl_percent=round(pnl_pct, 2),
                                nifty_close=None,
                            ))
                        estimated_points = [p for p in estimated_points if p.snapshot_date >= cutoff_date]
                        snapshots = estimated_points
                except Exception as e:
                    logging.info(f"[Valuation Seeding] Error for user {user_id}: {e}")

        if snapshots:
            first = snapshots[0]
            last = snapshots[-1]
            change_value = last.total_value - first.total_value
            change_pct = ((last.total_value - first.total_value) / first.total_value * 100) \
                if first.total_value > 0 else 0.0
            peak = max(s.total_value for s in snapshots)
            trough = min(s.total_value for s in snapshots)
        else:
            change_value = change_pct = peak = trough = 0.0

        return {
            "user_id": user_id,
            "days": days,
            "estimated": bool(estimated_points),
            "snapshots": [
                {
                    "date": s.snapshot_date,
                    "total_value": s.total_value,
                    "total_invested": s.total_invested,
                    "total_pnl": s.total_pnl,
                    "pnl_percent": s.pnl_percent,
                    "nifty_close": s.nifty_close,
                }
                for s in snapshots
            ],
            "summary": {
                "period_change_value": round(change_value, 2),
                "period_change_pct": round(change_pct, 2),
                "peak_value": round(peak, 2),
                "trough_value": round(trough, 2),
                "data_points": len(snapshots),
            }
        }


# Generated chart PNGs and meta JSON live here; never serve this dir publicly.
_CHART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "charts"))


# ---------------------------------------------------------------------------
# 14b. GET /api/v1/portfolio/charts/{user_id}/image/{filename}
# ---------------------------------------------------------------------------
@router.get("/api/v1/portfolio/charts/{user_id}/image/{filename}")
def portfolio_chart_image(user_id: int, filename: str, caller: int = Depends(require_auth)):
    """Serve one of the caller's own chart PNGs. 404 for anyone else's or any other file."""
    if caller != user_id or not re.fullmatch(rf"chart_{user_id}_\d{{1,2}}\.png", filename):
        raise HTTPException(status_code=404, detail="Not found")
    path = os.path.join(_CHART_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, no-store"})


# ---------------------------------------------------------------------------
# 14a. GET /api/v1/portfolio/charts/{user_id}
# ---------------------------------------------------------------------------
@router.get("/api/v1/portfolio/charts/{user_id}")
async def portfolio_charts_endpoint(
    user_id: int,
    authorization: str = Header(None),
    regenerate: bool = False,
):
    """
    Generate portfolio charts as PNG images. Returns list of chart metadata with URLs.

Charts are cached on disk per user. Set ?regenerate=true to force re‑generation.
Uses a thread-pool executor so the event loop is never blocked.

    Args:
        user_id (int): The user_id.
        authorization (str): The authorization.
        regenerate (bool): The regenerate.

    Returns:
        Any: The response.
    """
    token_user = verify_access_token(
        authorization.split(" ", 1)[1]
        if authorization and authorization.startswith("Bearer ")
        else ""
    )
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        from portfolio_charts import generate_portfolio_charts
        import asyncio
        import time as _time_module
        from concurrent.futures import ThreadPoolExecutor

        chart_dir = _CHART_DIR
        os.makedirs(chart_dir, exist_ok=True)

        # ── Cache: serve existing charts unless regenerate was requested ──
        meta_path = os.path.join(chart_dir, f"meta_{user_id}.json")
        existing = []
        if not regenerate and os.path.isdir(chart_dir):
            cutoff = _time_module.time() - 86400  # 24 h TTL
            for fname in sorted(os.listdir(chart_dir)):
                if fname.startswith(f"chart_{user_id}_") and fname.endswith(".png"):
                    fpath = os.path.join(chart_dir, fname)
                    if os.path.getmtime(fpath) > cutoff:
                        existing.append(fname)

        if existing and not regenerate:
            # Try loading persisted metadata, fall back to generic names
            import json as _json
            cached_meta: dict[str, dict] = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path) as f:
                        cached_meta = _json.loads(f.read())
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    cached_meta = {}
            cached_charts = []
            for fname in sorted(existing):
                n = fname.replace(f"chart_{user_id}_", "").replace(".png", "")
                meta = cached_meta.get(fname, {})
                cached_charts.append({
                    "filename": fname,
                    "title": meta.get("title", f"Chart {n}"),
                    "description": meta.get("description", "Portfolio chart"),
                    "url": f"/api/v1/portfolio/charts/{user_id}/image/{fname}",
                })
            return {"charts": cached_charts, "count": len(cached_charts), "cached": True}

        # ── Generate charts in thread pool (non-blocking) with 90 s timeout ──
        loop = asyncio.get_running_loop()
        charts = await asyncio.wait_for(
            loop.run_in_executor(
                ThreadPoolExecutor(max_workers=1),
                generate_portfolio_charts,
                user_id,
                chart_dir,
            ),
            timeout=90.0,
        )
        # Persist metadata so cache hits use proper names
        import json as _json
        meta_dict = {c["filename"]: {"title": c["title"], "description": c["description"]} for c in charts}
        try:
            with open(meta_path, "w") as mf:
                _json.dump(meta_dict, mf)
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            pass  # metadata write is best-effort
        return {
            "charts": [
                {
                    "filename": c["filename"],
                    "title": c["title"],
                    "description": c["description"],
                    "url": f"/api/v1/portfolio/charts/{user_id}/image/{c['filename']}",
                }
                for c in charts
            ],
            "count": len(charts),
            "cached": False,
        }
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Chart generation timed out after 90 seconds. Charts will be available on next request.",
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logging.info(f"[CHARTS] Generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 14. GET /portfolio/risk-analysis/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/risk-analysis/{user_id}")
def portfolio_risk_analysis_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_data = [(h.ticker, h.company_name, h.shares, h.buy_price) for h in holdings]

        if not holdings_data:
            return {"user_id": user_id, "holdings_count": 0, "total_portfolio_value": 0,
                    "sector_concentration": [], "portfolio_beta": None, "risk_score": None,
                    "risk_score_label": "Unknown", "concentration_risks": [], "stock_details": []}

        stock_details = []
        total_value = 0.0
        # For correlation: keep (ticker, list_of_daily_returns) indexed by date
        _return_series: dict[str, dict] = {}  # ticker -> {date_str: return_float}

        for ticker, company_name, shares, buy_price in holdings_data:
            ns = _to_ns(ticker)
            info = _yf_fetch_info(ns)
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or buy_price
            beta = info.get("beta")
            sector = info.get("sector") or "Unknown"
            current_value = shares * current_price
            total_value += current_value

            hist_volatility = None
            try:
                t = yf.Ticker(ns)
                hist = t.history(period="90d")
                if not hist.empty and len(hist) > 1:
                    returns = hist["Close"].pct_change().dropna()
                    v = float(returns.std() * (252 ** 0.5) * 100)
                    hist_volatility = round(v, 2) if not math.isnan(v) else None
                    # Store daily returns for correlation
                    daily = {}
                    for idx, val in returns.items():
                        try:
                            dstr = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                            if not math.isnan(float(val)):
                                daily[dstr] = float(val)
                        except Exception as e:
                            import logging
                            logging.error(f"Error occurred: {e}", exc_info=True)
                            raise HTTPException(status_code=500, detail="Internal server error")
                    if daily:
                        _return_series[ticker] = daily
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

            stock_details.append({
                "ticker": ticker,
                "company_name": company_name,
                "shares": shares,
                "current_price": current_price,
                "current_value": round(current_value, 2),
                "beta": round(beta, 3) if beta is not None and not math.isnan(beta) else None,
                "sector": sector,
                "hist_volatility_annualized_pct": hist_volatility,
            })

        # Sector concentration
        sector_map: dict[str, float] = {}
        for s in stock_details:
            sector_map[s["sector"]] = sector_map.get(s["sector"], 0) + s["current_value"]
        sector_concentration = sorted([
            {"sector": sec, "value": round(val, 2),
             "pct": round(val / total_value * 100, 1) if total_value > 0 else 0}
            for sec, val in sector_map.items()
        ], key=lambda x: x["pct"], reverse=True)

        # Beta-weighted portfolio beta
        stocks_with_beta = [s for s in stock_details if s["beta"] is not None]
        portfolio_beta = None
        if stocks_with_beta and total_value > 0:
            covered_value = sum(s["current_value"] for s in stocks_with_beta)
            portfolio_beta = round(
                sum(s["current_value"] / covered_value * s["beta"] for s in stocks_with_beta), 3
            )

        risk_score = min(10, max(1, round(portfolio_beta * 5))) if portfolio_beta is not None else None

        # Concentration risks: stocks > 20% of portfolio
        concentration_risks = sorted([
            {"ticker": s["ticker"], "company_name": s["company_name"],
             "pct_of_portfolio": round(s["current_value"] / total_value * 100, 1),
             "current_value": s["current_value"]}
            for s in stock_details
            if total_value > 0 and (s["current_value"] / total_value) > 0.20
        ], key=lambda x: x["pct_of_portfolio"], reverse=True)[:3]

        for s in stock_details:
            s["portfolio_weight_pct"] = round(s["current_value"] / total_value * 100, 1) if total_value > 0 else 0

        # Pearson correlation: find highest correlated pair
        highest_corr_pair = None
        try:
            highest_corr_pair = compute_pearson_correlation(_return_series)
        except Exception as _corr_err:
            logging.info(f"[RISK] Correlation calc failed: {_corr_err}")

        return {
            "user_id": user_id,
            "total_portfolio_value": round(total_value, 2),
            "holdings_count": len(stock_details),
            "portfolio_beta": portfolio_beta,
            "risk_score": risk_score,
            "risk_score_label": _risk_label(risk_score),
            "sector_concentration": sector_concentration,
            "concentration_risks": concentration_risks,
            "highest_correlation_pair": highest_corr_pair,
            "stock_details": sorted(stock_details, key=lambda x: x["current_value"], reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 15. GET /portfolio/red-flags/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/red-flags/{user_id}")
def portfolio_red_flags_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            held_tickers = [h.ticker for h in holdings]

            if not held_tickers:
                return {"user_id": user_id, "total_flags": 0, "critical": 0,
                        "warnings": 0, "watches": 0, "flags": [],
                        "summary": "No holdings found."}

            latest_analyses: dict[str, dict] = {}
            for ticker in held_tickers:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if row and row.full_json:
                    try:
                        data = json.loads(row.full_json)
                        data["_pledged_pct_db"] = row.promoter_pledged_pct
                        latest_analyses[ticker] = data
                    except Exception as e:
                        import logging
                        logging.error(f"Error occurred: {e}", exc_info=True)
                        raise HTTPException(status_code=500, detail="Internal server error")

            # FII trend: last 4 analyses per ticker (most recent first)
            fii_histories: dict[str, list[float]] = {}
            for ticker in held_tickers:
                rows = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).limit(4).all()
                fiis = []
                for r in rows:
                    try:
                        d = json.loads(r.full_json)
                        fii = d.get("fundamentals_snapshot", {}).get("fii_holding_pct")
                        if fii is not None:
                            fiis.append(float(fii))
                    except Exception as e:
                        import logging
                        logging.error(f"Error occurred: {e}", exc_info=True)
                        raise HTTPException(status_code=500, detail="Internal server error")
                fii_histories[ticker] = fiis

            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            bearish_flips = session.query(SignalEvent).filter(
                SignalEvent.created_at >= cutoff,
                SignalEvent.ticker.in_(held_tickers),
                SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"])
            ).all()
            bearish_flip_map = {f.ticker: (f.from_signal, f.to_signal) for f in bearish_flips}

        try:
            asm_gsm = _get_asm_gsm_lists()
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            asm_gsm = {"ASM": set(), "GSM": set()}

        flags = []
        for ticker in held_tickers:
            analysis = latest_analyses.get(ticker, {})
            fs = analysis.get("fundamentals_snapshot", {})

            pledged = fs.get("promoter_pledged_pct") or analysis.get("_pledged_pct_db")
            if pledged is not None and pledged > 30:
                flags.append({
                    "ticker": ticker,
                    "severity": "CRITICAL",
                    "flag_type": "HIGH_PROMOTER_PLEDGING",
                    "detail": f"Promoter pledging at {pledged:.1f}% (threshold: 30%)",
                })

            t_base = ticker.upper().split(".")[0]
            if t_base in asm_gsm.get("GSM", set()):
                flags.append({
                    "ticker": ticker, "severity": "CRITICAL",
                    "flag_type": "GSM_LISTED",
                    "detail": "Stock on NSE Graded Surveillance Measure (GSM) list",
                })
            elif t_base in asm_gsm.get("ASM", set()):
                flags.append({
                    "ticker": ticker, "severity": "WARNING",
                    "flag_type": "ASM_LISTED",
                    "detail": "Stock on NSE Additional Surveillance Measure (ASM) list",
                })

            if ticker in bearish_flip_map:
                from_sig, to_sig = bearish_flip_map[ticker]
                flags.append({
                    "ticker": ticker, "severity": "WARNING",
                    "flag_type": "BEARISH_SIGNAL_FLIP",
                    "detail": f"Signal flipped {from_sig} → {to_sig} in last 30 days",
                })

            fiis = fii_histories.get(ticker, [])
            if len(fiis) >= 3:
                consecutive_declines = 0
                for i in range(len(fiis) - 1):
                    if fiis[i] < fiis[i + 1]:
                        consecutive_declines += 1
                    else:
                        break
                if consecutive_declines >= 2:
                    fii_str = " → ".join(f"{v:.1f}%" for v in reversed(fiis[:consecutive_declines + 1]))
                    flags.append({
                        "ticker": ticker, "severity": "WATCH",
                        "flag_type": "FII_DECLINING",
                        "detail": f"FII holding declining: {fii_str}",
                    })

        severity_order = {"CRITICAL": 0, "WARNING": 1, "WATCH": 2}
        flags.sort(key=lambda x: severity_order.get(x["severity"], 3))

        summary = "No significant red flags detected across the portfolio."
        if flags:
            try:
                # Red flags summary → DeepSeek V4 Flash (Tier 1 bulk task)
                if os.getenv("DEEPSEEK_API_KEY"):
                    flags_text = "\n".join(
                        f"- [{f['severity']}] {f['ticker']}: {f['detail']}" for f in flags
                    )
                    prompt = (
                        f"Portfolio red flags:\n{flags_text}\n\n"
                        "Write exactly 3 sentences summarizing the biggest risks. "
                        "Be specific about tickers and risk types. Plain English."
                    )
                    summary = _deepseek_chat(
                        [{"role": "user", "content": prompt}],
                        max_tokens=200,
                        log_endpoint="red_flags_summary",
                    ).strip()
            except Exception as e:
                logging.info(f"[RED-FLAGS] Summary call failed: {e}")

        return {
            "user_id": user_id,
            "total_flags": len(flags),
            "critical": sum(1 for f in flags if f["severity"] == "CRITICAL"),
            "warnings": sum(1 for f in flags if f["severity"] == "WARNING"),
            "watches": sum(1 for f in flags if f["severity"] == "WATCH"),
            "flags": flags,
            "summary": summary,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 16. GET /macro-impact/{user_id}
# ---------------------------------------------------------------------------
@router.get("/macro-impact/{user_id}")
def macro_impact_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        now = time.time()
        cached = _dcache_get("macro_impact", str(user_id))
        if cached is not None:
            return cached

        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_data = [(h.ticker, h.company_name) for h in holdings]

        if not holdings_data:
            return {"user_id": user_id, "macro_readings": {}, "impacts": [], "generated_at": datetime.now(timezone.utc).isoformat()}

        macro: dict = {}
        for sym, key in [("BZ=F", "brent_oil_usd"), ("^INDIAVIX", "india_vix"), ("USDINR=X", "usd_inr")]:
            try:
                info = yf.Ticker(sym).info
                val = info.get("regularMarketPrice") or info.get("currentPrice")
                macro[key] = round(float(val), 2) if val and not math.isnan(float(val)) else None
            except Exception as e:
                import logging
                logging.warning(f"Caught exception: {e}")
                macro[key] = None
        macro["rbi_repo_rate_pct"] = 6.50

        holdings_list = "\n".join(f"- {t}: {c}" for t, c in holdings_data)
        macro_str = (
            f"Brent crude: ${macro.get('brent_oil_usd', 'N/A')}/bbl, "
            f"India VIX: {macro.get('india_vix', 'N/A')}, "
            f"USD/INR: {macro.get('usd_inr', 'N/A')}, "
            f"RBI repo rate: {macro.get('rbi_repo_rate_pct')}%"
        )
        prompt = (
            f"Current Indian macro environment: {macro_str}\n\n"
            f"Holdings:\n{holdings_list}\n\n"
            "For each ticker write one sentence on macro impact and classify direction. "
            "Return ONLY valid JSON array, no markdown:\n"
            '[{"ticker": "TICKER", "impact_statement": "...", "direction": "positive|negative|neutral"}]'
        )

        # Macro impact → DeepSeek V4 Flash (Tier 1 bulk task)
        impacts = []
        if os.getenv("DEEPSEEK_API_KEY"):
            try:
                raw_text = _deepseek_chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=1500,
                    temperature=0,
                    log_endpoint="macro_impact",
                )
                raw = _extract_json_from_text(raw_text)
                parsed = json.loads(raw)
                for item in parsed:
                    if item.get("direction") not in ("positive", "negative", "neutral"):
                        item["direction"] = "neutral"
                impacts = parsed
            except Exception as e:
                logging.info(f"[MACRO-IMPACT] AI call failed: {e}")
                impacts = [{"ticker": t, "impact_statement": "Macro assessment unavailable.", "direction": "neutral"} for t, _ in holdings_data]
        else:
            impacts = [{"ticker": t, "impact_statement": "DeepSeek API key not configured.", "direction": "neutral"} for t, _ in holdings_data]

        result = {
            "user_id": user_id,
            "macro_readings": macro,
            "impacts": impacts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _dcache_set("macro_impact", str(user_id), result, ttl=_MACRO_IMPACT_TTL)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 17. GET /portfolio/timeframe-conflicts/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/timeframe-conflicts/{user_id}")
def portfolio_timeframe_conflicts_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            held_tickers = [h.ticker for h in holdings]

            conflicts = []
            for ticker in held_tickers:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if not row or not row.full_json:
                    continue
                try:
                    data = json.loads(row.full_json)
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    continue

                current_price = data.get("current_price_inr")
                tp = data.get("target_prices") or {}
                short_target = tp.get("short_term_3m")
                long_target = tp.get("long_term_36m")

                if not all([current_price, short_target, long_target]) or current_price <= 0:
                    continue

                short_dir = "up" if short_target > current_price else "down"
                long_dir = "up" if long_target > current_price else "down"

                if short_dir == long_dir:
                    continue

                short_upside = round((short_target - current_price) / current_price * 100, 1)
                long_upside = round((long_target - current_price) / current_price * 100, 1)

                if short_dir == "down" and long_dir == "up":
                    explanation = (
                        f"{ticker} shows near-term caution ({short_upside:+.1f}% to ₹{short_target:.0f} in 3M) "
                        f"but long-term recovery expected ({long_upside:+.1f}% to ₹{long_target:.0f} in 3Y). "
                        "Consider holding through short-term weakness if long-term thesis is intact."
                    )
                else:
                    explanation = (
                        f"{ticker} has near-term upside ({short_upside:+.1f}% to ₹{short_target:.0f} in 3M) "
                        f"but faces long-term headwinds ({long_upside:+.1f}% to ₹{long_target:.0f} in 3Y). "
                        "Consider taking near-term gains; long-term outlook is uncertain."
                    )

                conflicts.append({
                    "ticker": ticker,
                    "company_name": data.get("company_name", ticker),
                    "current_price": current_price,
                    "short_term_target": short_target,
                    "long_term_target": long_target,
                    "short_term_direction": short_dir,
                    "long_term_direction": long_dir,
                    "short_upside_pct": short_upside,
                    "long_upside_pct": long_upside,
                    "explanation": explanation,
                    "analysis_date": row.analysis_date,
                    "signal": data.get("signal"),
                })

        return {"user_id": user_id, "conflict_count": len(conflicts), "conflicts": conflicts}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 18. POST /trade-journal
# ---------------------------------------------------------------------------
@router.post("/trade-journal")
def trade_journal_add_endpoint(req: TradeJournalAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    action = req.action.upper()
    if action not in ("BUY", "SELL", "HOLD", "WATCH"):
        raise HTTPException(status_code=400, detail="action must be BUY, SELL, HOLD, or WATCH")
    if req.price_at_time <= 0:
        raise HTTPException(status_code=400, detail="price_at_time must be > 0")
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            entry = TradeJournal(
                user_id=req.user_id,
                ticker=ticker,
                action=action,
                price_at_time=req.price_at_time,
                reason_text=req.reason_text.strip(),
                outcome_text=req.outcome_text.strip() if req.outcome_text else None,
            )
            # Set optional new columns gracefully (only if col exists in DB after migration)
            try:
                entry.company_name = req.company_name
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")
            try:
                entry.mood = req.mood
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")
            session.add(entry)
            session.commit()
            session.refresh(entry)
            entry_id = entry.id
        return {"success": True, "entry_id": entry_id, "ticker": ticker, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 19. GET /trade-journal/{user_id}
# ---------------------------------------------------------------------------
@router.get("/trade-journal/{user_id}")
def trade_journal_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            entries = session.query(TradeJournal).filter_by(
                user_id=user_id
            ).order_by(TradeJournal.created_at.desc()).all()
            result = []
            for e in entries:
                row = {
                    "id": e.id,
                    "ticker": e.ticker,
                    "action": e.action,
                    "price_at_time": e.price_at_time,
                    "reason_text": e.reason_text,
                    "outcome_text": e.outcome_text,
                    "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
                }
                # Gracefully include new columns if they exist post-migration
                try:
                    row["company_name"] = getattr(e, "company_name", None)
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    row["company_name"] = None
                try:
                    row["mood"] = getattr(e, "mood", None)
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    row["mood"] = None
                try:
                    upd = getattr(e, "updated_at", None)
                    row["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    row["updated_at"] = None
                result.append(row)
        return {"user_id": user_id, "entries": result, "total": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 20. PUT /trade-journal/{entry_id}
# ---------------------------------------------------------------------------
@router.put("/trade-journal/{entry_id}")
def trade_journal_update_endpoint(entry_id: int, req: TradeJournalUpdateRequest, user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    """Update outcome_text and mood on a trade journal entry. user_id passed as query param."""
    try:
        with get_session() as session:
            entry = session.query(TradeJournal).filter_by(id=entry_id).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Entry not found")
            if entry.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to edit this entry")
            entry.outcome_text = req.outcome_text.strip()
            try:
                entry.mood = req.mood
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")
            try:
                entry.updated_at = datetime.now(timezone.utc)
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")
            session.commit()
            session.refresh(entry)
            result = {
                "id": entry.id,
                "ticker": entry.ticker,
                "action": entry.action,
                "price_at_time": entry.price_at_time,
                "reason_text": entry.reason_text,
                "outcome_text": entry.outcome_text,
                "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "",
            }
            try:
                result["company_name"] = getattr(entry, "company_name", None)
                result["mood"] = getattr(entry, "mood", None)
                upd = getattr(entry, "updated_at", None)
                result["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
            except Exception as e:
                import logging
                logging.error(f"Error occurred: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 21. DELETE /trade-journal/{entry_id}
# ---------------------------------------------------------------------------
@router.delete("/trade-journal/{entry_id}")
def trade_journal_delete_endpoint(entry_id: int, user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    """Delete a trade journal entry. user_id passed as query param."""
    try:
        with get_session() as session:
            entry = session.query(TradeJournal).filter_by(id=entry_id).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Entry not found")
            if entry.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this entry")
            session.delete(entry)
            session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 22. GET /trade-journal/{user_id}/stats
# ---------------------------------------------------------------------------
@router.get("/trade-journal/{user_id}/stats")
def trade_journal_stats_endpoint(user_id: int, auth_user_id: int = Depends(require_auth)):
    """
    Compute analytics over all journal entries for a user. Auth required.

    Args:
        user_id (int): The user_id.
        auth_user_id (int): The auth_user_id.

    Returns:
        Any: The response.
    """
    try:
        with get_session() as session:
            user = session.get(User, auth_user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {auth_user_id} not found")
            entries = session.query(TradeJournal).filter_by(user_id=auth_user_id).all()
            entries_data = []
            for e in entries:
                entries_data.append({
                    "ticker": e.ticker,
                    "action": e.action,
                    "reason_text": e.reason_text or "",
                    "outcome_text": (e.outcome_text or "").lower(),
                })

        stats = compute_trade_journal_stats(entries_data)
        total_entries = stats["total_entries"]

        # Trade journal pattern detection → DeepSeek V4 Flash (Tier 1 bulk task)
        patterns = []
        try:
            all_reasons = " | ".join(e["reason_text"] for e in entries_data if e["reason_text"])
            if all_reasons and os.getenv("DEEPSEEK_API_KEY"):
                prompt = (
                    f'Find 2 patterns in these trade journal reasons: {all_reasons[:2000]}. '
                    'Return JSON: [{"pattern": str}]'
                )
                raw_text = _deepseek_chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=150,
                    log_endpoint="trade_journal_stats",
                )
                raw = _extract_json_from_text(raw_text)
                patterns = json.loads(raw)
                if not isinstance(patterns, list):
                    patterns = []
        except Exception as _pe:
            logging.info(f"[TJ-STATS] Pattern AI call failed: {_pe}")
            patterns = []

        return {
            "user_id": user_id,
            **stats,
            "patterns": patterns,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 23. GET /portfolio/export/pdf/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/export/pdf/{user_id}")
def export_portfolio_pdf(user_id: int, authorization: str = Header(None)):
    """Generate a deterministic, factual portfolio summary PDF (no LLM call, no advice)."""
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not FPDF2_AVAILABLE:
        raise HTTPException(status_code=503, detail="PDF export unavailable")
    try:
        import io

        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_snap = [(h.ticker, h.company_name, h.shares, h.buy_price) for h in holdings]
            tickers = [t for t, _, _, _ in holdings_snap]

            # Watch items: factual flags only (pledging is a company-level fact).
            red_flag_list = []
            cutoff30 = datetime.now(timezone.utc) - timedelta(days=30)
            bf_map = {
                f.ticker for f in session.query(SignalEvent).filter(
                    SignalEvent.created_at >= cutoff30,
                    SignalEvent.ticker.in_(tickers),
                    SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"]),
                ).all()
            }
            for ticker in tickers:
                pledged_row = session.query(AnalysisHistory.promoter_pledged_pct).filter(
                    AnalysisHistory.ticker == ticker,
                    AnalysisHistory.promoter_pledged_pct.isnot(None),
                ).order_by(AnalysisHistory.created_at.desc()).first()
                pledged = pledged_row[0] if pledged_row else None
                if pledged is not None and pledged > 30:
                    red_flag_list.append(f"{ticker}: Promoter pledging {pledged:.1f}%")
                if ticker in bf_map:
                    red_flag_list.append(f"{ticker}: Signal turned bearish in the last 30 days")

        # Holdings with no live price show N/A and are left out of BOTH totals,
        # so a failed fetch never reads as a loss.
        rows = []
        total_invested = 0.0
        total_current = 0.0
        unpriced = 0
        for ticker, _company, shares, buy_price in holdings_snap:
            current_price, _ = _yf_price(_to_ns(ticker))
            invested = shares * buy_price
            if not (current_price and current_price > 0):  # None, 0 or NaN
                unpriced += 1
                rows.append((ticker, shares, invested, None, None))
                continue
            current_val = shares * current_price
            pnl_pct = (current_val - invested) / invested * 100 if invested > 0 else None
            total_invested += invested
            total_current += current_val
            rows.append((ticker, shares, invested, current_val, pnl_pct))

        def _rs(value):
            # Core Helvetica font is latin-1 only, so no rupee glyph.
            return format_indian_currency(value, symbol="Rs. ")

        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Helvetica", style="B", size=16)
            pdf.cell(0, 10, "Portfolio Summary", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=9)
            pdf.cell(0, 6, f"Generated on {date.today().strftime('%d %b %Y')}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

            widths = (40, 25, 42, 42, 31)
            pdf.set_font("Helvetica", style="B", size=10)
            for w, head in zip(widths, ("Ticker", "Shares", "Invested", "Current value", "P&L %")):
                pdf.cell(w, 8, head, border=1)
            pdf.ln(8)
            pdf.set_font("Helvetica", size=10)
            for ticker, shares, invested, current_val, pnl_pct in rows:
                cells = (
                    ticker, f"{shares:.4f}".rstrip("0").rstrip("."), _rs(invested),
                    "N/A" if current_val is None else _rs(current_val),
                    "N/A" if pnl_pct is None else f"{pnl_pct:+.1f}%",
                )
                for w, text in zip(widths, cells):
                    pdf.cell(w, 7, text, border=1)
                pdf.ln(7)
            if not rows:
                pdf.cell(0, 7, "No holdings found.", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(4)
            pdf.set_font("Helvetica", style="B", size=11)
            pdf.cell(0, 7, f"Total invested: {_rs(total_invested)}", new_x="LMARGIN", new_y="NEXT")
            pnl_txt = f"  ({(total_current - total_invested) / total_invested * 100:+.1f}%)" if total_invested > 0 else ""
            pdf.cell(0, 7, f"Current value: {_rs(total_current)}{pnl_txt}", new_x="LMARGIN", new_y="NEXT")
            if unpriced:
                pdf.set_font("Helvetica", style="I", size=9)
                pdf.cell(0, 6, f"Totals exclude {unpriced} holding(s) with no live price.", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", style="B", size=11)

            pdf.ln(4)
            pdf.cell(0, 7, "Watch items", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
            for flag in red_flag_list or ["None detected"]:
                pdf.cell(0, 6, f"- {flag}", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(6)
            pdf.set_font("Helvetica", style="I", size=8)
            pdf.multi_cell(0, 5, "Informational summary only. Not investment advice.")
            pdf_bytes = bytes(pdf.output())
        except Exception as _pdfe:
            logging.error(f"[PDF-EXPORT] fpdf2 render failed: {_pdfe}", exc_info=True)
            raise HTTPException(status_code=500, detail="PDF export failed")

        today_str = date.today().strftime("%Y%m%d")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=portfolio_summary_{today_str}.pdf"},
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("[PDF-EXPORT] Top-level error")
        raise HTTPException(status_code=503, detail="Portfolio review unavailable. Please try again later.")


# ---------------------------------------------------------------------------
# 24. GET /api/v1/market/net-worth-ledger/{user_id}
# ---------------------------------------------------------------------------
# format_indian_currency is imported from helpers (canonical location)


@router.get("/api/v1/market/net-worth-ledger/{user_id}", response_model=NetWorthSnapshotResponse)
async def net_worth_ledger_endpoint(
    user_id: int,
    authorization: str = Header(None),
):
    """
    Return the latest net-worth snapshot for a user.
All monetary values use Indian Lakhs/Crores formatting.
Requires valid JWT. Returns 404 if no snapshot exists yet.

    Args:
        user_id (int): The user_id.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    # Auth guard
    authed_user_id = require_auth(authorization)
    if authed_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    with get_session() as session:
        row = (
            session.query(NetWorthLedger)
            .filter(NetWorthLedger.user_id == user_id)
            .order_by(NetWorthLedger.snapshot_date.desc())
            .first()
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No net-worth snapshot found. Add portfolio holdings to generate one.",
        )

    return NetWorthSnapshotResponse(
        user_id=user_id,
        snapshot_date=row.snapshot_date,
        total_value_formatted=format_indian_currency(row.total_value_inr),
        daily_delta_formatted=(
            format_indian_currency(row.daily_delta_inr) if row.daily_delta_inr is not None else None
        ),
        daily_delta_pct=row.daily_delta_pct,
        peak_value_formatted=(
            format_indian_currency(row.peak_value_inr) if row.peak_value_inr is not None else None
        ),
        top_gainer_ticker=row.top_gainer_ticker,
        top_gainer_pct=row.top_gainer_pct,
        top_loser_ticker=row.top_loser_ticker,
        top_loser_pct=row.top_loser_pct,
    )

@router.get("/attribution/{user_id}")
async def portfolio_attribution_endpoint(
    user_id: int,
    authorization: str = Header(None)
):
    authed_user_id = require_auth(authorization)
    if authed_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings"
        ).all()

    if not holdings:
        return {"sectors": []}

    sector_data = defaultdict(lambda: {"total_value": 0.0, "total_pnl": 0.0, "invested": 0.0})
    portfolio_total_value = 0.0
    portfolio_total_pnl = 0.0

    for h in holdings:
        try:
            t = yf.Ticker(_resolve_ticker(h.ticker, "NSE"))
            info = t.fast_info
            current_price = getattr(info, "last_price", None)
            info_dict = {}
            if current_price is None or math.isnan(current_price):
                info_dict = t.info
                current_price = info_dict.get("currentPrice") or info_dict.get("regularMarketPrice") or h.buy_price
            else:
                info_dict = t.info
            
            sector = info_dict.get("sector", "Unknown")
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            current_price = h.buy_price
            sector = "Unknown"
        
        invested = h.shares * h.buy_price
        val = h.shares * current_price
        pnl = val - invested
        
        sector_data[sector]["total_value"] += val
        sector_data[sector]["invested"] += invested
        sector_data[sector]["total_pnl"] += pnl
        
        portfolio_total_value += val
        portfolio_total_pnl += pnl

    results = []
    for sector, data in sector_data.items():
        val = data["total_value"]
        pnl = data["total_pnl"]
        weight = (val / portfolio_total_value * 100) if portfolio_total_value > 0 else 0.0
        contrib = (pnl / portfolio_total_pnl * 100) if portfolio_total_pnl != 0 else 0.0
        
        results.append({
            "sector": sector,
            "weight_pct": round(weight, 2),
            "total_value": round(val, 2),
            "total_pnl": round(pnl, 2),
            "contribution_to_total_pnl_pct": round(contrib, 2)
        })

    results.sort(key=lambda x: abs(x["contribution_to_total_pnl_pct"]), reverse=True)
    
    return {"sectors": results}

@router.get("/signal-accuracy")
def get_signal_accuracy():
    """
    Returns accuracy % by signal type.

    Args:

    Returns:
        Any: The response.
    """
    try:
        from database import AnalysisHistory, get_session
        with get_session() as db:
            rows = db.query(AnalysisHistory.signal, AnalysisHistory.was_correct).filter(AnalysisHistory.was_correct != None).all()
            stats = {}
            for row in rows:
                sig = row.signal.upper() if row.signal else "HOLD"
                if sig not in stats:
                    stats[sig] = {"total": 0, "correct": 0}
                stats[sig]["total"] += 1
                if row.was_correct:
                    stats[sig]["correct"] += 1
            
            resp = []
            for sig, data in stats.items():
                total = data["total"]
                correct = data["correct"]
                accuracy_pct = (correct / total * 100) if total > 0 else 0
                resp.append({
                    "signal": sig,
                    "total": total,
                    "correct": correct,
                    "accuracy_pct": round(accuracy_pct, 2)
                })
            return resp
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal server error")

from database import PortfolioTransaction
from typing import Literal as _Literal
from pydantic import Field as _Field, field_validator as _field_validator

class MultiAssetTransactionRequest(_BaseModel):
    user_id: int
    # Allowed values mirror the CHECK constraints on multi_asset_transactions.
    asset_type: _Literal["STOCK", "MF", "GOLD", "FD"]
    symbol: str = _Field(..., min_length=1, max_length=50)
    transaction_type: _Literal["BUY", "SELL", "DEPOSIT", "WITHDRAWAL", "MATURITY"]
    quantity: float = _Field(..., gt=0, allow_inf_nan=False)
    price: float = _Field(..., ge=0, allow_inf_nan=False)
    fees: float = _Field(0.0, ge=0, allow_inf_nan=False)
    notes: _Optional[str] = _Field(None, max_length=500)

    @_field_validator("asset_type", "transaction_type", mode="before")
    @classmethod
    def _upper(cls, v):
        # Keep accepting lowercase input from existing clients.
        return v.strip().upper() if isinstance(v, str) else v

@router.post("/portfolio/multi-asset/transaction")
def multi_asset_transaction_entry(req: MultiAssetTransactionRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        with get_session() as session:
            tx = PortfolioTransaction(
                user_id=req.user_id,
                asset_type=req.asset_type.upper(),
                symbol=req.symbol.upper(),
                transaction_type=req.transaction_type.upper(),
                quantity=req.quantity,
                price=req.price,
                fees=req.fees,
                notes=req.notes
            )
            session.add(tx)
            session.commit()
            return {"success": True, "transaction_id": tx.id}
    except Exception as e:
        import logging
        logging.error(f"Error saving multi-asset transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/portfolio/multi-asset/transactions/{user_id}")
def multi_asset_transactions_history(user_id: int, asset_type: _Optional[str] = None, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        with get_session() as session:
            query = session.query(PortfolioTransaction).filter(PortfolioTransaction.user_id == user_id)
            if asset_type:
                query = query.filter(PortfolioTransaction.asset_type == asset_type.upper())
            
            transactions = query.order_by(PortfolioTransaction.date.desc()).all()
            
            return [
                {
                    "id": tx.id,
                    "asset_type": tx.asset_type,
                    "symbol": tx.symbol,
                    "transaction_type": tx.transaction_type,
                    "quantity": tx.quantity,
                    "price": tx.price,
                    "fees": tx.fees,
                    "date": tx.date.isoformat() if tx.date else None,
                    "notes": tx.notes
                }
                for tx in transactions
            ]
    except Exception as e:
        import logging
        logging.error(f"Error fetching multi-asset transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
