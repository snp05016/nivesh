"""
Analysis endpoints router.
Handles quick-info, analyze, batch analysis, technical signals, home feed, screener, etc.
"""
import os
import json
import time as _time
import asyncio
import multiprocessing
import math
import uuid
from datetime import date, datetime, timedelta

import yfinance as yf
import anthropic
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse as _JSONResponse
from datetime import timezone as _timezone

from helpers import (
    get_session, EXCHANGE_SUFFIX, NSE_TICKERS, NSE_TICKER_OVERRIDES,
    _resolve_ticker, _to_ns, _yf_price, _yf_fetch_info,
    _quick_info_cache, _quick_info_lock, _QUICK_INFO_TTL,
    _get_analyze_semaphore, _acquire_analysis_slot, _release_analysis_slot,
    _ANALYZE_MAX_CONCURRENT, _RUNNING_ANALYSES_STALENESS_SEC,
    _dash_start_job, _dash_end_job,
    _log_token_usage, TOKEN_LOG_PATH,
    AnalyzeRequest, BatchAnalyzeRequest,
    AnalysisHistory, Portfolio, SignalEvent, PriceTarget,
    NewsArticle, YouTubeVideo, PKScreenerSignal,
    get_analysis_for_date, get_all_ticker_history, save_analysis,
    verify_access_token, require_admin,
    _check_rate_limit,
)

router = APIRouter(tags=["Analysis"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from services.llm_utils import deepseek_chat, SONNET_MODEL, DEEPSEEK_MODEL
_deepseek_chat = deepseek_chat  # backward-compat alias

SECTOR_PE_MAP = {
    "Technology": 35, "Financial Services": 18, "Energy": 12,
    "Healthcare": 28, "Consumer Cyclical": 25, "Industrials": 22,
    "Basic Materials": 15, "Consumer Defensive": 30, "Utilities": 20,
    "Real Estate": 20, "Communication Services": 22,
}

_BULLISH_SIGNALS = {"BULLISH", "CAUTIOUSLY BULLISH"}
_BEARISH_SIGNALS = {"BEARISH", "CAUTIOUSLY BEARISH"}

# Circuit breaker for yfinance-dependent endpoints
_yf_circuit_failures = 0
_yf_circuit_open_until = 0.0
_YF_CIRCUIT_THRESHOLD = 3
_YF_CIRCUIT_TIMEOUT = 300  # 5 minutes

# ---------------------------------------------------------------------------
# DeepSeek helpers — now imported from services.llm_utils (single source)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Signal normalization
# ---------------------------------------------------------------------------
_SIGNAL_MAP = {
    "BUY": "BULLISH",
    "STRONG BUY": "BULLISH",
    "STRONG_BUY": "BULLISH",
    "SELL": "BEARISH",
    "STRONG SELL": "BEARISH",
    "STRONG_SELL": "BEARISH",
    "AVOID": "BEARISH",
    "CAUTIOUS": "CAUTIOUSLY BEARISH",
}

def _normalize_signal(result: dict) -> dict:
    if "signal" in result:
        normalized = result["signal"].strip().upper()
        result["signal"] = _SIGNAL_MAP.get(normalized, normalized)
    return result

# ---------------------------------------------------------------------------
# yfinance circuit breaker
# ---------------------------------------------------------------------------
def _yf_circuit_is_open() -> bool:
    global _yf_circuit_failures, _yf_circuit_open_until
    if _yf_circuit_failures >= _YF_CIRCUIT_THRESHOLD:
        if time.time() < _yf_circuit_open_until:
            return True
        _yf_circuit_failures = 0
    return False

def _yf_circuit_record_failure():
    global _yf_circuit_failures, _yf_circuit_open_until
    _yf_circuit_failures += 1
    if _yf_circuit_failures >= _YF_CIRCUIT_THRESHOLD:
        _yf_circuit_open_until = time.time() + _YF_CIRCUIT_TIMEOUT

def _yf_circuit_record_success():
    global _yf_circuit_failures
    _yf_circuit_failures = 0

# ── Item 47: Batch Analysis ───────────────────────────────────────────
@router.post("/batch")
def batch_analysis(req: BatchAnalyzeRequest):
    if len(req.tickers) > 20:
        raise HTTPException(status_code=400, detail="Max 20 tickers allowed per batch")
    
    results = []
    with get_session() as db:
        for ticker in req.tickers:
            # Query the latest AnalysisHistory for this ticker
            db_analysis = (db.query(AnalysisHistory)
                           .filter(AnalysisHistory.ticker == ticker, AnalysisHistory.user_id == req.user_id)
                           .order_by(AnalysisHistory.analysis_date.desc())
                           .first())
            if db_analysis and db_analysis.full_json:
                try:
                    data = json.loads(db_analysis.full_json)
                    results.append({"ticker": ticker, "status": "cached", "data": data})
                except Exception:
                    results.append({"ticker": ticker, "status": "not_cached"})
            else:
                results.append({"ticker": ticker, "status": "not_cached"})
                
    return {"results": results}

# ---------------------------------------------------------------------------
# NSE session + ASM/GSM helpers
# ---------------------------------------------------------------------------
_asm_gsm_cache = {"data": {}, "ts": 0}
_ASM_GSM_CACHE_TTL = 21600  # 6 hours

def _nse_session():
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
    global _asm_gsm_cache
    now = time.time()
    if _asm_gsm_cache["ts"] > 0 and (now - _asm_gsm_cache["ts"]) < _ASM_GSM_CACHE_TTL:
        return _asm_gsm_cache["data"]

    print("[NSE] Refreshing ASM/GSM lists...")
    data = {"ASM": set(), "GSM": set()}
    try:
        session = _nse_session()
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=longTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())
        
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=shortTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())

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

# ---------------------------------------------------------------------------
# Analysis worker (runs in subprocess)
# ---------------------------------------------------------------------------
def _run_analysis_worker(queue, ticker, exchange, user_id, deep_scan=False, scan_type="standard"):
    from dotenv import load_dotenv
    from pathlib import Path as _Path
    import os
    import traceback
    import sys
    env_path = _Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    try:
        sys.path.insert(0, str(_Path(__file__).parent.parent))
        # Put the local tradingagents-core fork BEFORE the venv so it shadows
        # the PyPI tradingagents package which lacks default_config.
        _ta_core = _Path(__file__).parent.parent / "tradingagents-core"
        if _ta_core.exists():
            sys.path.insert(0, str(_ta_core))
        from services.orchestrator import analyze
        result = analyze(ticker, exchange, user_id, deep_scan=deep_scan, scan_type=scan_type)
        queue.put({"status": "ok", "result": result})
    except ImportError as e:
        tb = traceback.format_exc()
        print(f"[WORKER] Import failed: {e}\n{tb}")
        queue.put({
            "status": "error",
            "error": f"Failed to import analysis engine: {e}",
            "phase": "worker_import",
            "diagnostic": f"Import traceback:\n{tb[-2000:]}",
        })
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[WORKER] Analysis failed: {e}\n{tb}")
        queue.put({
            "status": "error",
            "error": str(e),
            "phase": "analyze_execution",
            "diagnostic": f"Exception type: {type(e).__name__}\nTraceback:\n{tb[-3000:]}",
        })

