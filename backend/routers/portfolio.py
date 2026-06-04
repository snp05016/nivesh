"""
Portfolio-related endpoints extracted from main.py.
"""
import json
import time
import math
import random
import threading
from datetime import datetime, date, timedelta
from typing import Optional
from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
import yfinance as yf

from helpers import (
    get_session, verify_access_token, EXCHANGE_SUFFIX, _resolve_ticker,
    _to_ns, _yf_price, _yf_fetch_info, _dcache_get, _dcache_set,
    _quick_info_cache, _QUICK_INFO_TTL, DataHarvestingError,
    User, Portfolio, AnalysisHistory, SignalEvent, PriceTarget,
    TradeJournal, PortfolioValuationHistory, PKScreenerSignal,
    MacroEvent, NetWorthLedger, AdvisorInsight,
    PortfolioAddRequest, PortfolioRemoveRequest, PortfolioUpdateRequest,
    PortfolioNoteRequest, TradeJournalAddRequest, TradeJournalUpdateRequest,
    _check_rate_limit, _get_analyze_semaphore, _running_analyses,
    _dash_start_job, _dash_end_job, _dash_update_harvest,
    _extract_json_from_text, _log_token_usage,
    require_auth,
)

import importlib.util as _importlib_util
FPDF2_AVAILABLE = _importlib_util.find_spec("fpdf2") is not None
if FPDF2_AVAILABLE:
    from fpdf import FPDF

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font as XLFont, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from services.staleness import compute_staleness
from services.piotroski import compute_piotroski

import os
import openai as _openai_lib

