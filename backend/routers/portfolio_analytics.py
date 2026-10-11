"""Portfolio analytics routes: benchmark, signal warnings, SIP calculator, valuation history, charts,
risk analysis, red flags, macro impact, timeframe conflicts, net-worth ledger, attribution and
signal accuracy.

Split out of routers/portfolio.py (ARCH-14); paths, handler names and tags are unchanged.
main.py must include this router BEFORE routers.portfolio, so GET /portfolio/benchmark and
/portfolio/signal-warnings are not captured by GET /portfolio/{user_id}.
"""
import logging
import json
import time
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from collections import defaultdict
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from core.security import require_user_match, require_admin
import yfinance as yf
from helpers import (
    get_session, _resolve_ticker, _to_ns, _yf_price, _yf_fetch_info,
    _dcache_get, _dcache_set, User, Portfolio, AnalysisHistory, SignalEvent,
    PortfolioValuationHistory, NetWorthLedger, _extract_json_from_text, require_auth,
    format_indian_currency,
)
import os
from services.market_service import get_rbi_policy
from services.llm_utils import deepseek_chat as _deepseek_chat
from services.kyc_consent_service import AI_PROCESSING_CONSENT, has_active_consent
from services import llm_budget
from services.portfolio_service import (
    _get_asm_gsm_lists, _risk_label, compute_sip, compute_pearson_correlation,
)
from pydantic import BaseModel as _BaseModel, Field as _Field
from typing import Optional as _Optional

router = APIRouter(tags=["Portfolio"])


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


# ── Item 35: SIP Calculator ───────────────────────────────────────────
# Bounded (MATH-17): at most 600 loop months, and every value stays finite (no inf -> 500).
class SIPCalculatorRequest(_BaseModel):
    monthly_amount: float = _Field(gt=0, le=1e8)
    expected_return_pct: float = _Field(ge=-50, le=50)
    years: int = _Field(ge=1, le=50)
    step_up_pct: float = _Field(default=0.0, ge=0, le=100)


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
def portfolio_benchmark(user_id: int, _caller: int = Depends(require_user_match)):
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


_MACRO_IMPACT_TTL = 7200  # 2 hours


# _nse_session, _get_asm_gsm_lists, _risk_label imported from services.portfolio_service


# ---------------------------------------------------------------------------
# 0. GET /portfolio/signal-warnings  (MUST be before /portfolio/{user_id})
# ---------------------------------------------------------------------------
@router.get("/portfolio/signal-warnings")
def portfolio_signal_warnings(user_id: int, _caller: int = Depends(require_user_match)):
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
# 13. GET /api/v1/portfolio/valuation-history
# ---------------------------------------------------------------------------
@router.get("/api/v1/portfolio/valuation-history")
def get_valuation_history(user_id: int, days: int = 90, _caller: int = Depends(require_user_match)):
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
    _caller: int = Depends(require_user_match),
    regenerate: bool = False,
):
    """
    Generate portfolio charts as PNG images. Returns list of chart metadata with URLs.

Charts are cached on disk per user. Set ?regenerate=true to force re‑generation.
Uses a thread-pool executor so the event loop is never blocked.

    Args:
        user_id (int): The user_id (must be the bearer's own id).
        regenerate (bool): The regenerate.

    Returns:
        Any: The response.
    """
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
def portfolio_risk_analysis_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
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
def portfolio_red_flags_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
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
            summary = f"{len(flags)} red flag(s) detected across the portfolio."
            try:
                # Red flags summary → DeepSeek V4 Flash (Tier 1 bulk task), consented users only
                if os.getenv("DEEPSEEK_API_KEY") and has_active_consent(user_id, AI_PROCESSING_CONSENT):
                    llm_budget.guard(user_id, "red_flags_summary")  # over budget -> default summary
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
def macro_impact_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
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
        rbi = get_rbi_policy()
        macro["rbi_repo_rate_pct"] = rbi["rbi_repo_rate_pct"]
        macro["rbi_repo_rate_as_of"] = rbi["rbi_repo_rate_as_of"]
        if rbi["rbi_repo_rate_pct"] is None:
            repo_str = "unavailable"
        else:
            repo_str = f"{rbi['rbi_repo_rate_pct']}% (as of {rbi['rbi_repo_rate_as_of'] or 'unknown date'})"

        holdings_list = "\n".join(f"- {t}: {c}" for t, c in holdings_data)
        macro_str = (
            f"Brent crude: ${macro.get('brent_oil_usd') or 'N/A'}/bbl, "
            f"India VIX: {macro.get('india_vix') or 'unavailable'}, "
            f"USD/INR: {macro.get('usd_inr') or 'N/A'}, "
            f"RBI repo rate: {repo_str}"
        )
        prompt = (
            f"Current Indian macro environment: {macro_str}\n\n"
            f"Holdings:\n{holdings_list}\n\n"
            "For each ticker write one sentence on macro impact and classify direction. "
            "Return ONLY valid JSON array, no markdown:\n"
            '[{"ticker": "TICKER", "impact_statement": "...", "direction": "positive|negative|neutral"}]'
        )

        # Macro impact → DeepSeek V4 Flash (Tier 1 bulk task), consented users only
        consent_ok = has_active_consent(user_id, AI_PROCESSING_CONSENT)
        impacts = []
        if os.getenv("DEEPSEEK_API_KEY") and consent_ok:
            try:
                llm_budget.guard(user_id, "macro_impact")  # over budget -> "assessment unavailable"
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
            note = ("DeepSeek API key not configured." if consent_ok else
                    "Enable 'AI processing' in Settings > Account Security > KYC Consents for a macro assessment.")
            impacts = [{"ticker": t, "impact_statement": note, "direction": "neutral"} for t, _ in holdings_data]

        result = {
            "user_id": user_id,
            "macro_readings": macro,
            "impacts": impacts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if consent_ok:  # never pin the consent hint in the 2h cache
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
def portfolio_timeframe_conflicts_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
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
# 24. GET /api/v1/market/net-worth-ledger/{user_id}
# ---------------------------------------------------------------------------
# format_indian_currency is imported from helpers (canonical location)


@router.get("/api/v1/market/net-worth-ledger/{user_id}", response_model=NetWorthSnapshotResponse)
def net_worth_ledger_endpoint(
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
            detail="No net-worth snapshot yet. Snapshots are recorded daily after market close.",
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
def portfolio_attribution_endpoint(
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
def get_signal_accuracy(_admin: int = Depends(require_admin)):
    """
    Returns accuracy % by signal type. Admin only (REG-11): accuracy of the app's own
    BUY/SELL calls is an internal QA metric, not a user-facing (PaRRVA-unverified) claim.

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