# ---------------------------------------------------------------------------
# GET /quick-info
# ---------------------------------------------------------------------------
@router.get("/quick-info")
def quick_info_endpoint(ticker: str, exchange: str = "NSE"):
    try:
        exchange = exchange.upper()
        if exchange not in EXCHANGE_SUFFIX:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange}")

        cache_key = f"{ticker.upper()}_{exchange.upper()}"
        from services.disk_cache import get as _dcache_get, set as _dcache_set
        _disk_hit = _dcache_get("quick-info", cache_key)
        if _disk_hit:
            print(f"[QUICK-INFO CACHE HIT] {cache_key}")
            return _disk_hit

        full_ticker = _resolve_ticker(ticker, exchange)
        
        import time
        import random
        info = {}
        t = None
        for attempt in range(3):
            try:
                t = yf.Ticker(full_ticker)
                info = t.info
                if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                    break
            except Exception as e:
                print(f"[YF] Quick info attempt {attempt+1} failed for {full_ticker}: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
        
        if not info:
            t = yf.Ticker(full_ticker)
            info = t.info or {}

        hist = t.history(period="1y")
        sparkline = [round(float(p), 2) for p in hist["Close"].tolist()[-30:] if not math.isnan(float(p))] if not hist.empty else []

        price_history_90d = []
        if not hist.empty:
            for dt, row in hist.iterrows():
                close_val = float(row["Close"])
                if math.isnan(close_val):
                    continue
                price_history_90d.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "close": round(close_val, 2),
                    "volume": int(row["Volume"]) if not math.isnan(float(row["Volume"])) else 0,
                })

        raw_news = t.news if hasattr(t, "news") and t.news else []
        recent_news = []
        for item in raw_news[:8]:
            content = item.get("content", {})
            pub = content.get("pubDate") or item.get("providerPublishTime", 0)
            if isinstance(pub, str):
                try:
                    from datetime import datetime, timezone
                    pub = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pub = 0
            
            image_url = None
            thumbnail = content.get("thumbnail", {})
            if thumbnail:
                image_url = thumbnail.get("originalUrl")
                if not image_url and thumbnail.get("resolutions"):
                    res = sorted(thumbnail["resolutions"], key=lambda x: x.get("width", 0), reverse=True)
                    if res:
                        image_url = res[0].get("url")

            recent_news.append({
                "title": content.get("title") or item.get("title", ""),
                "publisher": content.get("provider", {}).get("displayName") or item.get("publisher", ""),
                "link": content.get("canonicalUrl", {}).get("url") or item.get("link", ""),
                "publish_time": int(pub) if pub else 0,
                "summary": content.get("summary") or "",
                "image_url": image_url
            })

        current = info.get("currentPrice") or info.get("regularMarketPrice") or (sparkline[-1] if sparkline else None)
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        day_change_abs = round(current - prev_close, 2) if current and prev_close else None
        day_change_pct = round((day_change_abs / prev_close) * 100, 2) if day_change_abs and prev_close else None
        market_cap = info.get("marketCap")

        pe_current = info.get("trailingPE") or info.get("forwardPE")
        pe_vs_avg = None
        try:
            hist_3y = t.history(period="3y")
            earnings = t.earnings_history
            if earnings is not None and not earnings.empty and pe_current:
                pe_history = t.info.get("fiveYearAvgDividendYield")
                fin = t.quarterly_financials
                if fin is not None and not fin.empty and "Basic EPS" in fin.index:
                    eps_ttm = fin.loc["Basic EPS"].dropna().head(4).sum()
                    if eps_ttm and eps_ttm > 0 and pe_current:
                        hist_prices = t.history(period="3y")["Close"].dropna()
                        if not hist_prices.empty:
                            avg_price_3y = float(hist_prices.mean())
                            avg_pe_3y = round(avg_price_3y / float(eps_ttm), 1)
                            pct_diff = round((pe_current - avg_pe_3y) / avg_pe_3y * 100, 1)
                            pe_vs_avg = {"current_pe": round(pe_current, 1), "avg_pe_3y": avg_pe_3y, "pct_vs_avg": pct_diff}
        except Exception:
            pass

        dividends = []
        try:
            div = t.dividends
            if div is not None and not div.empty:
                div_df = div.resample("Y").sum()
                for dt, amt in div_df.tail(5).items():
                    if not math.isnan(float(amt)) and float(amt) > 0:
                        dividends.append({"year": dt.year, "amount": round(float(amt), 2)})
        except Exception:
            pass

        corporate_actions = []
        try:
            actions = t.actions
            if actions is not None and not actions.empty:
                for dt, row in actions.tail(10).iterrows():
                    splits = float(row.get("Stock Splits", 0))
                    divs = float(row.get("Dividends", 0))
                    if splits > 0:
                        corporate_actions.append({"date": dt.strftime("%d-%b-%Y"), "type": "split", "detail": f"Stock split {splits}:1"})
                    if divs > 0:
                        corporate_actions.append({"date": dt.strftime("%d-%b-%Y"), "type": "dividend", "detail": f"Dividend ₹{round(divs,2)}"})
        except Exception:
            pass

        # Fetch latest AI governance analysis for this ticker
        governance_score = None
        governance_red_flags = []
        try:
            from database import AnalysisHistory, get_session as _get_db_session
            import json as _json
            with _get_db_session() as _sess:
                _last = _sess.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker.upper()
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if _last:
                    try:
                        _raw = _last.full_json
                        _fj = _json.loads(_raw) if isinstance(_raw, str) else _raw
                        governance_score = _fj.get("governance_score")
                        governance_red_flags = _fj.get("governance_red_flags") or []
                    except Exception:
                        pass
        except Exception:
            pass

        asm_gsm_status = "CLEAN"
        try:
            lists = _get_asm_gsm_lists()
            t_base = ticker.upper().split(".")[0]
            if t_base in lists.get("GSM", set()): asm_gsm_status = "GSM"
            elif t_base in lists.get("ASM", set()): asm_gsm_status = "ASM"
            elif not lists.get("ASM") and not lists.get("GSM"): asm_gsm_status = "UNKNOWN"
        except:
            asm_gsm_status = "UNKNOWN"

        result = {
            "ticker": ticker.upper().split(".")[0],
            "asm_gsm_status": asm_gsm_status,
            "company_name": info.get("longName") or info.get("shortName") or ticker.upper(),
            "exchange": exchange,
            "current_price": current,
            "day_change_abs": day_change_abs,
            "day_change_pct": day_change_pct,
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "market_cap_crores": round(market_cap / 1e7, 0) if market_cap else None,
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "debt_to_equity": round(info.get("debtToEquity") / 100, 2) if info.get("debtToEquity") else None,
            "promoter_holding_pct": round(info.get("heldPercentInsiders", 0) * 100, 1) or None,
            "promoter_pledged_pct": round(float(info.get("heldPercentInsiders", 0)) * float(info.get("insiderPercentHeld", 0)) * 0.01, 1) if info.get("heldPercentInsiders") and info.get("insiderPercentHeld") else None,
            "fii_holding_pct": round(info.get("heldPercentInstitutions", 0) * 100, 1) or None,
            "dii_holding_pct": round(info.get("heldPercentInstitutions", 0) * 100 * 0.35, 1) or None,  # DII ~35% of institutional
            "ebitda_margin_pct": round(info.get("ebitdaMargins", 0) * 100, 1) if info.get("ebitdaMargins") else None,
            "roe_pct": round(info.get("returnOnEquity", 0) * 100, 1) if info.get("returnOnEquity") else None,
            "roce_pct": round(info.get("returnOnCapitalEmployed", 0) * 100, 1) if info.get("returnOnCapitalEmployed") else None,
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "avg_volume": info.get("averageVolume"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "description": info.get("longBusinessSummary") or "Company profile not available.",
            "officers": [officer.get("name") for officer in info.get("companyOfficers", [])[:3]] if info.get("companyOfficers") else [],
            "website": info.get("website"),
            "sparkline_30d": sparkline,
            "price_history_90d": price_history_90d,
            "recent_news": recent_news,
            "pe_vs_avg": pe_vs_avg,
            "dividends": dividends,
            "corporate_actions": corporate_actions,
            "governance_score": governance_score,
            "governance_red_flags": governance_red_flags,
        }
        _dcache_set("quick-info", cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

def _build_analysis_error(
    error_code: str,
    error_title: str,
    error_detail: str,
    error_type: str,
    phase_failed: str,
    ticker: str,
    suggested_action: str,
    diagnostic_info: str = "",
    http_status: int = 500,
) -> _JSONResponse:
    body = {
        "error": True,
        "error_code": error_code,
        "error_title": error_title,
        "error_detail": error_detail,
        "error_type": error_type,
        "phase_failed": phase_failed,
        "ticker": ticker,
        "timestamp": datetime.now(_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suggested_action": suggested_action,
        "diagnostic_info": diagnostic_info,
        "http_status": http_status,
    }
    return _JSONResponse(status_code=http_status, content=body)


def _save_analysis_result(user_id: int | None, ticker: str, result: dict) -> None:
    """Persist completed analysis to AnalysisHistory for dashboard visibility."""
    try:
        from database import save_analysis
        with get_session() as session:
            save_analysis(session, user_id, ticker.upper(), result)
    except Exception as e:
        print(f"[dash] Failed to persist analysis for {ticker}: {e}")


@router.post("/analyze", status_code=202)
async def analyze_endpoint(req: AnalyzeRequest):
    """Start a background analysis job and return immediately (202).

    v2 engine: the run is fully decoupled from this HTTP connection — the app polls
    GET /analyze/job/{job_id}. Backgrounding / navigating / closing the app no longer
    kills the run. One running job per user (guarded by the DB job state).
    """
    import database
    from services.job_manager import spawn_job

    ticker = req.ticker.upper()

    if req.user_id is not None:
        active = database.get_active_job_for_user(req.user_id)
        if active:
            return _JSONResponse(status_code=409, content={
                "error_code": "ALREADY_RUNNING",
                "error_title": "Analysis Already Running",
                "error_detail": (
                    f"You already have an analysis in progress "
                    f"({active['ticker']}, status {active['status']}). "
                    f"Cancel it or wait for it to finish before starting another."
                ),
                "error_type": "rate_limit",
                "job_id": active["job_id"],
                "ticker": active["ticker"],
                "suggested_action": "ATTACH_OR_CANCEL",
            })

    job = database.create_job(req.user_id, ticker, req.exchange, req.scan_type)
    try:
        spawn_job(job["job_id"], ticker, req.exchange,
                  req.user_id, req.deep_scan, req.scan_type)
    except Exception as e:
        database.update_job(job["job_id"], status="FAILED",
                            error=f"Failed to spawn worker: {e}")
        return _JSONResponse(status_code=500, content={
            "error_code": "SPAWN_FAILED",
            "error_title": "Could Not Start Analysis",
            "error_detail": str(e),
            "job_id": job["job_id"],
        })

    return {"job_id": job["job_id"], "status": "QUEUED",
            "ticker": ticker, "scan_type": req.scan_type}


@router.get("/analyze/job/{job_id}")
async def get_job_status(job_id: str):
    """Poll a job: status, stage, progress_pct, checkpoints, and result when done."""
    import database
    job = database.get_job(job_id)
    if not job:
        return _JSONResponse(status_code=404, content={"error": "job not found"})
    return job


@router.get("/analyze/active")
async def get_active_job(user_id: int):
    """The user's current running/queued job — drives the app's global running indicator."""
    import database
    job = database.get_active_job_for_user(user_id)
    return job or {"status": "NONE"}


@router.post("/analyze/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    """Cancel a running job (terminates the worker subprocess to stop credit spend)."""
    import database
    from services.job_manager import cancel_job
    if not database.get_job(job_id):
        return _JSONResponse(status_code=404, content={"error": "job not found"})
    cancel_job(job_id)
    return {"job_id": job_id, "status": "CANCELLED"}


# ---------------------------------------------------------------------------
# GET /analyze/slots — admin endpoint to inspect/clear stuck analysis slots
# ---------------------------------------------------------------------------
@router.get("/analyze/slots")
async def inspect_analysis_slots(authorization: str = Header(None)):
    require_admin(authorization)
    from helpers import _get_stuck_analyses, _force_clear_analysis_slot
    stuck = _get_stuck_analyses()
    return {
        "total": len(stuck),
        "slots": stuck,
        "staleness_timeout_sec": _RUNNING_ANALYSES_STALENESS_SEC,
    }


# ---------------------------------------------------------------------------
# DELETE /analyze/slots — admin endpoint to force-clear stuck slots
# ---------------------------------------------------------------------------
@router.delete("/analyze/slots")
async def clear_analysis_slots(
    user_id: int | None = None,
    authorization: str = Header(None),
):
    require_admin(authorization)
    from helpers import _force_clear_analysis_slot, _get_stuck_analyses

    if user_id is not None:
        cleared = _force_clear_analysis_slot(user_id)
        return {
            "cleared": cleared,
            "user_id": user_id,
            "message": "Slot force-cleared." if cleared else "No slot found for this user.",
        }

    # Clear all
    stuck = _get_stuck_analyses()
    cleared_count = 0
    for slot in stuck:
        if _force_clear_analysis_slot(slot["user_id"]):
            cleared_count += 1
    return {
        "cleared": cleared_count,
        "total_stuck": len(stuck),
        "message": f"Cleared {cleared_count} of {len(stuck)} stuck analysis slots.",
    }


# ---------------------------------------------------------------------------
# POST /analyze/batch
# ---------------------------------------------------------------------------
@router.post("/analyze/batch")
async def batch_analyze_endpoint(req: BatchAnalyzeRequest):
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

        exchange = req.exchange.upper()
        analysis_date = date.today().strftime("%Y-%m-%d")
        requests_list = []

        for ticker in req.tickers:
            full_ticker = _resolve_ticker(ticker, exchange)
            from prompts import INDIAN_MARKET_SYSTEM_PROMPT
            user_message = f"Analyze {full_ticker} on {exchange} for {analysis_date}. Return analysis JSON per system prompt."
            requests_list.append({
                "custom_id": ticker.upper(),
                "params": {
                    "model": SONNET_MODEL,
                    "max_tokens": 2000,
                    "system": [{"type": "text", "text": INDIAN_MARKET_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                    "messages": [{"role": "user", "content": user_message}],
                }
            })

        client = anthropic.Anthropic(api_key=api_key)
        
        import time
        for attempt in range(3):
            try:
                batch = client.messages.batches.create(requests=requests_list)
                break
            except Exception as e:
                print(f"[Anthropic] Batch create attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))

        return {
            "batch_id": batch.id,
            "status": batch.processing_status,
            "request_counts": batch.request_counts.model_dump() if hasattr(batch.request_counts, 'model_dump') else {},
            "tickers": req.tickers,
            "note": "Poll GET /analyze/batch/{batch_id} for results"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /analyze/batch/{batch_id}
# ---------------------------------------------------------------------------
@router.get("/analyze/batch/{batch_id}")
async def batch_analyze_status(batch_id: str):
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        
        import time
        for attempt in range(3):
            try:
                batch = client.messages.batches.retrieve(batch_id)
                break
            except Exception as e:
                print(f"[Anthropic] Batch retrieve attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))

        if batch.processing_status == "ended":
            results = []
            for result in client.messages.batches.results(batch_id):
                if result.result.type == "succeeded":
                    try:
                        raw_json = result.result.message.content[0].text.strip()
                        analysis = json.loads(raw_json)
                        analysis = _normalize_signal(analysis)
                        with get_session() as session:
                            save_analysis(session, None, result.custom_id, analysis)
                        results.append({"ticker": result.custom_id, "status": "saved"})
                    except Exception as e:
                        results.append({"ticker": result.custom_id, "status": "error", "detail": str(e)})
            return {"status": "complete", "results": results}

        return {"status": batch.processing_status, "batch_id": batch_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /api/v1/technical-signals
# ---------------------------------------------------------------------------
@router.get("/api/v1/technical-signals")
async def get_technical_signals(ticker: str):
    with get_session() as session:
        signal = session.query(PKScreenerSignal).filter(
            PKScreenerSignal.ticker == ticker.upper()
        ).order_by(PKScreenerSignal.signal_date.desc()).first()

        if not signal:
            return {"ticker": ticker.upper(), "signal": None, "message": "No scan data yet"}

        return {
            "ticker": signal.ticker,
            "signal_date": signal.signal_date,
            "technical_score": signal.technical_score,
            "breakout": signal.breakout,
            "consolidating": signal.consolidating,
            "rsi": signal.rsi,
            "macd_signal": signal.macd_signal,
            "ma_signal": signal.ma_signal,
            "volume_signal": signal.volume_signal,
            "pattern": signal.pattern,
        }


# ---------------------------------------------------------------------------
# GET /api/v1/home-feed
# ---------------------------------------------------------------------------
@router.get("/api/v1/home-feed")
async def get_home_feed(user_id: int, ticker: str = None):
    with get_session() as session:
        news_query = session.query(NewsArticle).order_by(NewsArticle.published_at.desc())
        if ticker:
            news_query = news_query.filter(NewsArticle.ticker == ticker.upper())
        else:
            cutoff = datetime.utcnow() - timedelta(hours=48)
            news_query = news_query.filter(NewsArticle.published_at >= cutoff)

        articles = news_query.limit(15).all()

        if not articles:
            try:
                _check_tickers = [ticker.upper()] if ticker else ["^NSEI", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
                _fb_arts = []
                for _t in _check_tickers[:4]:
                    try:
                        _news = yf.Ticker(_t).news or []
                        for _n in _news[:4]:
                            _pub_ts = _n.get("providerPublishTime", 0)
                            _pub_iso = datetime.utcfromtimestamp(_pub_ts).isoformat() + "Z" if _pub_ts else datetime.utcnow().isoformat() + "Z"
                            _fb_arts.append({
                                "id": abs(hash(_n.get("link", "") + _t)) % 1_000_000,
                                "source": _n.get("publisher", "Yahoo Finance"),
                                "ticker": _t.replace(".NS", "").replace(".BO", "").replace("^", ""),
                                "headline": _n.get("title", ""),
                                "summary": _n.get("summary", ""),
                                "image_url": None,
                                "article_url": _n.get("link", ""),
                                "published_at": _pub_iso,
                                "is_red_flag": False,
                                "sentiment": None,
                                "sentiment_score": None,
                                "sentiment_label": None,
                            })
                    except Exception:
                        continue
                if _fb_arts:
                    return {
                        "news": _fb_arts[:12],
                        "red_flag_alerts": [],
                        "youtube_videos": [],
                        "generated_at": datetime.utcnow().isoformat(),
                    }
            except Exception as _fe:
                print(f"[HOME-FEED] yfinance fallback error: {_fe}")

        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings"
        ).all()
        holding_tickers = [h.ticker for h in holdings]
        red_flags = session.query(NewsArticle).filter(
            NewsArticle.is_red_flag == True,
            NewsArticle.ticker.in_(holding_tickers),
            NewsArticle.published_at >= datetime.utcnow() - timedelta(days=7)
        ).order_by(NewsArticle.published_at.desc()).limit(5).all()

        holding_tickers_set = {h.ticker.upper() for h in holdings}
        cutoff_7d = datetime.utcnow() - timedelta(days=7)
        # Quality threshold cascade: prefer SEBI registry channels, then 50k+ views,
        # then 10k+ views so the section never silently disappears.
        def _quality_base(q, min_views: int):
            return q.filter(
                (YouTubeVideo.source != "ytdlp_search") | (YouTubeVideo.view_count >= min_views)
            )

        def _fetch_portfolio_videos(min_views: int):
            vids = _quality_base(
                session.query(YouTubeVideo).filter(
                    YouTubeVideo.matched_ticker.in_(holding_tickers_set),
                    YouTubeVideo.published_at >= cutoff_7d,
                ), min_views
            ).order_by(YouTubeVideo.view_count.desc()).limit(15).all()
            # Widen to 30 days if < 5 found
            if len(vids) < 5:
                vids = _quality_base(
                    session.query(YouTubeVideo).filter(
                        YouTubeVideo.matched_ticker.in_(holding_tickers_set),
                    ), min_views
                ).order_by(YouTubeVideo.view_count.desc()).limit(15).all()
            return vids

        portfolio_videos = _fetch_portfolio_videos(50_000)
        if len(portfolio_videos) < 3:
            portfolio_videos = _fetch_portfolio_videos(10_000)

        portfolio_vid_ids = {v.video_id for v in portfolio_videos}
        remaining = 15 - len(portfolio_videos)
        general_videos = []
        if remaining > 0:
            general_videos = _quality_base(
                session.query(YouTubeVideo).filter(
                    ~YouTubeVideo.video_id.in_(portfolio_vid_ids),
                    YouTubeVideo.published_at >= cutoff_7d,
                ), 10_000
            ).order_by(YouTubeVideo.view_count.desc()).limit(remaining).all()

        all_videos = portfolio_videos + general_videos

        def serialize_article(a) -> dict:
            return {
                "id": a.id,
                "source": a.source,
                "ticker": a.ticker,
                "headline": a.headline,
                "summary": a.summary,
                "image_url": a.image_url,
                "article_url": a.article_url,
                "published_at": a.published_at.isoformat(),
                "is_red_flag": a.is_red_flag,
                "sentiment": a.sentiment,
                "sentiment_score": a.sentiment_score,
                "sentiment_label": a.sentiment_label,
            }

        def serialize_video(v) -> dict:
            return {
                "id": v.id,
                "video_id": v.video_id,
                "channel_name": v.channel_name,
                "title": v.title,
                "thumbnail_url": v.thumbnail_url,
                "video_url": v.video_url,
                "published_at": v.published_at.isoformat(),
                "view_count": v.view_count,
                "duration_seconds": v.duration_seconds,
                "tickers_mentioned": v.tickers_mentioned.split(",") if v.tickers_mentioned else [],
                "matched_ticker": v.matched_ticker,
                "source": v.source,
                "sebi_reg": v.sebi_reg,
            }

        return {
            "news": [serialize_article(a) for a in articles],
            "red_flag_alerts": [serialize_article(a) for a in red_flags],
            "youtube_videos": [serialize_video(v) for v in all_videos],
            "generated_at": datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# GET /screener
# ---------------------------------------------------------------------------
@router.get("/screener")
def screener_endpoint(preset: str):
    if _yf_circuit_is_open():
        raise HTTPException(status_code=503, detail="Market data service temporarily unavailable. Try again in a few minutes.")
    try:
        results = []

        if preset == "ghar_ghar_modi":
            try:
                from services.piotroski import compute_piotroski
                from datetime import timedelta
                cutoff_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
                with get_session() as session:
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.analysis_date >= cutoff_date,
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                    ).order_by(AnalysisHistory.confidence_pct.desc()).limit(30).all()
                    seen: dict[str, tuple] = {}
                    for r in rows:
                        if r.ticker not in seen:
                            seen[r.ticker] = (r.signal, r.confidence_pct)
                candidates = list(seen.items())

                for ticker, (signal, conf) in candidates:
                    try:
                        ns = _to_ns(ticker)
                        info = _yf_fetch_info(ns)
                        pe = info.get("trailingPE") or info.get("forwardPE")
                        sector = info.get("sector") or "Unknown"
                        sector_pe = SECTOR_PE_MAP.get(sector, 25)
                        if pe is None or pe <= 0 or pe >= sector_pe:
                            continue
                        # Piotroski F-Score check
                        f_score = compute_piotroski(ticker)
                        if f_score < 7:
                            continue
                        company = info.get("longName") or info.get("shortName") or ticker
                        results.append({
                            "ticker": ticker,
                            "company_name": company,
                            "signal": signal,
                            "confidence_pct": conf or 0,
                            "reason": f"Piotroski: {f_score}/9, PE: {pe:.1f} (below sector {sector_pe})",
                            "f_score": f_score,
                            "pe_ratio": round(pe, 1),
                        })
                    except Exception:
                        continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER ghar_ghar_modi] {_se}")

        elif preset == "earnings_pioneers":
            try:
                from services.pkscreener_runner import PKScreenerRunner
                from datetime import timedelta
                with get_session() as session:
                    pk_signals = session.query(PKScreenerSignal).filter(
                        PKScreenerSignal.signal_date >= (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%d"),
                    ).all()
                    # Map ticker -> latest screener signal
                    pk_map: dict[str, PKScreenerSignal] = {}
                    for s in pk_signals:
                        if s.ticker not in pk_map:
                            pk_map[s.ticker] = s

                for ticker, pk in pk_map.items():
                    try:
                        is_breakout = pk.breakout or False
                        is_golden = pk.ma_signal and "golden" in pk.ma_signal.lower()
                        if not (is_breakout or is_golden):
                            continue
                        # Check YoY net profit growth from analysis history
                        with get_session() as session:
                            latest = session.query(AnalysisHistory).filter(
                                AnalysisHistory.ticker == ticker
                            ).order_by(AnalysisHistory.created_at.desc()).first()
                        if not latest:
                            continue
                        data = json.loads(latest.full_json or "{}")
                        fs = data.get("fundamentals_snapshot", {})
                        profit_growth = fs.get("net_profit_growth_pct") or fs.get("profit_growth_3y") or 0
                        if profit_growth <= 20:
                            continue
                        company = data.get("company_name") or ticker
                        results.append({
                            "ticker": ticker,
                            "company_name": company,
                            "signal": latest.signal or "BULLISH",
                            "confidence_pct": latest.confidence_pct or 0,
                            "reason": f"Breakout: {is_breakout}, GoldenCross: {is_golden}, ProfitGr: {profit_growth}%",
                            "profit_growth_pct": round(float(profit_growth), 1),
                        })
                    except Exception:
                        continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER earnings_pioneers] {_se}")

        elif preset == "institutional_capitulation":
            try:
                from services.factor_engine import FactorEngine
                from datetime import timedelta
                # Check options data for high PCR
                with get_session() as session:
                    # Query recent analysis for tickers with bearish signals
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.analysis_date >= (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    ).order_by(AnalysisHistory.created_at.desc()).limit(40).all()
                    seen: set[str] = set()
                    for r in rows:
                        if r.ticker in seen:
                            continue
                        seen.add(r.ticker)
                        try:
                            ns = _to_ns(r.ticker)
                            info = _yf_fetch_info(ns)
                            rsi_val = None
                            # Try to get RSI from various yfinance fields or compute approximate
                            try:
                                import yfinance as yf
                                t = yf.Ticker(ns)
                                hist = t.history(period="1mo")
                                if len(hist) >= 14:
                                    delta = hist["Close"].diff()
                                    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
                                    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
                                    rs = gain / loss.replace(0, 1e-10)
                                    rsi_val = 100 - (100 / (1 + float(rs.iloc[-1])))
                            except Exception:
                                rsi_val = None
                            if rsi_val is None or rsi_val >= 30:
                                continue
                            # Check PCR from options or use yfinance options data
                            pcr_val = None
                            try:
                                opt = t.options
                                if opt:
                                    nearest = opt[0]
                                    chain = t.option_chain(nearest)
                                    total_puts = sum(p.volume or 0 for p in chain.puts)
                                    total_calls = sum(c.volume or 0 for c in chain.calls)
                                    if total_calls > 0:
                                        pcr_val = round(total_puts / total_calls, 2)
                            except Exception:
                                pcr_val = None
                            if pcr_val is None or pcr_val <= 1.5:
                                continue
                            company = info.get("longName") or info.get("shortName") or r.ticker
                            results.append({
                                "ticker": r.ticker,
                                "company_name": company,
                                "signal": "CAUTIOUSLY BEARISH",
                                "confidence_pct": r.confidence_pct or 0,
                                "reason": f"RSI: {rsi_val:.1f} (oversold), PCR: {pcr_val} (extreme fear)",
                                "rsi": round(rsi_val, 1),
                                "pcr": pcr_val,
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER institutional_capitulation] {_se}")

        elif preset == "quality_value":
            try:
                from datetime import timedelta
                cutoff_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
                with get_session() as session:
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.analysis_date >= cutoff_date,
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                        AnalysisHistory.confidence_pct > 65,
                    ).order_by(AnalysisHistory.confidence_pct.desc()).all()
                    seen: dict[str, tuple] = {}
                    for r in rows:
                        if r.ticker not in seen:
                            seen[r.ticker] = (r.signal, r.confidence_pct, r.full_json)
                candidates = list(seen.items())

                for ticker, (signal, conf, fj) in candidates:
                    try:
                        ns = _to_ns(ticker)
                        info = _yf_fetch_info(ns)
                        pe = info.get("trailingPE") or info.get("forwardPE")
                        sector = info.get("sector") or "Unknown"
                        sector_pe = SECTOR_PE_MAP.get(sector, 25)
                        if pe is None or pe <= 0 or pe >= sector_pe:
                            continue
                        company = info.get("longName") or info.get("shortName") or ticker
                        results.append({
                            "ticker": ticker,
                            "company_name": company,
                            "signal": signal,
                            "confidence_pct": conf,
                            "reason": f"Signal: {signal}, Confidence: {conf}%, PE below sector avg",
                        })
                    except Exception:
                        continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER quality_value] {_se}")

        elif preset == "promoter_conviction":
            try:
                from datetime import timedelta
                cutoff_60 = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d")
                with get_session() as session:
                    from sqlalchemy import func
                    latest_ids = session.query(
                        func.max(AnalysisHistory.id)
                    ).group_by(AnalysisHistory.ticker).all()
                    latest_ids = [row[0] for row in latest_ids]
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.id.in_(latest_ids),
                        AnalysisHistory.signal.notin_(["BEARISH", "CAUTIOUSLY BEARISH"]),
                    ).all()

                    bearish_flipped = set(
                        r.ticker for r in session.query(SignalEvent).filter(
                            SignalEvent.event_date >= cutoff_60,
                            SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"]),
                        ).all()
                    )

                    for r in rows:
                        if r.ticker in bearish_flipped:
                            continue
                        try:
                            data = json.loads(r.full_json)
                            fs = data.get("fundamentals_snapshot", {})
                            pledged = fs.get("promoter_pledged_pct")
                            if pledged is None:
                                pledged = r.promoter_pledged_pct
                            if pledged is None or pledged >= 10:
                                continue
                            company = data.get("company_name") or r.ticker
                            results.append({
                                "ticker": r.ticker,
                                "company_name": company,
                                "signal": r.signal,
                                "confidence_pct": r.confidence_pct or 0,
                                "reason": f"Low pledging ({pledged:.1f}%), signal: {r.signal}",
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER promoter_conviction] {_se}")

        elif preset == "fii_accumulation":
            try:
                with get_session() as session:
                    from sqlalchemy import func
                    tickers_with_multi = session.query(AnalysisHistory.ticker).group_by(
                        AnalysisHistory.ticker
                    ).having(func.count(AnalysisHistory.id) >= 2).all()
                    tickers_with_multi = [t[0] for t in tickers_with_multi]

                    for ticker in tickers_with_multi:
                        rows = session.query(AnalysisHistory).filter(
                            AnalysisHistory.ticker == ticker
                        ).order_by(AnalysisHistory.created_at.desc()).limit(2).all()
                        if len(rows) < 2:
                            continue
                        try:
                            d0 = json.loads(rows[0].full_json)
                            d1 = json.loads(rows[1].full_json)
                            fii0 = d0.get("fundamentals_snapshot", {}).get("fii_holding_pct")
                            fii1 = d1.get("fundamentals_snapshot", {}).get("fii_holding_pct")
                            if fii0 is None or fii1 is None:
                                continue
                            if fii0 <= fii1:
                                continue
                            company = d0.get("company_name") or ticker
                            results.append({
                                "ticker": ticker,
                                "company_name": company,
                                "signal": rows[0].signal,
                                "confidence_pct": rows[0].confidence_pct or 0,
                                "reason": f"FII increased: {fii1:.1f}% → {fii0:.1f}%",
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER fii_accumulation] {_se}")

        elif preset == "turnaround":
            try:
                with get_session() as session:
                    from sqlalchemy import func
                    latest_ids = session.query(
                        func.max(AnalysisHistory.id)
                    ).group_by(AnalysisHistory.ticker).all()
                    latest_ids = [row[0] for row in latest_ids]
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.id.in_(latest_ids),
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                    ).all()

                    for r in rows:
                        try:
                            data = json.loads(r.full_json)
                            ts_story = (data.get("key_factors") or {}).get("turnaround_story") or ""
                            if len(ts_story.strip()) <= 20:
                                continue
                            company = data.get("company_name") or r.ticker
                            results.append({
                                "ticker": r.ticker,
                                "company_name": company,
                                "signal": r.signal,
                                "confidence_pct": r.confidence_pct or 0,
                                "reason": ts_story.strip()[:60],
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER turnaround] {_se}")

        elif preset == "52w_low_bullish":
            try:
                with get_session() as session:
                    from sqlalchemy import func
                    latest_ids = session.query(
                        func.max(AnalysisHistory.id)
                    ).group_by(AnalysisHistory.ticker).all()
                    latest_ids = [row[0] for row in latest_ids]
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.id.in_(latest_ids),
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                    ).all()
                    rows_data = [(r.ticker, r.signal, r.confidence_pct, r.full_json) for r in rows]

                for ticker, signal, conf, fj in rows_data:
                    try:
                        ns = _to_ns(ticker)
                        info = _yf_fetch_info(ns)
                        current = info.get("currentPrice") or info.get("regularMarketPrice")
                        low52 = info.get("fiftyTwoWeekLow")
                        if not current or not low52 or low52 <= 0:
                            continue
                        if current > low52 * 1.15:
                            continue
                        company = info.get("longName") or info.get("shortName") or ticker
                        try:
                            fj_data = json.loads(fj)
                            company = fj_data.get("company_name") or company
                        except Exception:
                            pass
                        results.append({
                            "ticker": ticker,
                            "company_name": company,
                            "signal": signal,
                            "confidence_pct": conf or 0,
                            "reason": "Price near 52W low, signal bullish",
                        })
                    except Exception:
                        continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER 52w_low_bullish] {_se}")

        else:
            return []

        if not results:
            _seed = {
                "ghar_ghar_modi":         [("TCS","Tata Consultancy Services"),("INFY","Infosys"),("HCLTECH","HCL Technologies"),("TECHM","Tech Mahindra"),("WIPRO","Wipro")],
                "earnings_pioneers":      [("TATAMOTORS","Tata Motors"),("BAJFINANCE","Bajaj Finance"),("LT","Larsen & Toubro"),("BHARTIARTL","Bharti Airtel"),("TITAN","Titan")],
                "institutional_capitulation": [("HDFCBANK","HDFC Bank"),("ICICIBANK","ICICI Bank"),("SBIN","SBI"),("AXISBANK","Axis Bank"),("KOTAKBANK","Kotak Mahindra")],
                "quality_value":        [("RELIANCE","Reliance Industries"),("TCS","Tata Consultancy Services"),("INFY","Infosys"),("HDFCBANK","HDFC Bank"),("ICICIBANK","ICICI Bank")],
                "promoter_conviction":  [("WIPRO","Wipro"),("HCLTECH","HCL Technologies"),("BAJAJFINSV","Bajaj Finserv"),("TITAN","Titan Company"),("PIDILITIND","Pidilite Industries")],
                "fii_accumulation":     [("LT","Larsen & Toubro"),("SBIN","State Bank of India"),("AXISBANK","Axis Bank"),("KOTAKBANK","Kotak Mahindra Bank"),("ADANIPORTS","Adani Ports")],
                "turnaround":           [("TATASTEEL","Tata Steel"),("HINDALCO","Hindalco Industries"),("JSWSTEEL","JSW Steel"),("VEDL","Vedanta"),("SAIL","Steel Authority of India")],
                "52w_low_bullish":      [("DRREDDY","Dr Reddys Labs"),("SUNPHARMA","Sun Pharma"),("CIPLA","Cipla"),("DIVISLAB","Divis Labs"),("APOLLOHOSP","Apollo Hospitals")],
            }
            for _ticker, _name in _seed.get(preset, []):
                results.append({"ticker": _ticker, "company_name": _name, "signal": "CAUTIOUSLY BULLISH", "confidence_pct": 60, "reason": "Seed pick — run a deep analysis to get a live signal"})

        _yf_circuit_record_success()
        return results
    except Exception as _top_err:
        print(f"[SCREENER] Top-level error: {_top_err}")
        _yf_circuit_record_failure()
        return []


# ---------------------------------------------------------------------------
# GET /daily-action/{user_id}
# ---------------------------------------------------------------------------
@router.get("/daily-action/{user_id}")
def daily_action_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        from datetime import timedelta

        warnings = []
        try:
            # Inline the signal warnings logic (from portfolio router or helper)
            from helpers import get_session, Portfolio, AnalysisHistory, SignalEvent
            with get_session() as session:
                holdings = session.query(Portfolio).filter_by(
                    user_id=user_id, group_name="holdings"
                ).all()
                held_tickers = [h.ticker for h in holdings]
                for ticker in held_tickers:
                    row = session.query(AnalysisHistory).filter(
                        AnalysisHistory.ticker == ticker
                    ).order_by(AnalysisHistory.created_at.desc()).first()
                    if not row:
                        continue
                    prev = session.query(AnalysisHistory).filter(
                        AnalysisHistory.ticker == ticker,
                        AnalysisHistory.id < row.id
                    ).order_by(AnalysisHistory.created_at.desc()).first()
                    if not prev:
                        continue
                    if row.signal != prev.signal:
                        warnings.append({
                            "ticker": ticker,
                            "signal": row.signal,
                            "prev_signal": prev.signal,
                            "signal_flipped": True,
                            "is_bearish": row.signal in {"BEARISH", "CAUTIOUSLY BEARISH"},
                        })
                    elif row.signal in {"BEARISH", "CAUTIOUSLY BEARISH"}:
                        warnings.append({
                            "ticker": ticker,
                            "signal": row.signal,
                            "signal_flipped": False,
                            "is_bearish": True,
                        })
        except Exception:
            pass

        conflicts = []
        try:
            with get_session() as session:
                holdings = session.query(Portfolio).filter_by(
                    user_id=user_id, group_name="holdings"
                ).all()
                held_tickers = [h.ticker for h in holdings]
                for ticker in held_tickers:
                    row = session.query(AnalysisHistory).filter(
                        AnalysisHistory.ticker == ticker
                    ).order_by(AnalysisHistory.created_at.desc()).first()
                    if not row or not row.full_json:
                        continue
                    try:
                        data = json.loads(row.full_json)
                        cp = data.get("current_price_inr")
                        tp = data.get("target_prices") or {}
                        st = tp.get("short_term_3m")
                        lt = tp.get("long_term_36m")
                        if cp and st and lt and cp > 0:
                            if (st > cp) != (lt > cp):
                                conflicts.append({
                                    "ticker": ticker,
                                    "short": round((st - cp) / cp * 100, 1),
                                    "long": round((lt - cp) / cp * 100, 1),
                                })
                    except Exception:
                        pass
        except Exception:
            pass

        triggered = []
        try:
            with get_session() as session:
                from helpers import PriceTarget
                alerts = session.query(PriceTarget).filter_by(
                    user_id=user_id, triggered=True
                ).all()
                triggered = [{"ticker": a.ticker, "direction": a.direction, "price": a.target_price} for a in alerts]
        except Exception:
            pass

        urgency = "low"
        if triggered or any(w.get("is_bearish") for w in warnings):
            urgency = "high"
        elif warnings or conflicts:
            urgency = "medium"

        action = "Review your portfolio — no urgent signals detected today."
        if os.getenv("DEEPSEEK_API_KEY"):
            try:
                context_parts = []
                if triggered:
                    context_parts.append(f"Triggered alerts: {', '.join(t['ticker'] for t in triggered)}")
                if warnings:
                    bearish = [w['ticker'] for w in warnings if w.get('is_bearish')]
                    flipped = [w['ticker'] for w in warnings if w.get('signal_flipped')]
                    if bearish: context_parts.append(f"Bearish signals: {', '.join(bearish)}")
                    if flipped: context_parts.append(f"Signal flips: {', '.join(flipped)}")
                if conflicts:
                    context_parts.append(f"Timeframe conflicts: {', '.join(c['ticker'] for c in conflicts)}")

                prompt = (
                    f"Portfolio data:\n{chr(10).join(context_parts) if context_parts else 'No urgent signals.'}\n\n"
                    "In exactly one sentence of max 20 words, what is the single most important "
                    "thing this investor should do today? Be specific — name the ticker."
                )
                action = _deepseek_chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=256,
                    temperature=0,
                    log_endpoint="daily_action",
                ).strip().rstrip(".")
            except Exception as e:
                print(f"[DAILY-ACTION] DeepSeek failed: {e}")

        return {"action": action, "urgency": urgency}

    except Exception as e:
        return {"action": "Check your portfolio for any recent signal changes.", "urgency": "low"}


# ---------------------------------------------------------------------------
# GET /token-stats
# ---------------------------------------------------------------------------
@router.get("/token-stats")
def token_stats_endpoint(authorization: str = Header(None)):
    require_admin(authorization)
    try:
        HAIKU_INPUT_RATE  = 0.001 / 1_000_000
        HAIKU_OUTPUT_RATE = 0.005 / 1_000_000
        SONNET_INPUT_RATE  = 0.003 / 1_000_000
        SONNET_OUTPUT_RATE = 0.015 / 1_000_000

        if not TOKEN_LOG_PATH.exists():
            return {
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "cost_by_endpoint": {},
                "cache_hit_rate_pct": 0.0,
                "most_expensive_endpoint": None,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_read_tokens": 0,
            }

        total_cost = 0.0
        total_calls = 0
        cost_by_ep: dict[str, float] = {}
        total_input = 0
        total_output = 0
        total_cache_read = 0

        with open(TOKEN_LOG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                inp = entry.get("input_tokens", 0) or 0
                out = entry.get("output_tokens", 0) or 0
                cr  = entry.get("cache_read_input_tokens", 0) or 0
                model = (entry.get("model") or "").lower()
                endpoint = entry.get("endpoint") or "unknown"

                if "haiku" in model:
                    cost = inp * HAIKU_INPUT_RATE + out * HAIKU_OUTPUT_RATE
                else:
                    cost = inp * SONNET_INPUT_RATE + out * SONNET_OUTPUT_RATE

                total_cost += cost
                total_calls += 1
                total_input += inp
                total_output += out
                total_cache_read += cr
                cost_by_ep[endpoint] = cost_by_ep.get(endpoint, 0.0) + cost

        cache_hit_rate = round(total_cache_read / total_input * 100, 2) if total_input > 0 else 0.0
        most_expensive = max(cost_by_ep, key=lambda k: cost_by_ep[k]) if cost_by_ep else None

        from collections import defaultdict
        day_costs: dict = defaultdict(float)
        day_calls: dict = defaultdict(int)
        with open(TOKEN_LOG_PATH, "r") as f2:
            for line in f2:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    day = (e.get("timestamp") or "")[:10]
                    if day:
                        inp2 = e.get("input_tokens", 0) or 0
                        out2 = e.get("output_tokens", 0) or 0
                        model2 = (e.get("model") or "").lower()
                        c2 = (inp2 * HAIKU_INPUT_RATE + out2 * HAIKU_OUTPUT_RATE) if "haiku" in model2 else (inp2 * SONNET_INPUT_RATE + out2 * SONNET_OUTPUT_RATE)
                        day_costs[day] += c2
                        day_calls[day] += 1
                except Exception:
                    continue

        unique_days = len(day_costs) or 1
        monthly_est = round(total_cost / unique_days * 30, 2)
        last_7 = sorted(day_costs.keys(), reverse=True)[:7]

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_cost_inr": round(total_cost * 83.5, 2),
            "total_calls": total_calls,
            "cost_by_endpoint": {k: round(v, 6) for k, v in sorted(cost_by_ep.items(), key=lambda x: x[1], reverse=True)},
            "cache_hit_rate_pct": cache_hit_rate,
            "most_expensive_endpoint": most_expensive,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_read_tokens": total_cache_read,
            "estimated_monthly_usd": monthly_est,
            "last_7_days": [{"date": d, "calls": day_calls[d], "cost_usd": round(day_costs[d], 6)} for d in last_7],
        }
    except Exception as e:
        print(f"[TOKEN-STATS] Error: {e}")
        return {
            "total_cost_usd": 0.0,
            "total_calls": 0,
            "cost_by_endpoint": {},
            "cache_hit_rate_pct": 0.0,
            "most_expensive_endpoint": None,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cache_read_tokens": 0,
        }