def _get_deepseek_client() -> "_openai_lib.OpenAI":
    """Return a lazily-constructed DeepSeek OpenAI-compatible client."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    return _openai_lib.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        timeout=60.0,
    )


def _deepseek_chat(
    messages: list[dict],
    *,
    max_tokens: int = 512,
    temperature: float = 0.3,
    log_endpoint: str | None = None,
) -> str:
    """
    Call DeepSeek V4 Flash via OpenAI-compatible API.
    V4 Flash is a thinking model — reasoning_content consumes max_tokens before
    final answer is generated, so we set max_tokens generously.
    """
    import time as _time
    client = _get_deepseek_client()
    last_err = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.choices[0].message.content or ""
            if log_endpoint:
                _log_token_usage(log_endpoint, response.usage)
            return text
        except Exception as exc:
            last_err = exc
            wait = 2 ** attempt + random.random() * 0.5
            print(f"[DeepSeek] attempt {attempt+1} failed: {exc} — retrying in {wait:.1f}s")
            _time.sleep(wait)
    raise last_err


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


_INDICES_TICKERS = [
    ("^NSEI",      "Nifty 50"),
    ("^BSESN",     "Sensex"),
    ("^NSEBANK",   "Nifty Bank"),
    ("^CNXIT",     "Nifty IT"),
    ("^CNXMIDCAP", "Nifty Midcap 100"),
    ("USDINR=X",   "USD/INR"),
]

_indices_cache: dict = {"data": None, "ts": 0}

_INDICES_CACHE_TTL = 300  # 5 minutes


def _get_indices_data() -> dict:
    """Fetch and cache market indices data. Used by both /market-indices and /morning-summary."""
    now = time.time()
    if _indices_cache["data"] is not None and (now - _indices_cache["ts"]) < _INDICES_CACHE_TTL:
        return _indices_cache["data"]

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
                        # Fallback 1: Standard info
                        full_info = t.info
                        current = full_info.get("currentPrice") or full_info.get("regularMarketPrice")
                        prev_close = full_info.get("previousClose") or full_info.get("regularMarketPreviousClose")
                    
                    if current is None or math.isnan(current):
                        # Fallback 2: History (Reliable for indices)
                        hist = t.history(period="5d")
                        if not hist.empty and len(hist) >= 2:
                            current = float(hist["Close"].iloc[-1])
                            prev_close = float(hist["Close"].iloc[-2])
                    
                    if current is not None and not math.isnan(current):
                        break
                except Exception as e:
                    print(f"[YF] Indices attempt {attempt+1} failed for {ticker}: {e}")
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
            print(f"[indices] Skipping {ticker}: {e}")
            continue

    payload = {
        "indices": result,
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _indices_cache["data"] = payload
    _indices_cache["ts"] = now
    return payload


router = APIRouter(tags=["Portfolio"])

# ---------------------------------------------------------------------------
# Local caches & helpers needed by endpoints
# ---------------------------------------------------------------------------
_morning_cache: dict = {}  # {user_id: {"data": {...}, "ts": float}}
_MORNING_CACHE_TTL = 7200  # 2 hours

_macro_impact_cache: dict[int, tuple[float, dict]] = {}  # {user_id: (expiry_ts, data)}
_MACRO_IMPACT_TTL = 7200  # 2 hours

_asm_gsm_cache = {"data": {}, "ts": 0}
_ASM_GSM_CACHE_TTL = 21600  # 6 hours


def _nse_session():
    """Bootstrap a session with NSE cookies."""
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=8)
    except: pass
    return s


def _get_asm_gsm_lists():
    """Fetch and cache ASM/GSM lists from NSE."""
    global _asm_gsm_cache
    now = time.time()
    if _asm_gsm_cache["ts"] > 0 and (now - _asm_gsm_cache["ts"]) < _ASM_GSM_CACHE_TTL:
        return _asm_gsm_cache["data"]

    print("[NSE] Refreshing ASM/GSM lists...")
    data = {"ASM": set(), "GSM": set()}
    try:
        session = _nse_session()
        # ASM Long Term
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=longTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())
        
        # ASM Short Term
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=shortTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())

        # GSM
        resp = session.get("https://www.nseindia.com/api/surveillance-gsm-list", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["GSM"].add(sym.upper())

        _asm_gsm_cache = {"data": data, "ts": now}
        return data
    except Exception as e:
        print(f"[NSE] ASM/GSM fetch failed: {e}")
        return data


def _risk_label(score: int | None) -> str:
    if score is None: return "Unknown"
    if score <= 3: return "Low"
    if score <= 6: return "Moderate"
    if score <= 8: return "High"
    return "Very High"


# ---------------------------------------------------------------------------
# 1. GET /portfolio/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/{user_id}")
def portfolio_endpoint(user_id: int, authorization: str = Header(None)):
    # Auth optional — personal app, user_id scoping is sufficient
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is not None and token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")

            holdings = session.query(Portfolio).filter(
                Portfolio.user_id == user_id,
                Portfolio.group_name != "watchlist",
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

        rows = []
        total_invested = 0.0
        total_current = 0.0

        for h in holdings:
            ns = _to_ns(h.ticker)
            current_price, prev_close = _yf_price(ns)

            invested = h.shares * h.buy_price
            current_value = h.shares * current_price if current_price else 0.0
            pnl = current_value - invested if current_value > 0 else 0.0
            pnl_pct = (pnl / invested * 100) if invested > 0 and current_value > 0 else 0.0
            day_change_pct = 0.0
            if current_price and prev_close and prev_close > 0:
                day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

            total_invested += invested
            total_current += current_value

            rows.append({
                "ticker": h.ticker,
                "company_name": h.company_name,
                "group": h.group_name,
                "shares": h.shares,
                "buy_price": h.buy_price,
                "purchase_date": getattr(h, "purchase_date", "N/A"),
                "notes": getattr(h, "notes", ""),
                "target_price": getattr(h, "target_price", 0.0),
                "current_price": current_price or 0.0,
                "day_change_pct": day_change_pct,
                "invested_inr": round(invested, 2),
                "current_value_inr": round(current_value, 2),
                "pnl_inr": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "notes": h.notes or "",
                "staleness": compute_staleness(
                    last_analyses.get(h.ticker),
                    day_change_pct,
                    last_signals.get(h.ticker, "HOLD"),
                ),
            })

        total_pnl = total_current - total_invested

        return {
            "user": user.display_name,
            "user_id": user_id,
            "as_of": datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC"),
            "total_invested_inr": round(total_invested, 2),
            "total_current_inr": round(total_current, 2),
            "total_pnl_inr": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_invested * 100), 2) if total_invested > 0 else 0,
            "holdings": sorted(rows, key=lambda x: (x["pnl_pct"] or 0), reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 2. GET /portfolio/history/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/history/{user_id}")
def portfolio_history_endpoint(user_id: int, days: int = 30, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
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
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    now = time.time()

    # Check cache
    cached = _morning_cache.get(user_id)
    if cached and (now - cached["ts"]) < _MORNING_CACHE_TTL:
        return cached["data"]

    generated_at = datetime.utcnow().strftime("%H:%M")

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

            # Get last known signal for each ticker from analysis_history
            last_signals: dict[str, str] = {}
            for h in holdings:
                row = (
                    session.query(AnalysisHistory)
                    .filter(AnalysisHistory.user_id == user_id, AnalysisHistory.ticker == h.ticker)
                    .order_by(AnalysisHistory.created_at.desc())
                    .first()
                )
                if row:
                    last_signals[h.ticker] = row.signal

        # Fetch prices and compute movers
        holding_lines = []
        mover_tickers = []
        significant_movers_lines = []

        for h in holdings:
            ns = _to_ns(h.ticker)
            try:
                current_price, prev_close = _yf_price(ns)
            except Exception:
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
        except Exception:
            pass

        portfolio_text = "\n".join(holding_lines) if holding_lines else "No holdings found."
        movers_text = "\n".join(significant_movers_lines) if significant_movers_lines else "None today"
        signals_text = "\n".join(signal_lines) if signal_lines else "No analysis available."
        indices_text = "\n".join(indices_lines) if indices_lines else "Data unavailable."

        prompt = f"""You are a friendly Indian stock market advisor. Write a short morning brief (4-6 bullet points) for an investor based on their portfolio data. Write in simple English. Be specific about which stocks to watch and why. Mention any big movers. Flag anything concerning. End with one sentence on overall market mood. Use Indian number format (lakhs/crores). Be warm and helpful.

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
        import os
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        HAIKU_MODEL = "claude-haiku-4-5-20251001"
        if not api_key or api_key == "placeholder":
            _morning_cache[user_id] = {"data": fallback, "ts": now}
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
                print(f"[Anthropic] Morning summary attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))
        _log_token_usage("morning_summary", response.usage)

        raw = _extract_json_from_text(response.content[0].text)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse morning summary JSON: {e}")
            parsed = fallback

        result = {
            "summary": parsed.get("summary", fallback["summary"]),
            "movers": parsed.get("movers", mover_tickers),
            "mood": parsed.get("mood", "cautious"),
            "generated_at": generated_at,
        }

        # Validate mood value
        if result["mood"] not in ("positive", "cautious", "negative"):
            result["mood"] = "cautious"

        # Build prioritised action list for today
        priority_items = []

        # Priority 1: Triggered alerts
        try:
            with get_session() as session:
                triggered = session.query(PriceTarget).filter(
                    PriceTarget.user_id == user_id,
                    PriceTarget.triggered == True
                ).all()
                for a in triggered:
                    priority_items.append({
                        "priority": 1,
                        "type": "alert_triggered",
                        "ticker": a.ticker,
                        "message": f"Price alert triggered: {a.ticker} {a.direction} ₹{a.target_price:.0f}",
                    })
        except Exception as e:
            print(f"[MORNING] Alert priority check failed: {e}")

        # Priority 2: Signal changes in last 24h for held stocks
        try:
            cutoff = datetime.utcnow() - timedelta(hours=24)
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
                    priority_items.append({
                        "priority": 2,
                        "type": "signal_change",
                        "ticker": f.ticker,
                        "message": f"{f.ticker}: signal changed {f.from_signal} → {f.to_signal}",
                    })
        except Exception as e:
            print(f"[MORNING] Signal change priority check failed: {e}")

        priority_items.sort(key=lambda x: x["priority"])
        result["priority_items"] = priority_items

        _morning_cache[user_id] = {"data": result, "ts": now}
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[morning-summary] Error: {e}")
        _morning_cache[user_id] = {"data": fallback, "ts": now}
        return fallback


# ---------------------------------------------------------------------------
# 5. POST /portfolio & 6. POST /portfolio/add
# ---------------------------------------------------------------------------
@router.post("/portfolio")
@router.post("/portfolio/add")
def portfolio_add_endpoint(req: PortfolioAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is not None and token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not req.ticker or not req.ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker cannot be empty.")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            existing = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="holdings"
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="Holding already exists. Use /portfolio/update to modify.")

            new_holding = Portfolio(
                user_id=req.user_id,
                ticker=ticker,
                company_name=req.company_name,
                shares=req.shares,
                buy_price=req.buy_price,
                group_name="holdings",
            )
            session.add(new_holding)
            session.commit()

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        invested = req.shares * req.buy_price
        current_value = req.shares * current_price if current_price else 0.0
        pnl = current_value - invested if current_value > 0 else 0.0
        pnl_pct = (pnl / invested * 100) if invested > 0 and current_value > 0 else 0.0
        day_change_pct = 0.0
        if current_price and prev_close and prev_close > 0:
            day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": req.company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or 0.0,
            "day_change_pct": day_change_pct,
            "invested_inr": round(invested, 2),
            "current_value_inr": round(current_value, 2),
            "pnl_inr": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 7. DELETE /portfolio/remove
# ---------------------------------------------------------------------------
@router.delete("/portfolio/remove")
def portfolio_remove_endpoint(req: PortfolioRemoveRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="holdings"
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Holding not found.")
            session.delete(holding)
            session.commit()
        return {"success": True, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 8. PUT /portfolio/update
# ---------------------------------------------------------------------------
@router.put("/portfolio/update")
def portfolio_update_endpoint(req: PortfolioUpdateRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="holdings"
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Holding not found.")
            holding.shares = req.shares
            holding.buy_price = req.buy_price
            session.commit()
            company_name = holding.company_name

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        invested = req.shares * req.buy_price
        current_value = req.shares * current_price if current_price else 0.0
        pnl = current_value - invested if current_value > 0 else 0.0
        pnl_pct = (pnl / invested * 100) if invested > 0 and current_value > 0 else 0.0
        day_change_pct = 0.0
        if current_price and prev_close and prev_close > 0:
            day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or 0.0,
            "day_change_pct": day_change_pct,
            "invested_inr": round(invested, 2),
            "current_value_inr": round(current_value, 2),
            "pnl_inr": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 9. GET /portfolio/signal-warnings
# ---------------------------------------------------------------------------
@router.get("/portfolio/signal-warnings")
def portfolio_signal_warnings(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    """Return tickers where signal flipped or is BEARISH/CAUTIOUSLY BEARISH for held stocks."""
    warnings = []
    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings"
        ).all()

        for h in holdings:
            rows = (
                session.query(AnalysisHistory)
                .filter(AnalysisHistory.ticker == h.ticker)
                .order_by(AnalysisHistory.created_at.desc())
                .limit(2)
                .all()
            )

            if not rows:
                continue

            latest = rows[0]
            prev = rows[1] if len(rows) > 1 else None

            signal_flipped = prev is not None and prev.signal != latest.signal
            confidence_dropped = (
                prev is not None
                and latest.confidence_pct is not None
                and prev.confidence_pct is not None
                and (prev.confidence_pct - latest.confidence_pct) > 20
            )
            is_bearish = latest.signal in ("BEARISH", "CAUTIOUSLY BEARISH")

            if signal_flipped or confidence_dropped or is_bearish:
                warnings.append({
                    "ticker": h.ticker,
                    "current_signal": latest.signal,
                    "previous_signal": prev.signal if prev else None,
                    "signal_flipped": signal_flipped,
                    "confidence_dropped": confidence_dropped,
                    "is_bearish": is_bearish,
                    "analysis_date": latest.analysis_date,
                })

    return {"warnings": warnings}


# ---------------------------------------------------------------------------
# 10. PUT /portfolio/note
# ---------------------------------------------------------------------------
@router.put("/portfolio/note")
def portfolio_note_endpoint(req: PortfolioNoteRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != req.user_id:
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
        return {"success": True, "ticker": ticker, "note": req.note.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 11. GET /api/v1/portfolio/advisor-consensus
# ---------------------------------------------------------------------------
_NSE_DIRECTORY = []

@router.get("/api/v1/portfolio/advisor-consensus")
def portfolio_advisor_consensus(user_id: int, days: int = 7):
    """Aggregate AdvisorInsight rows into sector signals and trending tickers."""

    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Build a sector lookup from the in-memory NSE directory
        _sector_map: dict[str, str] = {
            entry["ticker"]: entry.get("sector", "Unknown")
            for entry in _NSE_DIRECTORY
        }
        # Also build company_name lookup from NSE directory
        _company_map: dict[str, str] = {
            entry["ticker"]: entry["company_name"]
            for entry in _NSE_DIRECTORY
        }

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
            except Exception:
                pass

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
                _company_map.get(tk)
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
            sector = _sector_map.get(tk, "Unknown")
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
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "window_days": days,
            "sector_signals": sector_signals,
            "trending_tickers": trending_tickers,
            "total_videos_processed": total_videos_processed,
            "last_harvest_at": last_harvest_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 12. GET /portfolio/export/excel/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/export/excel/{user_id}")
def export_portfolio_excel(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 13. GET /api/v1/portfolio/valuation-history
# ---------------------------------------------------------------------------
@router.get("/api/v1/portfolio/valuation-history")
async def get_valuation_history(user_id: int, days: int = 90, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with get_session() as session:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()

        snapshots = session.query(PortfolioValuationHistory).filter(
            PortfolioValuationHistory.user_id == user_id,
            PortfolioValuationHistory.snapshot_date >= cutoff_date
        ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()

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
                        except Exception:
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

                            existing = session.query(PortfolioValuationHistory).filter_by(
                                user_id=user_id, snapshot_date=date_str
                            ).first()
                            if not existing:
                                session.add(PortfolioValuationHistory(
                                    user_id=user_id,
                                    snapshot_date=date_str,
                                    total_value=round(total_value, 2),
                                    total_invested=round(total_invested, 2),
                                    total_pnl=round(pnl, 2),
                                    pnl_percent=round(pnl_pct, 2),
                                ))
                        session.commit()

                        snapshots = session.query(PortfolioValuationHistory).filter(
                            PortfolioValuationHistory.user_id == user_id,
                            PortfolioValuationHistory.snapshot_date >= cutoff_date
                        ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()
                except Exception as e:
                    print(f"[Valuation Seeding] Error for user {user_id}: {e}")
                    session.rollback()

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


# ---------------------------------------------------------------------------
# 14. GET /portfolio/risk-analysis/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/risk-analysis/{user_id}")
def portfolio_risk_analysis_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
                        except Exception:
                            pass
                    if daily:
                        _return_series[ticker] = daily
            except Exception:
                pass

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

        # ------------------------------------------------------------------
        # Pearson correlation: find highest correlated pair (manual, no sklearn)
        # ------------------------------------------------------------------
        highest_corr_pair = None
        try:
            ticker_list = list(_return_series.keys())
            if len(ticker_list) >= 2:
                max_corr = -999.0
                best_pair = None
                for i in range(len(ticker_list)):
                    for j in range(i + 1, len(ticker_list)):
                        ta = ticker_list[i]
                        tb = ticker_list[j]
                        ra_map = _return_series[ta]
                        rb_map = _return_series[tb]
                        # Align by common dates
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
                    highest_corr_pair = {
                        "ticker_a": best_pair[0],
                        "ticker_b": best_pair[1],
                        "correlation": round(max_corr, 4),
                    }
        except Exception as _corr_err:
            print(f"[RISK] Correlation calc failed: {_corr_err}")

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
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 15. GET /portfolio/red-flags/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/red-flags/{user_id}")
def portfolio_red_flags_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
                    except Exception:
                        pass

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
                    except Exception:
                        pass
                fii_histories[ticker] = fiis

            cutoff = datetime.utcnow() - timedelta(days=30)
            bearish_flips = session.query(SignalEvent).filter(
                SignalEvent.created_at >= cutoff,
                SignalEvent.ticker.in_(held_tickers),
                SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"])
            ).all()
            bearish_flip_map = {f.ticker: (f.from_signal, f.to_signal) for f in bearish_flips}

        try:
            asm_gsm = _get_asm_gsm_lists()
        except Exception:
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
                import os
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
                print(f"[RED-FLAGS] Summary call failed: {e}")

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
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 16. GET /macro-impact/{user_id}
# ---------------------------------------------------------------------------
@router.get("/macro-impact/{user_id}")
def macro_impact_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        now = time.time()
        cached = _macro_impact_cache.get(user_id)
        if cached and now < cached[0]:
            return cached[1]

        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_data = [(h.ticker, h.company_name) for h in holdings]

        if not holdings_data:
            return {"user_id": user_id, "macro_readings": {}, "impacts": [], "generated_at": datetime.utcnow().isoformat()}

        macro: dict = {}
        for sym, key in [("BZ=F", "brent_oil_usd"), ("^INDIAVIX", "india_vix"), ("USDINR=X", "usd_inr")]:
            try:
                info = yf.Ticker(sym).info
                val = info.get("regularMarketPrice") or info.get("currentPrice")
                macro[key] = round(float(val), 2) if val and not math.isnan(float(val)) else None
            except Exception:
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
        import os
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
                print(f"[MACRO-IMPACT] AI call failed: {e}")
                impacts = [{"ticker": t, "impact_statement": "Macro assessment unavailable.", "direction": "neutral"} for t, _ in holdings_data]
        else:
            impacts = [{"ticker": t, "impact_statement": "DeepSeek API key not configured.", "direction": "neutral"} for t, _ in holdings_data]

        result = {
            "user_id": user_id,
            "macro_readings": macro,
            "impacts": impacts,
            "generated_at": datetime.utcnow().isoformat(),
        }
        _macro_impact_cache[user_id] = (now + _MACRO_IMPACT_TTL, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 17. GET /portfolio/timeframe-conflicts/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/timeframe-conflicts/{user_id}")
def portfolio_timeframe_conflicts_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
                except Exception:
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
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 18. POST /trade-journal
# ---------------------------------------------------------------------------
@router.post("/trade-journal")
def trade_journal_add_endpoint(req: TradeJournalAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != req.user_id:
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
            except Exception:
                pass
            try:
                entry.mood = req.mood
            except Exception:
                pass
            session.add(entry)
            session.commit()
            session.refresh(entry)
            entry_id = entry.id
        return {"success": True, "entry_id": entry_id, "ticker": ticker, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 19. GET /trade-journal/{user_id}
# ---------------------------------------------------------------------------
@router.get("/trade-journal/{user_id}")
def trade_journal_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
                except Exception:
                    row["company_name"] = None
                try:
                    row["mood"] = getattr(e, "mood", None)
                except Exception:
                    row["mood"] = None
                try:
                    upd = getattr(e, "updated_at", None)
                    row["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
                except Exception:
                    row["updated_at"] = None
                result.append(row)
        return {"user_id": user_id, "entries": result, "total": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 20. PUT /trade-journal/{entry_id}
# ---------------------------------------------------------------------------
@router.put("/trade-journal/{entry_id}")
def trade_journal_update_endpoint(entry_id: int, req: TradeJournalUpdateRequest, user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
            except Exception:
                pass
            try:
                entry.updated_at = datetime.utcnow()
            except Exception:
                pass
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
            except Exception:
                pass
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 21. DELETE /trade-journal/{entry_id}
# ---------------------------------------------------------------------------
@router.delete("/trade-journal/{entry_id}")
def trade_journal_delete_endpoint(entry_id: int, user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 22. GET /trade-journal/{user_id}/stats
# ---------------------------------------------------------------------------
@router.get("/trade-journal/{user_id}/stats")
def trade_journal_stats_endpoint(user_id: int):
    """Compute analytics over all journal entries for a user."""
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            entries = session.query(TradeJournal).filter_by(user_id=user_id).all()
            entries_data = []
            for e in entries:
                entries_data.append({
                    "ticker": e.ticker,
                    "action": e.action,
                    "reason_text": e.reason_text or "",
                    "outcome_text": (e.outcome_text or "").lower(),
                })

        total_entries = len(entries_data)

        # most_journalled_ticker
        ticker_counts: dict[str, int] = {}
        for e in entries_data:
            ticker_counts[e["ticker"]] = ticker_counts.get(e["ticker"], 0) + 1
        most_journalled_ticker = max(ticker_counts, key=lambda k: ticker_counts[k]) if ticker_counts else None

        # win_loss_ratio
        wins = sum(1 for e in entries_data if "profit" in e["outcome_text"])
        losses = sum(1 for e in entries_data if "loss" in e["outcome_text"])
        ratio = round(wins / losses, 2) if losses > 0 else None
        win_loss_ratio = {"wins": wins, "losses": losses, "ratio": ratio}

        # top_keywords from reason_text
        STOPWORDS = {"the", "a", "an", "is", "in", "of", "and", "to", "i", "my", "this", "for", "it", "at"}
        word_freq: dict[str, int] = {}
        for e in entries_data:
            for w in e["reason_text"].lower().split():
                cleaned = "".join(c for c in w if c.isalpha())
                if cleaned and cleaned not in STOPWORDS and len(cleaned) > 2:
                    word_freq[cleaned] = word_freq.get(cleaned, 0) + 1
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = [{"word": w, "count": c} for w, c in top_keywords]

        # action_breakdown
        action_breakdown = {"BUY": 0, "SELL": 0, "HOLD": 0, "WATCH": 0}
        for e in entries_data:
            act = e["action"].upper()
            if act in action_breakdown:
                action_breakdown[act] += 1

        # Trade journal pattern detection → DeepSeek V4 Flash (Tier 1 bulk task)
        patterns = []
        try:
            all_reasons = " | ".join(e["reason_text"] for e in entries_data if e["reason_text"])
            import os
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
            print(f"[TJ-STATS] Pattern AI call failed: {_pe}")
            patterns = []

        return {
            "user_id": user_id,
            "total_entries": total_entries,
            "most_journalled_ticker": most_journalled_ticker,
            "win_loss_ratio": win_loss_ratio,
            "top_keywords": top_keywords,
            "action_breakdown": action_breakdown,
            "patterns": patterns,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 23. GET /portfolio/export/pdf/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/export/pdf/{user_id}")
def export_portfolio_pdf(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    """Generate a one-page portfolio review PDF (or plain text if fpdf2 not installed)."""
    try:
        import io

        # Step 1: Fetch holdings with P&L (same logic as /portfolio/{user_id})
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_snap = [(h.ticker, h.company_name, h.shares, h.buy_price) for h in holdings]

            # Step 2: Get latest signal per ticker
            ticker_signals: dict[str, dict] = {}
            for ticker, _, _, _ in holdings_snap:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if row:
                    ticker_signals[ticker] = {"signal": row.signal, "conf": row.confidence_pct}

            # Step 3: Red flags (inline — no HTTP call)
            red_flag_list = []
            cutoff30 = datetime.utcnow() - timedelta(days=30)
            bearish_flips_pdf = session.query(SignalEvent).filter(
                SignalEvent.created_at >= cutoff30,
                SignalEvent.ticker.in_([t for t, _, _, _ in holdings_snap]),
                SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"]),
            ).all()
            bf_map = {f.ticker for f in bearish_flips_pdf}
            for ticker, _, _, _ in holdings_snap:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if row and row.full_json:
                    try:
                        d = json.loads(row.full_json)
                        pledged = (d.get("fundamentals_snapshot") or {}).get("promoter_pledged_pct") or row.promoter_pledged_pct
                        if pledged and pledged > 30:
                            red_flag_list.append(f"{ticker}: High pledging {pledged:.1f}%")
                    except Exception:
                        pass
                if ticker in bf_map:
                    red_flag_list.append(f"{ticker}: Bearish signal flip in last 30 days")

        # Build P&L summary
        holdings_summary = []
        for ticker, company, shares, buy_price in holdings_snap:
            ns = _to_ns(ticker)
            current_price, _ = _yf_price(ns)
            invested = shares * buy_price
            current_val = shares * current_price if current_price else 0.0
            pnl_pct = round((current_val - invested) / invested * 100, 1) if invested > 0 and current_val > 0 else 0.0
            sig_info = ticker_signals.get(ticker, {})
            holdings_summary.append({
                "ticker": ticker,
                "company": company,
                "signal": sig_info.get("signal", "N/A"),
                "pnl_pct": pnl_pct,
                "current_price": round(current_price, 2) if current_price else 0.0,
            })

        holdings_json = json.dumps(holdings_summary, indent=2)
        flags_text = "\n".join(red_flag_list) if red_flag_list else "None detected"

        # Step 4: One Sonnet call for review markdown
        markdown_text = "# Portfolio Review\n\nUnable to generate AI review.\n"
        try:
            import os
            import anthropic
            SONNET_MODEL = "claude-sonnet-4-6"
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and api_key != "placeholder":
                client = anthropic.Anthropic(api_key=api_key)
                for attempt in range(3):
                    try:
                        resp = client.messages.create(
                            model=SONNET_MODEL,
                            max_tokens=1200,
                            system="You are a private wealth advisor. Write a one-page portfolio review for a long-term Indian equity investor. Use bullet points. Format as clean markdown.",
                            messages=[{
                                "role": "user",
                                "content": (
                                    f"Holdings: {holdings_json}\n"
                                    f"Red flags: {flags_text}\n\n"
                                    "Write: Executive Summary (3 bullets), Holdings Review (one line per stock with signal and P&L%), Risk Watch, Overall Recommendation."
                                )
                            }],
                        )
                        break
                    except Exception as _pe:
                        if attempt == 2:
                            raise
                        time.sleep(1.0 * (2 ** attempt))
                _log_token_usage("pdf_export", resp.usage)
                markdown_text = resp.content[0].text.strip()
        except Exception as _ae:
            print(f"[PDF-EXPORT] AI call failed: {_ae}")

        # Step 5/6: Return PDF or plain text
        if FPDF2_AVAILABLE:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)

                for line in markdown_text.split("\n"):
                    if line.startswith("# "):
                        pdf.set_font("Arial", style="B", size=16)
                        pdf.cell(0, 10, line[2:], ln=True)
                    elif line.startswith("## "):
                        pdf.set_font("Arial", style="B", size=13)
                        pdf.cell(0, 8, line[3:], ln=True)
                    elif line.startswith("### "):
                        pdf.set_font("Arial", style="B", size=11)
                        pdf.cell(0, 7, line[4:], ln=True)
                    else:
                        # Strip bold markers
                        clean = line.replace("**", "").replace("__", "")
                        pdf.set_font("Arial", size=10)
                        pdf.multi_cell(0, 6, clean)

                pdf_bytes = pdf.output(dest="S")
                if isinstance(pdf_bytes, str):
                    pdf_bytes = pdf_bytes.encode("latin-1")

                today_str = date.today().strftime("%Y%m%d")
                return StreamingResponse(
                    io.BytesIO(pdf_bytes),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=portfolio_review_{user_id}_{today_str}.pdf"},
                )
            except Exception as _pdfe:
                print(f"[PDF-EXPORT] fpdf2 render failed: {_pdfe}")
                # Fall through to plain text

        # Plain text fallback
        today_str = date.today().strftime("%Y%m%d")
        return StreamingResponse(
            io.BytesIO(markdown_text.encode("utf-8")),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=portfolio_review_{user_id}_{today_str}.txt"},
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF-EXPORT] Top-level error: {e}")
        fallback_text = f"Portfolio review unavailable. Error: {str(e)}"
        return StreamingResponse(
            io.BytesIO(fallback_text.encode("utf-8")),
            media_type="text/plain",
        )


# ---------------------------------------------------------------------------
# 24. GET /api/v1/market/net-worth-ledger/{user_id}
# ---------------------------------------------------------------------------
def format_indian_currency(value: float) -> str:
    """Format a number in Indian Lakhs/Crores style."""
    if value >= 1e7:
        return f"₹{value / 1e7:.2f} Cr"
    elif value >= 1e5:
        return f"₹{value / 1e5:.2f} L"
    else:
        return f"₹{value:,.2f}"


@router.get("/api/v1/market/net-worth-ledger/{user_id}", response_model=NetWorthSnapshotResponse)
async def net_worth_ledger_endpoint(
    user_id: int,
    authorization: str = Header(None),
):
    """
    Return the latest net-worth snapshot for a user.
    All monetary values use Indian Lakhs/Crores formatting.
    Requires valid JWT. Returns 404 if no snapshot exists yet.
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
