from helpers import (
    get_session, verify_access_token, EXCHANGE_SUFFIX, _resolve_ticker,
    _to_ns, _yf_price, _dcache_get, _dcache_set,
    _quick_info_cache, _QUICK_INFO_TTL, DataHarvestingError,
    EarningsSyncRatioResponse, YoYAggregateResponse, require_auth,
    InstitutionalLeaderboardResponse, NetWorthSnapshotResponse,
    User, Portfolio, AnalysisHistory, NetWorthLedger,
    MarketErrorLog, EarningsAlert, log_market_error,
    EarningsErrorLog, log_earnings_error,
    AdvisorBiography, TextAdvisoryInsight, IdeasErrorLog, log_ideas_error,
    _check_rate_limit, _get_indices_data, _get_asm_gsm_lists, _nse_session
)

from services.market_service import (
    _get_quarterly_fin, _yf_fetch_info, _fmt_inr_crores,
    _safe_float, _earnings_result_from_row, _scan_upcoming_earnings,
)

import json
import os
import time
import asyncio
import random
import math
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
import yfinance as yf
from services.scraper import (
    fetch_market_pulse, fetch_momentum, fetch_macro_alternatives,
    fetch_institutional_flow, fetch_earnings_sync_ratio,
    fetch_yoy_aggregate_indicators,
)
from services.options_scraper import fetch_option_chain, compute_derivatives_metrics
from services.nse_data_provider import get_price_history, get_fundamentals
from services.filings_extractor import harvest_filings, get_cached_filings

router = APIRouter(tags=["Market Data"])


@router.get("/market-indices")
def market_indices_endpoint():
    return _get_indices_data()


@router.get("/nifty-history")
def nifty_history_endpoint(days: int = 365):
    cache_key = f"nifty_history_{days}"
    cached = _dcache_get("market", cache_key)
    if cached is not None:
        return cached
    try:
        import time
        import random
        hist = None
        for attempt in range(3):
            try:
                t = yf.Ticker("^NSEI")
                hist = t.history(period=f"{days}d")
                if not hist.empty:
                    break
            except Exception as e:
                logging.info(f"[YF] Nifty history attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))

        if hist is None or hist.empty:
            return {"prices": []}

        result = []
        for date, row in hist.iterrows():
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2)
            })
        payload = {"prices": result}
        _dcache_set("market", cache_key, payload, ttl=1800)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/dividends/{ticker}")
def dividend_history_endpoint(ticker: str, exchange: str = "NSE"):
    try:
        try:
            from main import format_indian_currency
        except ImportError:
            def format_indian_currency(value, symbol="₹"):
                if value is None: return "N/A"
                abs_val = abs(value)
                sign = "-" if value < 0 else ""
                if abs_val >= 10000000:
                    return f"{sign}{symbol}{abs_val/10000000:,.2f} Crores"
                elif abs_val >= 100000:
                    return f"{sign}{symbol}{abs_val/100000:,.2f} Lakhs"
                else:
                    return f"{sign}{symbol}{abs_val:,.2f}"

        resolved_ticker = _resolve_ticker(ticker, exchange)
        t = yf.Ticker(resolved_ticker)
        divs = t.dividends
        
        current_price = None
        try:
            fast = t.fast_info
            current_price = getattr(fast, "last_price", None)
        except Exception as e:
            import logging
            logging.warning(f"Swallowed exception: {e}")

        history = []
        if divs is not None and not divs.empty:
            last_8 = divs.tail(8).sort_index(ascending=False)
            for d_date, amt in last_8.items():
                yield_pct = 0.0
                if current_price and current_price > 0:
                    yield_pct = round((amt / current_price) * 100, 2)
                
                dt_str = d_date.strftime("%Y-%m-%d") if hasattr(d_date, "strftime") else str(d_date)
                history.append({
                    "date": dt_str,
                    "amount": float(amt),
                    "amount_formatted": format_indian_currency(amt),
                    "yield_pct": yield_pct
                })
                
        next_ex_date = None
        cal = t.calendar
        if cal is not None:
            # yfinance calendar can be a dict or DataFrame depending on version
            cal_is_empty = False
            if hasattr(cal, "empty"):
                cal_is_empty = cal.empty
            elif isinstance(cal, dict):
                cal_is_empty = len(cal) == 0
            if not cal_is_empty:
                if "Dividend Date" in cal:
                    div_date = cal.get("Dividend Date")
                    if isinstance(div_date, list) and div_date:
                        div_date = div_date[0]
                    if str(div_date).strip() and str(div_date) != "NaT":
                        try:
                            next_ex_date = div_date.strftime("%Y-%m-%d")
                        except Exception as e:
                            import logging
                            logging.warning(f"Caught exception: {e}")
                            next_ex_date = str(div_date)
                        
        return {
            "ticker": ticker,
            "next_ex_date": next_ex_date,
            "dividends": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dividend data: {str(e)}")

@router.get("/mf/{scheme_code}")
def mutual_fund_nav_endpoint(scheme_code: str):
    try:
        import requests
        from config.settings import HTTP_DEFAULT_TIMEOUT as _HTTP_TIMEOUT
        resp = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=_HTTP_TIMEOUT)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch MF data")
        
        data = resp.json()
        meta = data.get("meta", {})
        nav_data = data.get("data", [])
        
        scheme_name = meta.get("scheme_name", "Unknown Scheme")
        
        nav_history = []
        for point in nav_data[:365]:
            nav_history.append({
                "date": point["date"],
                "nav": float(point["nav"])
            })
            
        current_nav = nav_history[0]["nav"] if nav_history else 0.0
        
        return_1y = 0.0
        if len(nav_history) >= 2:
            past_nav = nav_history[-1]["nav"]
            if past_nav > 0:
                return_1y = round(((current_nav - past_nav) / past_nav) * 100, 2)
                
        return {
            "scheme_name": scheme_name,
            "current_nav": current_nav,
            "return_1y_pct": return_1y,
            "nav_history": nav_history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/block-deals/{ticker}")
def block_deals_endpoint(
    ticker: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from database import BlockDeal
    try:
        with get_session() as db:
            deals = db.query(BlockDeal).filter(BlockDeal.ticker == ticker.upper()).order_by(BlockDeal.date.desc()).offset(offset).limit(limit).all()
            return {
                "ticker": ticker,
                "deals": [
                    {
                        "date": d.date,
                        "client_name": d.client_name,
                        "deal_type": d.deal_type,
                        "quantity": d.quantity,
                        "price": d.price
                    } for d in deals
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/fii-dii-flow")
def fii_dii_flow_endpoint(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from database import FIIDIIFlow
    try:
        with get_session() as db:
            flows = db.query(FIIDIIFlow).order_by(FIIDIIFlow.date.desc()).offset(offset).limit(limit).all()
            # Try to parse dates properly if needed or just return them
            return {
                "flows": [
                    {
                        "date": f.date,
                        "fii_buy": f.fii_buy,
                        "fii_sell": f.fii_sell,
                        "fii_net": f.fii_net,
                        "dii_buy": f.dii_buy,
                        "dii_sell": f.dii_sell,
                        "dii_net": f.dii_net
                    } for f in flows
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/quarterly-financials")
def quarterly_financials_endpoint(ticker: str, exchange: str = "NSE"):
    cache_key = f"quarterly_{ticker.upper()}_{exchange.upper()}"
    cached = _dcache_get("market", cache_key)
    if cached is not None:
        return cached
    try:
        exchange = exchange.upper()
        full_ticker = _resolve_ticker(ticker, exchange)
        t, fin = _get_quarterly_fin(full_ticker)
        result = []
        if fin is not None and not fin.empty:
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            profit_row = fin.loc["Net Income"] if "Net Income" in fin.index else None
            import math
            for col in list(fin.columns)[:8]:  # last 8 quarters
                label = col.strftime("Q%q %Y") if hasattr(col, 'strftime') else str(col)[:7]
                rev = float(rev_row[col]) / 1e7 if rev_row is not None and col in rev_row.index else 0  # in crores
                profit = float(profit_row[col]) / 1e7 if profit_row is not None and col in profit_row.index else 0
                rev = 0.0 if math.isnan(rev) or math.isinf(rev) else round(rev, 1)
                profit = 0.0 if math.isnan(profit) or math.isinf(profit) else round(profit, 1)
                result.append({"label": label, "revenue": rev, "net_profit": profit})
        # Fetch promoter holding history from quarterly balance sheet / info
        promoter_history = []
        try:
            # yfinance doesn't expose quarterly promoter holdings directly
            # Use the last 4 entries from analysis_history in our DB if available
            from database import get_session, AnalysisHistory
            with get_session() as session:
                rows = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker.upper()
                ).order_by(AnalysisHistory.created_at.desc()).limit(8).all()
                seen = {}
                for row in rows:
                    if row.full_json:
                        try:
                            data = json.loads(row.full_json)
                            fs = data.get("fundamentals_snapshot", {})
                            promoter = fs.get("promoter_holding_pct")
                            fii = fs.get("fii_holding_pct")
                            dii = fs.get("dii_holding_pct")
                            date_key = row.analysis_date[:7] if row.analysis_date else "?"
                            if date_key not in seen and promoter is not None:
                                seen[date_key] = True
                                promoter_history.append({
                                    "period": row.analysis_date,
                                    "promoter": promoter,
                                    "fii": fii or 0,
                                    "dii": dii or 0,
                                })
                        except Exception as e:
                            import logging
                            logging.warning(f"Swallowed exception: {e}")
            promoter_history = list(reversed(promoter_history[:4]))
        except Exception as e:
            import logging
            logging.warning(f"Swallowed exception: {e}")

        payload = {"quarters": result, "promoter_history": promoter_history}
        _dcache_set("market", cache_key, payload, ttl=3600)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/macro-strip")
def macro_strip_endpoint():
    """
    Returns USD/INR rate, crude oil price, and RBI repo rate for context strip.

    Args:

    Returns:
        Any: The response.
    """
    try:
        import math
        result = {}

        # USD/INR
        try:
            t = yf.Ticker("USDINR=X")
            info = t.info
            usd_inr = info.get("regularMarketPrice") or info.get("currentPrice")
            if usd_inr and not math.isnan(float(usd_inr)):
                result["usd_inr"] = round(float(usd_inr), 2)
            else:
                result["usd_inr"] = None
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            result["usd_inr"] = None

        # Crude oil (WTI)
        try:
            t = yf.Ticker("CL=F")
            info = t.info
            crude = info.get("regularMarketPrice") or info.get("currentPrice")
            if crude and not math.isnan(float(crude)):
                result["crude_oil_usd"] = round(float(crude), 2)
            else:
                result["crude_oil_usd"] = None
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            result["crude_oil_usd"] = None

        # Brent crude (India imports Brent-priced oil, more relevant than WTI)
        try:
            t = yf.Ticker("BZ=F")
            info = t.info
            brent = info.get("regularMarketPrice") or info.get("currentPrice")
            if brent and not math.isnan(float(brent)):
                result["brent_oil_usd"] = round(float(brent), 2)
            else:
                result["brent_oil_usd"] = None
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            result["brent_oil_usd"] = None

        # India VIX — fear gauge for Indian retail markets
        # Fix 2.16: fallback to historical average (~16) when scraper fails
        INDIA_VIX_HISTORICAL_AVG = 16.0
        try:
            t = yf.Ticker("^INDIAVIX")
            info = t.info
            vix = info.get("regularMarketPrice") or info.get("currentPrice")
            if vix and not math.isnan(float(vix)):
                result["india_vix"] = round(float(vix), 2)
                result["india_vix_source"] = "live"
            else:
                result["india_vix"] = INDIA_VIX_HISTORICAL_AVG
                result["india_vix_source"] = "historical_avg_fallback"
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            result["india_vix"] = INDIA_VIX_HISTORICAL_AVG
            result["india_vix_source"] = "historical_avg_fallback"

        # RBI repo rate — hardcoded (changes rarely, update manually)
        result["rbi_repo_rate_pct"] = 6.50
        result["rbi_stance"] = "Neutral"

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/macro-context/{ticker}")
def macro_context_endpoint(ticker: str, exchange: str = "NSE", sector: str = ""):
    """
    Returns macro context for a specific stock: strip data, FII/DII trend,
sector performance, Market Mood Index, deterministic impact mapping, and
AI-generated analysis if a cached analysis exists.

    Args:
        ticker (str): The ticker.
        exchange (str): The exchange.
        sector (str): The sector.

    Returns:
        Any: The response.
    """
    import math as _m_ctx
    try:
        _dcache_key = f"macro_ctx_{ticker.upper()}_{sector}"
        _dcached = _dcache_get("market", _dcache_key)
        if _dcached is not None:
            return _dcached

        result = {
            "ticker": ticker.upper(),
            "macro_strip": {},
            "fii_dii_trend": {},
            "sector_performance": {},
            "market_mood": {},
            "stock_impact": [],
            "summary": "",
        }

        # -- 1. Macro strip ---------------------------------------------------
        try:
            t_usd = yf.Ticker("USDINR=X")
            usd_info = t_usd.info
            usd_inr = usd_info.get("regularMarketPrice") or usd_info.get("currentPrice")
            if usd_inr and not _m_ctx.isnan(float(usd_inr)):
                result["macro_strip"]["usd_inr"] = round(float(usd_inr), 2)

            t_brent = yf.Ticker("BZ=F")
            brent_info = t_brent.info
            brent = brent_info.get("regularMarketPrice") or brent_info.get("currentPrice")
            if brent and not _m_ctx.isnan(float(brent)):
                result["macro_strip"]["brent_oil_usd"] = round(float(brent), 2)

            t_vix = yf.Ticker("^INDIAVIX")
            vix_info = t_vix.info
            vix = vix_info.get("regularMarketPrice") or vix_info.get("currentPrice")
            if vix and not _m_ctx.isnan(float(vix)):
                result["macro_strip"]["india_vix"] = round(float(vix), 2)
            else:
                result["macro_strip"]["india_vix"] = 16.0

            result["macro_strip"]["rbi_repo_rate_pct"] = 6.50
            result["macro_strip"]["rbi_stance"] = "Neutral"
        except Exception as e:
            result["macro_strip"]["_error"] = str(e)

        # -- 2. FII/DII trend -------------------------------------------------
        try:
            from database import FIIDIIFlow, get_session as _get_db_sess
            with _get_db_sess() as db:
                flows = db.query(FIIDIIFlow).order_by(FIIDIIFlow.date.desc()).limit(5).all()
                if flows:
                    total_fii = sum(f.fii_net or 0 for f in flows)
                    total_dii = sum(f.dii_net or 0 for f in flows)
                    result["fii_dii_trend"] = {
                        "last_5_sessions": [
                            {"date": str(f.date), "fii_net": f.fii_net, "dii_net": f.dii_net}
                            for f in flows
                        ],
                        "fii_net_5d_crores": round(total_fii, 0),
                        "dii_net_5d_crores": round(total_dii, 0),
                    }
                    if total_fii < -500:
                        result["fii_dii_trend"]["bias"] = "FII_SELLING"
                    elif total_fii > 500:
                        result["fii_dii_trend"]["bias"] = "FII_BUYING"
                    elif total_dii > 500 and total_fii < 0:
                        result["fii_dii_trend"]["bias"] = "DII_SUPPORTING"
                    else:
                        result["fii_dii_trend"]["bias"] = "NEUTRAL"
        except Exception as e:
            result["fii_dii_trend"] = {"_error": str(e), "bias": "NEUTRAL"}

        # -- 3. Sector performance --------------------------------------------
        try:
            from services.scraper import fetch_market_pulse
            pulse = fetch_market_pulse()
            sectors = pulse.get("sectors", [])
            sector_name = sector or "Unknown"
            for s in sectors:
                if s.get("name", "").lower() == sector_name.lower():
                    result["sector_performance"] = {
                        "name": s.get("name"),
                        "change_pct": s.get("change_pct"),
                    }
                    break
            result["sector_performance"]["nifty_change_pct"] = pulse.get("nifty_change_pct")
        except Exception as e:
            result["sector_performance"] = {"_error": str(e)}

        # -- 4. Market Mood Index ---------------------------------------------
        vix_val = result["macro_strip"].get("india_vix", 16)
        fii_bias = result["fii_dii_trend"].get("bias", "NEUTRAL")
        if vix_val > 25 and fii_bias == "FII_SELLING":
            zone = "EXTREME_FEAR"; score = 20
        elif vix_val > 20:
            zone = "FEAR"; score = 35
        elif vix_val > 15 and fii_bias == "FII_BUYING":
            zone = "GREED"; score = 65
        elif vix_val < 12 and fii_bias == "FII_BUYING":
            zone = "EXTREME_GREED"; score = 80
        else:
            zone = "NEUTRAL"; score = 50
        interp_map = {
            "EXTREME_FEAR": "Markets oversold — historically good entry points for long-term investors",
            "FEAR": "Cautious sentiment — observe before deploying heavy capital",
            "NEUTRAL": "Balanced sentiment — normal market conditions",
            "GREED": "Markets overbought — hold existing positions, avoid fresh entries",
            "EXTREME_GREED": "Euphoria zone — consider profit booking, high risk of correction",
        }
        result["market_mood"] = {
            "zone": zone, "score": score, "india_vix": vix_val,
            "interpretation": interp_map.get(zone, ""),
        }

        # -- 5. Deterministic impact mapping ----------------------------------
        sector_lower = (sector or "").lower()
        impacts = []
        brent_val = result["macro_strip"].get("brent_oil_usd")
        if brent_val:
            if any(kw in sector_lower for kw in ("oil", "energy", "petroleum")):
                impacts.append({"factor": "Brent Crude", "value": f"${brent_val}/bbl",
                    "impact": "POSITIVE",
                    "detail": "Higher crude directly benefits upstream margins. Every $1/bbl rise adds to revenue per barrel of domestic production."})
            elif any(kw in sector_lower for kw in ("paint", "chemical", "aviation", "tyre", "logistics")):
                impacts.append({"factor": "Brent Crude", "value": f"${brent_val}/bbl",
                    "impact": "NEGATIVE",
                    "detail": "Crude is a key input cost. Sustained high prices compress EBITDA margins in this sector."})
            elif any(kw in sector_lower for kw in ("it", "software", "technology")):
                impacts.append({"factor": "Brent Crude", "value": f"${brent_val}/bbl",
                    "impact": "INDIRECT",
                    "detail": "Crude impacts client budgets in energy-dependent verticals. Marginally negative for IT services demand from oil-dependent economies."})
            else:
                impacts.append({"factor": "Brent Crude", "value": f"${brent_val}/bbl",
                    "impact": "NEUTRAL",
                    "detail": "No direct margin linkage. Indirect impact via inflation expectations and input costs across the supply chain."})

        usd_val = result["macro_strip"].get("usd_inr")
        if usd_val:
            if any(kw in sector_lower for kw in ("it", "software", "technology", "pharma")):
                impacts.append({"factor": "USD/INR", "value": f"Rs.{usd_val}",
                    "impact": "POSITIVE",
                    "detail": f"Rupee depreciation boosts export revenues. Every Rs.1 weakness adds to operating margins for exporters billing in USD."})
            elif any(kw in sector_lower for kw in ("oil", "energy", "chemical", "aviation")):
                impacts.append({"factor": "USD/INR", "value": f"Rs.{usd_val}",
                    "impact": "NEGATIVE",
                    "detail": "Weaker rupee increases cost of dollar-denominated imports (crude, raw materials). Margin compression risk."})
            else:
                impacts.append({"factor": "USD/INR", "value": f"Rs.{usd_val}",
                    "impact": "MONITOR",
                    "detail": "Indirect impact. FII sentiment turns cautious above Rs.85/USD as dollar returns shrink in rupee terms."})

        repo = result["macro_strip"].get("rbi_repo_rate_pct", 6.5)
        if repo:
            if any(kw in sector_lower for kw in ("bank", "finance", "nbfc", "housing")):
                if repo < 7:
                    impacts.append({"factor": "RBI Repo Rate", "value": f"{repo}%",
                        "impact": "POSITIVE",
                        "detail": f"Rate-sensitive sector. Lower rates boost credit growth and reduce NPAs. Every 25bps cut adds ~15bps to bank NIMs."})
                else:
                    impacts.append({"factor": "RBI Repo Rate", "value": f"{repo}%",
                        "impact": "NEGATIVE",
                        "detail": "Higher rates compress NIMs and slow credit offtake. Every 25bps hike reduces loan demand with ~2 quarter lag."})
            elif any(kw in sector_lower for kw in ("real estate", "auto", "infra")):
                impacts.append({"factor": "RBI Repo Rate", "value": f"{repo}%",
                    "impact": "INTEREST_RATE_SENSITIVE",
                    "detail": "Demand linked to borrowing costs. Rate changes impact buyer affordability with a ~2 quarter lag."})
            else:
                impacts.append({"factor": "RBI Repo Rate", "value": f"{repo}%",
                    "impact": "NEUTRAL",
                    "detail": "Minimal direct impact. Broader economy effect via credit cycle and consumption demand."})

        bias = result["fii_dii_trend"].get("bias", "NEUTRAL")
        fii_net = result["fii_dii_trend"].get("fii_net_5d_crores", 0)
        if bias == "FII_SELLING":
            impacts.append({"factor": "FII/DII Flow", "value": f"{fii_net:.0f} Cr (FII 5D net)",
                "impact": "DII_SUPPORTING",
                "detail": "FIIs are net sellers but DIIs (mutual funds, insurance) are absorbing via SIP inflows. This suppresses volatility short-term but builds fragility if fundamentals don't improve. Watch for DII absorption fatigue."})
        elif bias == "FII_BUYING":
            impacts.append({"factor": "FII/DII Flow", "value": f"{fii_net:.0f} Cr (FII 5D net)",
                "impact": "POSITIVE",
                "detail": "FIIs accumulating — institutional conviction supporting the stock. Combined FII+DII buying typically precedes upward price momentum."})

        result["stock_impact"] = impacts

        # -- 6. AI-enhanced summary -------------------------------------------
        try:
            from database import AnalysisHistory, get_session as _get_db_sess2
            import json as _json2
            with _get_db_sess2() as db:
                last = db.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker.upper()
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if last:
                    try:
                        fj = _json2.loads(last.full_json) if isinstance(last.full_json, str) else last.full_json
                        kf = fj.get("key_factors", {})
                        macro_impact = kf.get("global_macro_impact", "")
                        sentiment = kf.get("indian_market_sentiment", "")
                        if macro_impact:
                            result["ai_summary"] = macro_impact
                            result["ai_sentiment"] = sentiment
                    except Exception as e:
                        import logging
                        logging.warning(f"Swallowed exception: {e}")
        except Exception as e:
            import logging
            logging.warning(f"Swallowed exception: {e}")

        if not result.get("ai_summary"):
            impact_lines = []
            for imp in impacts:
                if imp["impact"] in ("POSITIVE", "NEGATIVE"):
                    impact_lines.append(f"{imp['factor']} ({imp['value']}): {imp['impact']} — {imp['detail'][:100]}")
            result["summary"] = " | ".join(impact_lines[:3]) if impact_lines else "No significant macro headwinds or tailwinds detected."

        _dcache_set("market", _dcache_key, result, ttl=3600)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/earnings-calendar")
def earnings_calendar_endpoint():
    """
    Returns upcoming earnings dates for NSE portfolio stocks.

    Args:

    Returns:
        Any: The response.
    """
    cached = _dcache_get("market", "earnings_calendar")
    if cached is not None:
        return cached
    try:
        from database import get_session, Portfolio
        with get_session() as session:
            tickers = session.query(Portfolio.ticker).filter(
                Portfolio.group_name == "holdings"
            ).distinct().all()
            tickers = [t[0] for t in tickers]

        results = []
        today = datetime.now().date()

        for ticker_raw in tickers:
            try:
                full_ticker = _resolve_ticker(ticker_raw, "NSE")
                t = yf.Ticker(full_ticker)
                cal = t.calendar
                earnings_dates = []
                if isinstance(cal, dict) and 'Earnings Date' in cal:
                    dates_val = cal['Earnings Date']
                    if isinstance(dates_val, list):
                        earnings_dates = dates_val
                elif hasattr(cal, 'empty') and not cal.empty and 'Earnings Date' in cal.columns:
                    # fallback for older yfinance versions that return DataFrame
                    earnings_dates = cal['Earnings Date'].dropna().tolist()

                for d in earnings_dates:
                    try:
                        ed = d.date() if hasattr(d, 'date') else d
                        days_away = (ed - today).days
                        if -7 <= days_away <= 45:
                            results.append({
                                "ticker": ticker_raw.upper(),
                                "earnings_date": ed.strftime("%d-%b-%Y"),
                                "days_away": days_away,
                            })
                    except Exception as e:
                        import logging
                        logging.warning(f"Swallowed exception: {e}")
            except Exception as e:
                import logging
                logging.warning(f"Swallowed exception: {e}")

        results.sort(key=lambda x: x["days_away"])
        payload = {"events": results}
        _dcache_set("market", "earnings_calendar", payload, ttl=900)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analyst-ratings")
def analyst_ratings_endpoint(ticker: str, exchange: str = "NSE"):
    cache_key = f"analyst_ratings_{ticker.upper()}_{exchange.upper()}"
    cached = _dcache_get("market", cache_key)
    if cached is not None:
        return cached
    try:
        full_ticker = _resolve_ticker(ticker, exchange)

        import time
        import random
        recs = None
        for attempt in range(3):
            try:
                t = yf.Ticker(full_ticker)
                recs = t.recommendations
                if recs is not None and not recs.empty:
                    break
            except Exception as e:
                logging.info(f"[YF] Ratings attempt {attempt+1} failed for {full_ticker}: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))

        if recs is None or recs.empty:
            return {"ratings": [], "consensus": None}

        import math
        recent = recs.tail(10)
        ratings = []
        for _, row in recent.iterrows():
            firm = row.get("Firm", row.get("firm", "Unknown"))
            grade = row.get("To Grade", row.get("toGrade", row.get("Action", "")))
            period = row.name.strftime("%b %Y") if hasattr(row.name, 'strftime') else str(row.name)[:7]
            if firm and grade:
                ratings.append({"firm": str(firm), "grade": str(grade), "period": period})

        # Consensus
        BUY_KEYWORDS = ["BUY", "OUTPERFORM", "OVERWEIGHT", "ACCUMULATE", "ADD", "STRONG BUY", "POSITIVE", "TOP PICK", "UPGRADE"]
        SELL_KEYWORDS = ["SELL", "UNDERPERFORM", "UNDERWEIGHT", "REDUCE", "STRONG SELL", "NEGATIVE", "AVOID", "DOWNGRADE"]
        buys = sum(1 for r in ratings if any(w in r["grade"].upper() for w in BUY_KEYWORDS))
        sells = sum(1 for r in ratings if any(w in r["grade"].upper() for w in SELL_KEYWORDS))
        holds = len(ratings) - buys - sells
        if buys > sells and buys > holds: consensus = "BUY"
        elif sells > buys and sells > holds: consensus = "SELL"
        elif len(ratings) > 0: consensus = "HOLD"
        else: consensus = None

        payload = {"ratings": ratings[-6:], "consensus": consensus, "buy": buys, "hold": holds, "sell": sells}
        _dcache_set("market", cache_key, payload, ttl=3600)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ipo-calendar")
def ipo_calendar_endpoint():
    """
    Returns upcoming IPO data (best-effort from public sources).

    Args:

    Returns:
        Any: The response.
    """
    return {
        "ipos": UPCOMING_IPOS,
        "note": "IPO data from manual tracking.",
        "source": "Manual Tracking"
    }


@router.get("/sector-weekly")
def sector_weekly_endpoint():
    """
    Returns sector performance with 1-week and 1-day change. Handles holidays and NaN.

    Args:

    Returns:
        Any: The response.
    """
    SECTOR_ETFS = {
        "Nifty Bank": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Nifty Pharma": "^CNXPHARMA",
        "Nifty Auto": "^CNXAUTO",
        "Nifty FMCG": "^CNXFMCG",
        "Nifty Metal": "^CNXMETAL",
        "Nifty Energy": "^CNXENERGY",
        "Nifty Realty": "^CNXREALTY",
        "Nifty Infra": "^CNXINFRA",
        "Nifty Media": "^CNXMEDIA",
        "Nifty PSU Bank": "^CNXPSUBANK",
        "Nifty MidCap": "^NSEMDCP50",
    }
    import math
    import time
    import random
    results = []
    for name, sym in SECTOR_ETFS.items():
        try:
            hist = None
            for attempt in range(3):
                try:
                    t = yf.Ticker(sym)
                    hist = t.history(period="8d")
                    if not hist.empty and len(hist) >= 2:
                        break
                except Exception as e:
                    logging.info(f"[YF] Sector attempt {attempt+1} failed for {sym}: {e}")
                    if attempt < 2:
                        time.sleep((1.0 * (2 ** attempt)) + (random.random() * 0.2))

            if hist is None or hist.empty or len(hist) < 2:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < 2:
                continue

            valid_closes = [float(c) for c in closes if not math.isnan(float(c))]
            if len(valid_closes) < 2:
                continue

            current = valid_closes[-1]
            prev_day = valid_closes[-2]
            week_ago = valid_closes[0] if len(valid_closes) >= 5 else prev_day

            if math.isnan(current) or math.isnan(prev_day) or prev_day == 0:
                continue

            day_chg = round((current - prev_day) / prev_day * 100, 2)
            week_chg = round((current - week_ago) / week_ago * 100, 2) if week_ago != 0 else 0.0
            results.append({
                "name": name,
                "ticker": sym,
                "value": round(current, 2),
                "change_pct": day_chg,
                "change_abs": round(current - prev_day, 2),
                "week_change_pct": week_chg,
            })
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            continue
    return {"sectors": results}


# ---------------------------------------------------------------------------
# Stock Directory Search
# ---------------------------------------------------------------------------

# Load NSE/BSE directory from JSON — falls back to empty list if file missing
_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "nse_bse_symbols.json")
try:
    with open(_DATA_FILE, "r", encoding="utf-8") as _f:
        _raw = json.load(_f)
    _NSE_DIRECTORY = [
        {"ticker": e["ticker"], "company_name": e["name"], "sector": e["sector"], "exchange": e.get("exchange", "NSE")}
        for e in _raw
    ]
except Exception as _e:
    import logging as _logging
    _logging.getLogger(__name__).warning("market.py: failed to load %s: %s", _DATA_FILE, _e)
    _NSE_DIRECTORY = []

# Legacy inline fallback entry (kept so the variable always has at least one entry for tests)
_NSE_DIRECTORY = _NSE_DIRECTORY or [
    {"ticker": "RELIANCE",    "company_name": "Reliance Industries Ltd",        "sector": "Oil & Gas"},
    {"ticker": "TCS",         "company_name": "Tata Consultancy Services",      "sector": "IT"},
    {"ticker": "HDFCBANK",    "company_name": "HDFC Bank Ltd",                  "sector": "Banking"},
    {"ticker": "INFY",        "company_name": "Infosys Ltd",                    "sector": "IT"},
    {"ticker": "ICICIBANK",   "company_name": "ICICI Bank Ltd",                 "sector": "Banking"},
    {"ticker": "HINDUNILVR",  "company_name": "Hindustan Unilever Ltd",         "sector": "FMCG"},
    {"ticker": "ITC",         "company_name": "ITC Ltd",                        "sector": "FMCG"},
    {"ticker": "SBIN",        "company_name": "State Bank of India",            "sector": "Banking"},
    {"ticker": "BHARTIARTL",  "company_name": "Bharti Airtel Ltd",              "sector": "Telecom"},
    {"ticker": "KOTAKBANK",   "company_name": "Kotak Mahindra Bank",            "sector": "Banking"},
    {"ticker": "LT",          "company_name": "Larsen & Toubro Ltd",            "sector": "Infrastructure"},
    {"ticker": "ASIANPAINT",  "company_name": "Asian Paints Ltd",               "sector": "Consumer"},
    {"ticker": "AXISBANK",    "company_name": "Axis Bank Ltd",                  "sector": "Banking"},
    {"ticker": "BAJFINANCE",  "company_name": "Bajaj Finance Ltd",              "sector": "NBFC"},
    {"ticker": "MARUTI",      "company_name": "Maruti Suzuki India Ltd",        "sector": "Auto"},
    {"ticker": "SUNPHARMA",   "company_name": "Sun Pharmaceutical Industries",  "sector": "Pharma"},
    {"ticker": "TITAN",       "company_name": "Titan Company Ltd",              "sector": "Consumer"},
    {"ticker": "ADANIENT",    "company_name": "Adani Enterprises Ltd",          "sector": "Conglomerate"},
    {"ticker": "BAJAJFINSV",  "company_name": "Bajaj Finserv Ltd",             "sector": "NBFC"},
    {"ticker": "WIPRO",       "company_name": "Wipro Ltd",                      "sector": "IT"},
    {"ticker": "ULTRACEMCO",  "company_name": "UltraTech Cement Ltd",           "sector": "Cement"},
    {"ticker": "TATAMOTORS",  "company_name": "Tata Motors Ltd",                "sector": "Auto"},
    {"ticker": "NTPC",        "company_name": "NTPC Ltd",                       "sector": "Power"},
    {"ticker": "ONGC",        "company_name": "Oil & Natural Gas Corp",         "sector": "Oil & Gas"},
    {"ticker": "POWERGRID",   "company_name": "Power Grid Corp of India",       "sector": "Power"},
    {"ticker": "M&M",         "company_name": "Mahindra & Mahindra Ltd",        "sector": "Auto"},
    {"ticker": "HCLTECH",     "company_name": "HCL Technologies Ltd",           "sector": "IT"},
    {"ticker": "TATASTEEL",   "company_name": "Tata Steel Ltd",                 "sector": "Steel"},
    {"ticker": "TECHM",       "company_name": "Tech Mahindra Ltd",              "sector": "IT"},
    {"ticker": "JSWSTEEL",    "company_name": "JSW Steel Ltd",                  "sector": "Steel"},
    {"ticker": "TATACONSUM",  "company_name": "Tata Consumer Products",         "sector": "FMCG"},
    {"ticker": "INDUSINDBK",  "company_name": "IndusInd Bank Ltd",              "sector": "Banking"},
    {"ticker": "HINDALCO",    "company_name": "Hindalco Industries Ltd",        "sector": "Metals"},
    {"ticker": "COALINDIA",   "company_name": "Coal India Ltd",                 "sector": "Mining"},
    {"ticker": "GRASIM",      "company_name": "Grasim Industries Ltd",          "sector": "Cement"},
    {"ticker": "BAJAJ-AUTO",  "company_name": "Bajaj Auto Ltd",                 "sector": "Auto"},
    {"ticker": "DRREDDY",     "company_name": "Dr. Reddy's Laboratories",       "sector": "Pharma"},
    {"ticker": "CIPLA",       "company_name": "Cipla Ltd",                      "sector": "Pharma"},
    {"ticker": "APOLLOHOSP",  "company_name": "Apollo Hospitals Enterprise",    "sector": "Healthcare"},
    {"ticker": "HEROMOTOCO",  "company_name": "Hero MotoCorp Ltd",              "sector": "Auto"},
    {"ticker": "EICHERMOT",   "company_name": "Eicher Motors Ltd",              "sector": "Auto"},
    {"ticker": "BRITANNIA",   "company_name": "Britannia Industries",           "sector": "FMCG"},
    {"ticker": "DIVISLAB",    "company_name": "Divi's Laboratories Ltd",        "sector": "Pharma"},
    {"ticker": "TRENT",       "company_name": "Trent Ltd",                      "sector": "Retail"},
    {"ticker": "NESTLEIND",   "company_name": "Nestle India Ltd",               "sector": "FMCG"},
    {"ticker": "SBILIFE",     "company_name": "SBI Life Insurance Company",     "sector": "Insurance"},
    {"ticker": "HDFCLIFE",    "company_name": "HDFC Life Insurance Company",    "sector": "Insurance"},
    {"ticker": "BPCL",        "company_name": "Bharat Petroleum Corp Ltd",      "sector": "Oil & Gas"},
    {"ticker": "TATACHEM",    "company_name": "Tata Chemicals Ltd",             "sector": "Chemicals"},
    {"ticker": "HINDPETRO",   "company_name": "Hindustan Petroleum Corp Ltd",   "sector": "Oil & Gas"},
    {"ticker": "GAIL",        "company_name": "GAIL (India) Ltd",               "sector": "Oil & Gas"},
    {"ticker": "ADANIPORTS",  "company_name": "Adani Ports & SEZ Ltd",          "sector": "Infrastructure"},
    {"ticker": "VEDL",        "company_name": "Vedanta Ltd",                    "sector": "Metals"},
    {"ticker": "DABUR",       "company_name": "Dabur India Ltd",                "sector": "FMCG"},
    {"ticker": "MARICO",      "company_name": "Marico Ltd",                     "sector": "FMCG"},
    {"ticker": "PIDILITIND",  "company_name": "Pidilite Industries Ltd",        "sector": "Chemicals"},
    {"ticker": "ACC",         "company_name": "ACC Ltd",                        "sector": "Cement"},
    {"ticker": "AMBUJACEM",   "company_name": "Ambuja Cements Ltd",             "sector": "Cement"},
    {"ticker": "UBL",         "company_name": "United Breweries Ltd",           "sector": "FMCG"},
    {"ticker": "COLPAL",      "company_name": "Colgate-Palmolive India",        "sector": "FMCG"},
    {"ticker": "MCDOWELL-N",  "company_name": "United Spirits Ltd",             "sector": "FMCG"},
    {"ticker": "PGHH",        "company_name": "Procter & Gamble Health",        "sector": "Pharma"},
    {"ticker": "VBL",         "company_name": "Varun Beverages Ltd",            "sector": "FMCG"},
    {"ticker": "BRITANNIA",   "company_name": "Britannia Industries",           "sector": "FMCG"},
    {"ticker": "DABUR",       "company_name": "Dabur India Ltd",                "sector": "FMCG"},
    {"ticker": "MARICO",      "company_name": "Marico Ltd",                     "sector": "FMCG"},
    {"ticker": "COLPAL",      "company_name": "Colgate-Palmolive India",        "sector": "FMCG"},
    {"ticker": "GODREJCP",    "company_name": "Godrej Consumer Products",       "sector": "FMCG"},
    {"ticker": "AWL",         "company_name": "Adani Wilmar",                   "sector": "FMCG"},
    {"ticker": "PATANJALI",   "company_name": "Patanjali Foods",                "sector": "FMCG"},
    {"ticker": "BIKAJI",      "company_name": "Bikaji Foods",                   "sector": "FMCG"},
    {"ticker": "TRENT",       "company_name": "Trent Ltd",                      "sector": "Retail"},
    {"ticker": "KALYANKJIL",  "company_name": "Kalyan Jewellers",               "sector": "Consumer"},
    {"ticker": "TITAN",       "company_name": "Titan Company Ltd",              "sector": "Consumer"},
    {"ticker": "MANYAVAR",    "company_name": "Vedant Fashions",                "sector": "Retail"},
    {"ticker": "METROBRAND",  "company_name": "Metro Brands",                   "sector": "Retail"},
    {"ticker": "ESCORTS",     "company_name": "Escorts Kubota Ltd",             "sector": "Auto"},
    {"ticker": "ASHOKLEY",    "company_name": "Ashok Leyland Ltd",              "sector": "Auto"},
    {"ticker": "TVSMOTOR",    "company_name": "TVS Motor Company",              "sector": "Auto"},
    {"ticker": "MRF",         "company_name": "MRF Ltd",                        "sector": "Tyres"},
    {"ticker": "APOLLOTYRE",  "company_name": "Apollo Tyres Ltd",               "sector": "Tyres"},
    {"ticker": "BALKRISIND",  "company_name": "Balkrishna Industries",          "sector": "Tyres"},
    {"ticker": "CEATLTD",     "company_name": "CEAT Ltd",                       "sector": "Tyres"},
    {"ticker": "BHARATFORG",  "company_name": "Bharat Forge Ltd",               "sector": "Auto Ancillary"},
    {"ticker": "BOSCHLTD",    "company_name": "Bosch Ltd",                      "sector": "Auto Ancillary"},
    {"ticker": "MOTHERSON",   "company_name": "Samvardhana Motherson",          "sector": "Auto Ancillary"},
    {"ticker": "SONACOMS",    "company_name": "Sona BLW Precision",             "sector": "Auto Ancillary"},
    {"ticker": "UNOMINDA",    "company_name": "Uno Minda Ltd",                  "sector": "Auto Ancillary"},
    {"ticker": "DLF",         "company_name": "DLF Ltd",                        "sector": "Real Estate"},
    {"ticker": "GODREJPROP",  "company_name": "Godrej Properties",              "sector": "Real Estate"},
    {"ticker": "OBEROIRLTY",  "company_name": "Oberoi Realty Ltd",              "sector": "Real Estate"},
    {"ticker": "LODHA",       "company_name": "Macrotech Developers",           "sector": "Real Estate"},
    {"ticker": "PRESTIGE",    "company_name": "Prestige Estate",                "sector": "Real Estate"},
    {"ticker": "PHOENIXLTD",  "company_name": "Phoenix Mills Ltd",              "sector": "Real Estate"},
    {"ticker": "BRIGADE",     "company_name": "Brigade Enterprises",            "sector": "Real Estate"},
    {"ticker": "NYKAA",       "company_name": "FSN E-Commerce (Nykaa)",         "sector": "Consumer Tech"},
    {"ticker": "PAYTM",       "company_name": "One 97 Communications",          "sector": "Consumer Tech"},
    {"ticker": "POLICYBZR",   "company_name": "PB Fintech (PolicyBazaar)",      "sector": "Consumer Tech"},
    {"ticker": "DELHIVERY",   "company_name": "Delhivery Ltd",                  "sector": "Logistics"},
    {"ticker": "ZEEL",        "company_name": "Zee Entertainment",              "sector": "Media"},
    {"ticker": "SUNTV",       "company_name": "Sun TV Network Ltd",             "sector": "Media"},
    {"ticker": "SHREECEM",    "company_name": "Shree Cement Ltd",               "sector": "Cement"},
    {"ticker": "ACC",         "company_name": "ACC Ltd",                        "sector": "Cement"},
    {"ticker": "AMBUJACEM",   "company_name": "Ambuja Cements Ltd",             "sector": "Cement"},
    {"ticker": "DALBHARAT",   "company_name": "Dalmia Bharat Ltd",              "sector": "Cement"},
    {"ticker": "JKCEMENT",    "company_name": "JK Cement Ltd",                  "sector": "Cement"},
    {"ticker": "RAMCOCEM",    "company_name": "Ramco Cements",                  "sector": "Cement"},
    {"ticker": "SAIL",        "company_name": "Steel Authority of India",       "sector": "Steel"},
    {"ticker": "HINDZINC",    "company_name": "Hindustan Zinc Ltd",             "sector": "Metals"},
    {"ticker": "NMDC",        "company_name": "NMDC Ltd",                       "sector": "Mining"},
    {"ticker": "HAVELLS",     "company_name": "Havells India Ltd",              "sector": "Consumer Durables"},
    {"ticker": "VOLTAS",      "company_name": "Voltas Ltd",                     "sector": "Consumer Durables"},
    {"ticker": "DIXON",       "company_name": "Dixon Technologies",             "sector": "Consumer Durables"},
    {"ticker": "BLUESTARCO",  "company_name": "Blue Star Ltd",                  "sector": "Consumer Durables"},
    {"ticker": "WHIRLPOOL",   "company_name": "Whirlpool of India",             "sector": "Consumer Durables"},
    {"ticker": "INDHOTEL",    "company_name": "Indian Hotels Co Ltd",           "sector": "Hotels"},
    {"ticker": "EIHOTEL",     "company_name": "EIH Ltd (Oberoi Hotels)",        "sector": "Hotels"},
    {"ticker": "LEMONTREE",   "company_name": "Lemon Tree Hotels",              "sector": "Hotels"},
    {"ticker": "COROMANDEL",  "company_name": "Coromandel International",       "sector": "Fertilizers"},
    {"ticker": "CHAMBLFERT",  "company_name": "Chambal Fertilizers",            "sector": "Fertilizers"},
    {"ticker": "DEEPAKFERT",  "company_name": "Deepak Fertilisers",             "sector": "Fertilizers"},
    {"ticker": "NAUKRI",      "company_name": "Info Edge (Naukri)",             "sector": "IT"},
    {"ticker": "ZOMATO",      "company_name": "Zomato Ltd",                     "sector": "Consumer Tech"},
    {"ticker": "SWIGGY",      "company_name": "Bundl Technologies (Swiggy)",    "sector": "Consumer Tech"},
    {"ticker": "IXIGO",       "company_name": "Le Travenues Technology (ixigo)","sector": "Consumer Tech"},
    {"ticker": "KAYNES",      "company_name": "Kaynes Technology",              "sector": "Engineering"},
    {"ticker": "SYRMA",       "company_name": "Syrma SGS Technology",           "sector": "Engineering"},
    {"ticker": "AVALON",      "company_name": "Avalon Technologies",            "sector": "Engineering"},
    {"ticker": "DOMS",        "company_name": "DOMS Industries",                "sector": "Consumer"},
    {"ticker": "VARUN",       "company_name": "Varun Beverages Ltd",            "sector": "FMCG"},
    {"ticker": "PVRINOX",     "company_name": "PVR INOX Ltd",                   "sector": "Media"},
    {"ticker": "INOXWIND",    "company_name": "Inox Wind Ltd",                  "sector": "Renewable Energy"},
    {"ticker": "WAAREEENER",  "company_name": "Waaree Energies",                "sector": "Renewable Energy"},
    {"ticker": "PREMIERENE",  "company_name": "Premier Energies",               "sector": "Renewable Energy"},
]

# Pre-process for fast search: lowercase index
# Deduplicate by ticker (JSON load may have no dupes, but legacy fallback might)
_seen_tickers: set = set()
_NSE_DIR_INDEX = []
for e in _NSE_DIRECTORY:
    _tk = e["ticker"]
    if _tk in _seen_tickers:
        continue
    _seen_tickers.add(_tk)
    _NSE_DIR_INDEX.append({
        "ticker": _tk,
        "company_name": e["company_name"],
        "sector": e["sector"],
        "exchange": e.get("exchange", "NSE"),
        "_t": _tk.lower(),
        "_n": e["company_name"].lower(),
        "_s": e["sector"].lower(),
    })
del _seen_tickers


@router.get("/search")
def search_endpoint(q: str = "", limit: int = 20):
    """
    Fast in-memory NSE stock search. No yfinance, no DB. Returns in <5ms.

    Args:
        q (str): The q.
        limit (int): The limit.

    Returns:
        Any: The response.
    """
    q = q.strip()
    if not q:
        return []
    ql = q.lower()
    prefix: list[dict] = []
    contains: list[dict] = []
    for e in _NSE_DIR_INDEX:
        if e["_t"].startswith(ql) or e["_n"].startswith(ql):
            prefix.append(e)
        elif ql in e["_t"] or ql in e["_n"] or ql in e["_s"]:
            contains.append(e)
    results = prefix + contains
    return [
        {"ticker": r["ticker"], "company_name": r["company_name"],
         "sector": r["sector"], "exchange": r["exchange"]}
        for r in results[:limit]
    ]


# Upcoming IPOs (manually tracked)
UPCOMING_IPOS = [
    {"company": "Swiggy Ltd", "open_date": "TBD 2026", "price_band": "₹371-390"},
    {"company": "Bajaj Housing Finance", "open_date": "TBD 2026", "price_band": "₹66-70"},
    {"company": "Hyundai India", "open_date": "TBD 2026", "price_band": "₹1865-1960"},
]

SECTOR_TICKERS = [
    ("^CNXPSUBANK",  "PSU Bank"),
    ("^CNXFMCG",     "FMCG"),
    ("^CNXIT",       "IT"),
    ("^CNXPHARMA",   "Pharma"),
    ("^CNXAUTO",     "Auto"),
    ("^CNXREALTY",   "Realty"),
    ("^CNXENERGY",   "Energy"),
    ("^CNXMETAL",    "Metal"),
]

_sector_cache: dict = {"data": None, "ts": 0.0}


@router.get("/sector-performance")
def sector_performance_endpoint():
    global _sector_cache
    now = time.time()
    if _sector_cache["data"] and now - _sector_cache["ts"] < 600:
        return _sector_cache["data"]

    def _as_finite_float(value):
        if isinstance(value, bool):
            return None
        if not isinstance(value, (int, float)):
            return None
        value = float(value)
        return value if math.isfinite(value) else None

    sectors = []
    import math
    for ticker, name in SECTOR_TICKERS:
        try:
            current = None
            prev = None
            for attempt in range(3):
                try:
                    t = yf.Ticker(ticker)
                    info = t.fast_info if hasattr(t, "fast_info") else {}
                    current = _as_finite_float(getattr(info, "last_price", None)) or _as_finite_float((t.info or {}).get("regularMarketPrice"))
                    prev    = _as_finite_float(getattr(info, "previous_close", None)) or _as_finite_float((t.info or {}).get("previousClose"))

                    if current is None:
                        # Fallback: History
                        hist = t.history(period="5d")
                        if not hist.empty and len(hist) >= 2:
                            current = float(hist["Close"].iloc[-1])
                            prev = float(hist["Close"].iloc[-2])

                    if current is not None:
                        break
                except Exception as e:
                    logging.info(f"[YF] Sector perf attempt {attempt+1} failed for {ticker}: {e}")
                    if attempt < 2:
                        time.sleep((1.0 * (2 ** attempt)) + (random.random() * 0.2))

            current = _as_finite_float(current)
            prev = _as_finite_float(prev)
            if current is None or prev is None or prev == 0:
                continue
            change_abs = round(current - prev, 2)
            change_pct = round((change_abs / prev) * 100, 2)
            sectors.append({
                "name": name,
                "ticker": ticker,
                "value": round(current, 2),
                "change_abs": change_abs,
                "change_pct": change_pct,
            })
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            continue

    result = {
        "sectors": sorted(sectors, key=lambda x: abs(x["change_pct"]), reverse=True),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _sector_cache = {"data": result, "ts": now}
    return result


# ---------------------------------------------------------------------------
# v1 Market Intelligence Routes (Firecrawl + fallback scraping, 15-min cache)
# ---------------------------------------------------------------------------

@router.get("/api/v1/market/pulse")
def market_pulse_endpoint():
    """
    Market indices + advance/decline breadth ratio.

    Args:

    Returns:
        Any: The response.
    """
    try:
        return fetch_market_pulse()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market pulse unavailable: {e}")

@router.get("/api/v1/market/momentum")
def market_momentum_endpoint():
    """
    Bullish/bearish MA crossover lists with sparkline coordinate arrays.

    Args:

    Returns:
        Any: The response.
    """
    try:
        return fetch_momentum()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Momentum data unavailable: {e}")

@router.get("/api/v1/market/macro-alternatives")
def market_macro_alternatives_endpoint():
    """
    Brent, Gold, USD/INR, US 10Y, India VIX, ETFs.

    Args:

    Returns:
        Any: The response.
    """
    try:
        return fetch_macro_alternatives()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Macro data unavailable: {e}")

@router.get("/api/v1/market/institutional-flow")
def market_institutional_flow_endpoint():
    """
    Top 10 mutual funds by 1-year return (leaderboard).

    Args:

    Returns:
        Any: The response.
    """
    try:
        return fetch_institutional_flow()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Institutional flow unavailable: {e}")


@router.get("/api/v1/market/stock-history")
def stock_history_endpoint(ticker: str, exchange: str = "NSE", period: str = "1y"):
    """
    OHLCV price history for a stock. period: 1mo,3mo,6mo,1y,2y,5y

    Args:
        ticker (str): The ticker.
        exchange (str): The exchange.
        period (str): The period.

    Returns:
        Any: The response.
    """
    try:
        cache_key = f"{ticker}_{exchange}_{period}"
        cached = _dcache_get("stock_history", cache_key)
        if cached:
            return cached

        period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650}
        days = period_map.get(period, 365)

        df = get_price_history(ticker.upper(), period_days=days, exchange=exchange.upper())
        if df is None or df.empty:
            return {"ticker": ticker, "exchange": exchange, "period": period, "prices": []}

        import math as _m_stock
        prices = []
        for dt, row in df.iterrows():
            o = float(row["Open"]); h = float(row["High"]); l = float(row["Low"])
            c = float(row["Close"]); v = float(row.get("Volume", 0) or 0)
            prices.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(o, 2) if not (_m_stock.isnan(o) or _m_stock.isinf(o)) else 0,
                "high": round(h, 2) if not (_m_stock.isnan(h) or _m_stock.isinf(h)) else 0,
                "low": round(l, 2) if not (_m_stock.isnan(l) or _m_stock.isinf(l)) else 0,
                "close": round(c, 2) if not (_m_stock.isnan(c) or _m_stock.isinf(c)) else 0,
                "volume": v if not (_m_stock.isnan(v) or _m_stock.isinf(v)) else 0,
            })

        result = {"ticker": ticker, "exchange": exchange, "period": period, "prices": prices}
        _dcache_set("stock_history", cache_key, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════════════════════════
# Stock Profile — unified endpoint for iOS StockProfileView
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/v1/stock-profile")
def stock_profile_endpoint(ticker: str, exchange: str = "NSE"):
    """
    All data needed for StockProfileView in a single call.
Returns HTTP 200 on partial failures — errors array explains what's missing.

    Args:
        ticker (str): The ticker.
        exchange (str): The exchange.

    Returns:
        Any: The response.
    """
    import math
    
    cache_key = f"profile_{ticker.upper()}_{exchange.upper()}"
    cached = _dcache_get("market", cache_key)
    if cached is not None:
        return cached
    
    errors: list[str] = []
    full_ticker = _resolve_ticker(ticker, exchange)

    # ── 1. Company overview from yfinance ──────────────────────────────────
    company_name = None
    current_price = None
    day_change_pct = None
    pe_ratio = None
    sector = None
    promoter_holding_pct = None
    fii_holding_pct = None
    dii_holding_pct = None
    roe_pct = None
    roce_pct = None
    ebitda_margin_pct = None
    debt_to_equity = None
    week_52_high = None
    week_52_low = None
    market_cap_crores = None
    description = None

    try:
        info = _yf_fetch_info(full_ticker)
        if not info:
            raise Exception("yfinance returned empty info dict after 3 retries")

        company_name = info.get("longName")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

        if current_price and prev_close and float(prev_close) > 0:
            day_change_pct = round(
                ((float(current_price) - float(prev_close)) / float(prev_close)) * 100, 2
            )

        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        sector = info.get("sector")

        # Holdings — yfinance stores as decimal (0.452 = 45.2%)
        raw_promoter = info.get("heldPercentInsiders")
        if raw_promoter is not None:
            promoter_holding_pct = round(float(raw_promoter) * 100, 2)

        # heldPercentInstitutions = total institutional (FII + DII combined).
        # Store it separately so we can derive FII = institutional - DII later
        # instead of misreporting the full institutional as FII alone (#256/#306).
        raw_inst = info.get("heldPercentInstitutions")
        _institutional_total_pct: float | None = None
        if raw_inst is not None:
            _institutional_total_pct = round(float(raw_inst) * 100, 2)
            fii_holding_pct = _institutional_total_pct  # provisional; revised below

        # Profitability — yfinance returns decimal (0.152 = 15.2%)
        roe = info.get("returnOnEquity")
        if roe is not None:
            roe_pct = round(float(roe) * 100, 2) if float(roe) < 10 else round(float(roe), 2)

        roce = info.get("returnOnCapitalEmployed")
        if roce is not None:
            roce_pct = round(float(roce) * 100, 2) if float(roce) < 10 else round(float(roce), 2)

        # EBITDA margin — compute from ebitda / totalRevenue
        ebitda = info.get("ebitda")
        total_revenue = info.get("totalRevenue")
        if ebitda and total_revenue and float(total_revenue) > 0:
            ebitda_margin_pct = round((float(ebitda) / float(total_revenue)) * 100, 2)

        debt_to_equity = info.get("debtToEquity")
        week_52_high = info.get("fiftyTwoWeekHigh")
        week_52_low = info.get("fiftyTwoWeekLow")

        mcap = info.get("marketCap")
        if mcap is not None:
            market_cap_crores = round(float(mcap) / 1e7, 2)

        description = info.get("longBusinessSummary")

        if current_price is None:
            raise Exception(f"yfinance info missing currentPrice for {full_ticker}")

    except Exception as e:
        errors.append("company_info_unavailable")

    # ── Supplement holdings from fundamentals provider ─────────────────────
    try:
        fund = get_fundamentals(ticker, exchange)
        if fund:
            fund_fii = fund.get("fii_holding_pct")
            fund_dii = fund.get("dii_holding_pct")
            if fund_fii:
                fii_holding_pct = fund_fii
            if fund_dii:
                dii_holding_pct = fund_dii
                # If fundamentals gave DII but not FII and we only have the
                # yfinance institutional total (FII+DII combined), derive FII
                # so FII + DII = institutional_total, not 135%+ (#256/#306).
                if not fund_fii and _institutional_total_pct is not None:
                    fii_holding_pct = max(0.0, round(_institutional_total_pct - fund_dii, 2))
    except Exception as e:
        import logging
        logging.warning(f"Swallowed exception: {e}")

    # ── 2. Price history — full error capture ──────────────────────────────
    price_history_data: dict = {"prices": [], "source": None, "error": None}

    try:
        df = get_price_history(ticker.upper(), period_days=365, exchange=exchange.upper())
        if df is None or df.empty:
            # Diagnose which source(s) failed and why
            failure_reasons: list[str] = []

            # Probe jugaad-data
            try:
                from services.nse_data_provider import _JUGAAD_AVAILABLE as _j
            except ImportError:
                _j = False

            if not _j:
                failure_reasons.append("jugaad-data: module unavailable at startup")

            # Probe yfinance directly for the real error
            try:
                import yfinance as _yf
                _suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
                _sym = f"{ticker.upper()}{_suffix}"
                _test = _yf.Ticker(_sym)
                _test_hist = _test.history(period="5d")
                if _test_hist is None or _test_hist.empty:
                    failure_reasons.append(f"yfinance: returned empty DataFrame for {_sym}")
            except Exception as _yfe:
                failure_reasons.append(f"yfinance: {type(_yfe).__name__}('{_yfe}')")

            if not failure_reasons:
                failure_reasons.append("unknown: get_price_history returned empty")
            price_history_data["error"] = "; ".join(failure_reasons)
            errors.append("price_history_unavailable")
        else:
            import math as _m_sp
            prices = []
            for dt_val, row in df.iterrows():
                o = float(row["Open"]); h = float(row["High"]); l = float(row["Low"])
                c = float(row["Close"]); v = float(row.get("Volume", 0) or 0)
                prices.append({
                    "date": dt_val.strftime("%Y-%m-%d") if hasattr(dt_val, "strftime") else str(dt_val)[:10],
                    "open": round(o, 2) if not (_m_sp.isnan(o) or _m_sp.isinf(o)) else 0,
                    "high": round(h, 2) if not (_m_sp.isnan(h) or _m_sp.isinf(h)) else 0,
                    "low": round(l, 2) if not (_m_sp.isnan(l) or _m_sp.isinf(l)) else 0,
                    "close": round(c, 2) if not (_m_sp.isnan(c) or _m_sp.isinf(c)) else 0,
                    "volume": v if not (_m_sp.isnan(v) or _m_sp.isinf(v)) else 0,
                })
            price_history_data["prices"] = prices
            try:
                from services.nse_data_provider import _JUGAAD_AVAILABLE as _j2
                price_history_data["source"] = "jugaad-data" if _j2 else "yfinance"
            except ImportError:
                price_history_data["source"] = "yfinance"
    except Exception as e:
        price_history_data["error"] = f"get_price_history: {type(e).__name__}('{e}')"
        errors.append("price_history_unavailable")

    # ── 3. Quarterly financials ────────────────────────────────────────────
    quarterly_data: dict = {"quarters": [], "promoter_history": [], "error": None}

    try:
        t_obj, fin = _get_quarterly_fin(full_ticker)
        if fin is not None and not fin.empty:
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            profit_row = fin.loc["Net Income"] if "Net Income" in fin.index else None
            cols = list(fin.columns)[:8]
            for col in cols:
                label = col.strftime("Q%q %Y") if hasattr(col, "strftime") else str(col)[:7]
                rev = float(rev_row[col]) / 1e7 if rev_row is not None and col in rev_row.index else 0
                profit = float(profit_row[col]) / 1e7 if profit_row is not None and col in profit_row.index else 0
                rev = 0.0 if math.isnan(rev) or math.isinf(rev) else round(rev, 1)
                profit = 0.0 if math.isnan(profit) or math.isinf(profit) else round(profit, 1)
                quarterly_data["quarters"].append({
                    "label": label,
                    "revenue": rev,
                    "net_profit": profit,
                })
        else:
            quarterly_data["error"] = f"_get_quarterly_fin: empty data for {full_ticker}"
            errors.append("quarterly_financials_unavailable")
    except Exception as e:
        quarterly_data["error"] = f"_get_quarterly_fin: {type(e).__name__}('{e}')"
        errors.append("quarterly_financials_unavailable")

    # Promoter/FII/DII holding history from DB (same pattern as quarterly-financials endpoint)
    try:
        from database import get_session as _gs, AnalysisHistory as _AH
        with _gs() as session:
            rows = session.query(_AH).filter(
                _AH.ticker == ticker.upper()
            ).order_by(_AH.created_at.desc()).limit(8).all()
            seen: dict[str, bool] = {}
            for row in rows:
                if row.full_json:
                    try:
                        data = json.loads(row.full_json)
                        fs = data.get("fundamentals_snapshot", {})
                        prom = fs.get("promoter_holding_pct")
                        fii_v = fs.get("fii_holding_pct")
                        dii_v = fs.get("dii_holding_pct")
                        date_key = row.analysis_date[:7] if row.analysis_date else "?"
                        if date_key not in seen and prom is not None:
                            seen[date_key] = True
                            quarterly_data["promoter_history"].append({
                                "period": row.analysis_date,
                                "promoter": prom,
                                "fii": fii_v or 0,
                                "dii": dii_v or 0,
                            })
                    except Exception as e:
                        import logging
                        logging.warning(f"Swallowed exception: {e}")
            quarterly_data["promoter_history"] = list(
                reversed(quarterly_data["promoter_history"][:4])
            )
    except Exception as e:
        import logging
        logging.warning(f"Swallowed exception: {e}")

    # ── 4. Sanitise & assemble ─────────────────────────────────────────────
    def _clean_num(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                return None
        return v

    def _sanitize_for_json(obj):
        """Recursively replace NaN/Inf with 0 so json.dumps never fails."""
        if isinstance(obj, dict):
            return {k: _sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize_for_json(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return 0
        return obj

    result = {
        "ticker": ticker.upper(),
        "exchange": exchange.upper(),
        "company_name": company_name or ticker.upper(),
        "current_price": _clean_num(current_price) or 0,
        "day_change_pct": _clean_num(day_change_pct) or 0,
        "pe_ratio": _clean_num(pe_ratio),
        "sector": sector,
        "promoter_holding_pct": _clean_num(promoter_holding_pct),
        "fii_holding_pct": _clean_num(fii_holding_pct),
        "dii_holding_pct": _clean_num(dii_holding_pct),
        "roe_pct": _clean_num(roe_pct),
        "roce_pct": _clean_num(roce_pct),
        "ebitda_margin_pct": _clean_num(ebitda_margin_pct),
        "debt_to_equity": _clean_num(debt_to_equity),
        "week_52_high": _clean_num(week_52_high),
        "week_52_low": _clean_num(week_52_low),
        "market_cap_crores": _clean_num(market_cap_crores),
        "description": description,
        "price_history": _sanitize_for_json(price_history_data),
        "quarterly_financials": _sanitize_for_json(quarterly_data),
        "errors": errors,
    }

    _dcache_set("market", cache_key, result, ttl=900)
    return result


# ── Pydantic response schemas (must precede endpoints that reference them) ────
from pydantic import BaseModel as _BaseModel
from typing import List as _List, Optional as _Optional

class EarningsSyncRatioResponseLocal(_BaseModel):
    declared_count: int
    total_expected: int
    sync_ratio_pct: float
    fetched_at: str
    source: str

class YoYAggregateResponseLocal(_BaseModel):
    revenue_yoy_pct: float
    net_profit_yoy_pct: float
    companies_reported: int
    fetched_at: str
    source: str


@router.get("/api/v1/earnings/sync-ratio", response_model=EarningsSyncRatioResponseLocal)
async def earnings_sync_ratio_endpoint():
    """
    Real-time tracking metric: total companies that have declared quarterly
results vs total statutory listed exchange obligations (e.g. 4432/5042).
Backed by 15-min in-memory TTL cache.

    Args:

    Returns:
        Any: The response.
    """
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            None, fetch_earnings_sync_ratio
        )
    except DataHarvestingError:
        raise
    except Exception as exc:
        raise DataHarvestingError(str(exc)) from exc

    declared = raw.get("declared_count", 0)
    total = raw.get("total_expected", 5042)
    ratio = round((declared / total) * 100, 1) if total > 0 else 0.0

    return EarningsSyncRatioResponseLocal(
        declared_count=declared,
        total_expected=total,
        sync_ratio_pct=ratio,
        fetched_at=raw.get("fetched_at", ""),
        source=raw.get("source", "unknown"),
    )

@router.get("/api/v1/earnings/yoy-aggregate", response_model=YoYAggregateResponseLocal)
async def yoy_aggregate_endpoint():
    """
    Composite market health: aggregate YoY Revenue and Net Profit
expansion/contraction metrics across NSE-listed companies.
Backed by 15-min in-memory TTL cache.

    Args:

    Returns:
        Any: The response.
    """
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            None, fetch_yoy_aggregate_indicators
        )
    except DataHarvestingError:
        raise
    except Exception as exc:
        raise DataHarvestingError(str(exc)) from exc

    return YoYAggregateResponseLocal(
        revenue_yoy_pct=raw.get("revenue_yoy_pct", 0.0),
        net_profit_yoy_pct=raw.get("net_profit_yoy_pct", 0.0),
        companies_reported=raw.get("companies_reported", 0),
        fetched_at=raw.get("fetched_at", ""),
        source=raw.get("source", "unknown"),
    )


# ---------------------------------------------------------------------------
# Unified dashboard endpoint — returns all 4 market intelligence feeds in one
# call. Fetchers are cached (15-min TTL) so this is fast after first load.
# ---------------------------------------------------------------------------

from datetime import datetime as _dt
import concurrent.futures as _cf

# ── Pydantic response schemas ────────────────────────────────────────────────

class IndexSnapshot(_BaseModel):
    name: str
    value: _Optional[float]
    change_pct: _Optional[float]
    change_abs: _Optional[float]

class BreadthData(_BaseModel):
    advances: _Optional[int]
    declines: _Optional[int]
    unchanged: _Optional[int]
    ad_ratio: _Optional[float]

class MomentumSignal(_BaseModel):
    ticker: str
    signal: str          # "GOLDEN_CROSS" | "DEATH_CROSS"
    dma_50: _Optional[float]
    dma_200: _Optional[float]
    score: _Optional[float]

class DashboardPulseResponse(_BaseModel):
    indices: _List[IndexSnapshot]
    breadth: _Optional[BreadthData]
    momentum_signals: _List[MomentumSignal]
    fetched_at: str

class MutualFundEntry(_BaseModel):
    fund_name: str
    amc: _Optional[str]
    return_1y_pct: _Optional[float]
    return_3y_pct: _Optional[float]
    aum_crores: _Optional[float]
    category: _Optional[str]

class InstitutionalLeaderboardResponseLocal(_BaseModel):
    top_funds: _List[MutualFundEntry]
    fetched_at: str

class NetWorthSnapshotResponseLocal(_BaseModel):
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


# ── /api/v1/market/dashboard ─────────────────────────────────────────────────

@router.get("/api/v1/market/dashboard")
def market_dashboard_endpoint():
    """
    All four market intelligence feeds in a single round-trip.

    Args:

    Returns:
        Any: The response.
    """
    try:
        with _cf.ThreadPoolExecutor(max_workers=4) as ex:
            fp = ex.submit(fetch_market_pulse)
            fm = ex.submit(fetch_momentum)
            fa = ex.submit(fetch_macro_alternatives)
            fi = ex.submit(fetch_institutional_flow)
            return {
                "pulse":         fp.result(timeout=25),
                "momentum":      fm.result(timeout=25),
                "macro":         fa.result(timeout=25),
                "institutional": fi.result(timeout=25),
                "fetched_at":    _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dashboard fetch failed: {e}")


# ── /api/v1/market/dashboard-pulse ───────────────────────────────────────────

@router.get("/api/v1/market/dashboard-pulse")
async def dashboard_pulse_endpoint():
    """
    Unified market dashboard — returns full iOS MarketDashboardResponse shape:
{ pulse, momentum: {bullish, bearish}, live_reporting_sync,
  yoy_market_health, cap_index_aggregator, fetched_at }

All value strings use Indian numbering (Lakhs/Crores).
Errors are caught, logged to market_error_logs, and fallback values served.

    Args:

    Returns:
        Any: The response.
    """
    now_iso = _dt.now(timezone.utc).isoformat()
    pulse_raw: dict = {}
    momentum_raw: dict = {}

    # ── Pulse & Momentum (existing) ──────────────────────────────────────────
    try:
        pulse_raw = await asyncio.get_event_loop().run_in_executor(None, fetch_market_pulse)
    except Exception as exc:
        log_market_error("market_pulse", str(exc))
        logging.info(f"[DASHBOARD-PULSE] pulse fetch error: {exc}")
    try:
        momentum_raw = await asyncio.get_event_loop().run_in_executor(None, fetch_momentum)
    except Exception as exc:
        log_market_error("market_momentum", str(exc))
        logging.info(f"[DASHBOARD-PULSE] momentum fetch error: {exc}")

    raw_breadth = pulse_raw.get("breadth") or {}
    pulse_section = {
        "indices": pulse_raw.get("indices", []),
        "advances": raw_breadth.get("advances", 0) or 0,
        "declines": raw_breadth.get("declines", 0) or 0,
        "unchanged": raw_breadth.get("unchanged", 0) or 0,
        "breadth_ratio": raw_breadth.get("ad_ratio"),
        "fetched_at": now_iso,
    }

    def _ticker_dict(s: dict) -> dict:
        dma50 = float(s.get("dma_50") or 0.0)
        dma200 = float(s.get("dma_200") or 0.0)
        return {
            "ticker": s.get("ticker", ""),
            "last_price": dma50,
            "ma20": dma50,
            "ma50": dma200,
            "sparkline": [],
            "trend_date": now_iso[:10],
            "crossover": s.get("signal", ""),
        }

    raw_signals = momentum_raw.get("crossovers", []) if isinstance(momentum_raw, dict) else []
    bullish = [_ticker_dict(s) for s in raw_signals if s.get("signal") == "GOLDEN_CROSS"]
    bearish = [_ticker_dict(s) for s in raw_signals if s.get("signal") == "DEATH_CROSS"]

    # No hardcoded fallback — if no real crossover signals exist, return empty lists

    # ── SECTION 1: Live Reporting Sync ───────────────────────────────────────
    live_sync: dict = {"declared_count": 0, "total_expected": 5042,
                        "sync_ratio_pct": 0.0, "source": "fallback", "fetched_at": now_iso}
    try:
        # Primary: filings_extractor counts from NSE corporate filings
        filings_data = await asyncio.get_event_loop().run_in_executor(None, harvest_filings)
        if filings_data:
            declared = filings_data.get("earnings_filings_count", 0)
            live_sync = {
                "declared_count": declared,
                "total_expected": 5042,
                "sync_ratio_pct": round((declared / 5042) * 100, 1) if declared > 0 else 0.0,
                "source": filings_data.get("source", "nse"),
                "fetched_at": now_iso,
            }
    except Exception as exc:
        log_market_error("filings_extractor", str(exc))
        # Fallback: scraper's firecrawl-based sync ratio
        try:
            sync_raw = await asyncio.get_event_loop().run_in_executor(None, fetch_earnings_sync_ratio)
            if sync_raw:
                live_sync = {
                    "declared_count": sync_raw.get("declared_count", 0),
                    "total_expected": sync_raw.get("total_expected", 5042),
                    "sync_ratio_pct": round((sync_raw.get("declared_count", 0) / max(sync_raw.get("total_expected", 5042), 1)) * 100, 1),
                    "source": sync_raw.get("source", "fallback"),
                    "fetched_at": now_iso,
                }
        except Exception as exc2:
            log_market_error("earnings_sync_ratio", str(exc2))

    # ── SECTION 2: YoY Market Health ─────────────────────────────────────────
    yoy_health: dict = {"revenue_yoy_pct": 0.0, "net_profit_yoy_pct": 0.0,
                         "companies_reported": 0, "source": "fallback", "fetched_at": now_iso}
    try:
        yoy_raw = await asyncio.get_event_loop().run_in_executor(None, fetch_yoy_aggregate_indicators)
        if yoy_raw:
            yoy_health = {
                "revenue_yoy_pct": round(float(yoy_raw.get("revenue_yoy_pct", 0.0)), 2),
                "net_profit_yoy_pct": round(float(yoy_raw.get("net_profit_yoy_pct", 0.0)), 2),
                "companies_reported": int(yoy_raw.get("companies_reported", 0)),
                "source": yoy_raw.get("source", "unknown"),
                "fetched_at": now_iso,
            }
    except Exception as exc:
        log_market_error("yoy_aggregate", str(exc))

    # ── SECTION 3: Cap Index Aggregator ──────────────────────────────────────
    cap_grid: list[dict] = []
    try:
        cap_grid = await asyncio.get_event_loop().run_in_executor(
            None, _build_cap_index_grid
        )
    except Exception as exc:
        log_market_error("cap_index_aggregator", str(exc))

    return {
        "pulse": pulse_section,
        "momentum": {"bullish": bullish, "bearish": bearish, "fetched_at": now_iso},
        "live_reporting_sync": live_sync,
        "yoy_market_health": yoy_health,
        "cap_index_aggregator": cap_grid,
        "fetched_at": now_iso,
    }


# ── Cap Index Aggregator Helper ────────────────────────────────────────────────

# TTL cache — cap weights change slowly, recompute every 6 hours
_cap_grid_cache: dict = {"data": None, "ts": 0.0}
_CAP_GRID_TTL = 21600  # 6 hours

# Index constituent tickers by cap bracket — representative sample per index
_CAP_INDEX_MAP: dict[str, list[str]] = {
    "NIFTY_50": ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
                 "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
                 "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA",
                 "TATAMOTORS", "WIPRO", "ULTRACEMCO"],
    "LARGE_CAP": ["ADANIENT", "ADANIPORTS", "TECHM", "BAJAJFINSV", "INDUSINDBK",
                   "GRASIM", "CIPLA", "DRREDDY", "EICHERMOT", "APOLLOHOSP"],
    "MID_CAP": ["COALINDIA", "DIVISLAB", "BRITANNIA", "HEROMOTOCO", "SBILIFE",
                 "HDFCLIFE", "TATACONSUM", "HINDALCO", "BPCL", "DLF"],
    "SMALL_CAP": ["TRENT", "POLYCAB", "HAL", "APOLLO", "CDSL", "BSE", "KIMS",
                   "FORTIS", "MAXHEALTH", "RAINBOW"],
}


def _build_cap_index_grid() -> list[dict]:
    """
    Build multi-period financial grid sliced by cap weight brackets.
    6-hour TTL cache — cap weights don't change intraday.

    Uses parallel ThreadPoolExecutor for yfinance calls (8 workers).
    Falls back to cached data if yfinance completely fails.
    """
    import math
    import concurrent.futures

    # Return cached grid if fresh
    now = time.time()
    if _cap_grid_cache["data"] is not None and (now - _cap_grid_cache["ts"]) < _CAP_GRID_TTL:
        return _cap_grid_cache["data"]

    brackets: list[dict] = [
        {"cap_bracket": "All",       "source_keys": ["NIFTY_50", "LARGE_CAP", "MID_CAP", "SMALL_CAP"]},
        {"cap_bracket": "Nifty 50",  "source_keys": ["NIFTY_50"]},
        {"cap_bracket": "Large Cap", "source_keys": ["LARGE_CAP"]},
        {"cap_bracket": "Mid Cap",   "source_keys": ["MID_CAP"]},
        {"cap_bracket": "Small Cap", "source_keys": ["SMALL_CAP"]},
    ]

    # Collect all unique tickers
    all_tickers: list[str] = []
    for bracket in brackets:
        for key in bracket["source_keys"]:
            for t in _CAP_INDEX_MAP.get(key, []):
                if t not in all_tickers:
                    all_tickers.append(t)

    # Fetch all ticker info in parallel (8 workers, single attempt — no retries)
    ticker_data: dict[str, dict] = {}

    def _fetch_one(ticker: str) -> tuple[str, dict | None]:
        try:
            import yfinance as yf
            ns = _to_ns(ticker)
            info = yf.Ticker(ns).info
            return (ticker, info if info and info.get("regularMarketPrice") else None)
        except Exception as e:
            import logging
            logging.warning(f"Caught exception: {e}")
            return (ticker, None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in all_tickers}
        for fut in concurrent.futures.as_completed(futures, timeout=30):
            try:
                ticker, info = fut.result()
                if info:
                    ticker_data[ticker] = info
            except Exception as e:
                import logging
                logging.warning(f"Swallowed exception: {e}")

    results: list[dict] = []
    for bracket in brackets:
        tickers: list[str] = []
        for key in bracket["source_keys"]:
            for t in _CAP_INDEX_MAP.get(key, []):
                if t not in tickers:
                    tickers.append(t)

        market_caps: list[float] = []
        revenues: list[float] = []
        profits: list[float] = []
        pe_ratios: list[float] = []
        rev_yoy_list: list[float] = []

        for ticker in tickers:
            info = ticker_data.get(ticker)
            if not info:
                continue
            try:
                mc = info.get("marketCap")
                rev = info.get("totalRevenue")
                profit = info.get("netIncomeToCommon") or info.get("netIncome")
                pe = info.get("trailingPE")
                rev_growth = info.get("revenueGrowth")
                if rev_growth is not None:
                    rev_growth = float(rev_growth) * 100

                if mc and not math.isnan(float(mc)):
                    market_caps.append(float(mc))
                if rev and not math.isnan(float(rev)):
                    revenues.append(float(rev))
                if profit and not math.isnan(float(profit)):
                    profits.append(float(profit))
                if pe and not math.isnan(float(pe)) and float(pe) > 0:
                    pe_ratios.append(float(pe))
                if rev_growth is not None and not math.isnan(rev_growth):
                    rev_yoy_list.append(rev_growth)
            except Exception as e:
                import logging
                logging.warning(f"Caught exception: {e}")
                continue

        count = len(tickers)
        avg_mc = sum(market_caps) / len(market_caps) if market_caps else 0.0
        avg_rev = sum(revenues) / len(revenues) if revenues else 0.0
        avg_profit = sum(profits) / len(profits) if profits else 0.0
        avg_pe = round(sum(pe_ratios) / len(pe_ratios), 1) if pe_ratios else None
        avg_rev_yoy = round(sum(rev_yoy_list) / len(rev_yoy_list), 2) if rev_yoy_list else None

        results.append({
            "cap_bracket": bracket["cap_bracket"],
            "ticker_count": count,
            "avg_market_cap_cr": _fmt_inr_crores(avg_mc),
            "avg_revenue_cr": _fmt_inr_crores(avg_rev),
            "avg_net_profit_cr": _fmt_inr_crores(avg_profit),
            "avg_pe_ratio": avg_pe,
            "avg_revenue_yoy_pct": avg_rev_yoy,
        })

    # Cache the result
    if results and any(r["avg_market_cap_cr"] != "₹0" for r in results):
        _cap_grid_cache["data"] = results
        _cap_grid_cache["ts"] = now
    elif _cap_grid_cache["data"] is not None:
        # yfinance failed completely — return stale cache rather than empty
        return _cap_grid_cache["data"]

    return results


# ── /api/v1/admin/error-logs ──────────────────────────────────────────────────

@router.get("/api/v1/admin/error-logs")
def admin_error_logs_endpoint(limit: int = 50, authorization: str = Header(None)):
    """
    Admin diagnostic endpoint — returns recent market_error_logs entries
as a clean JSON stream for iOS console debugging. Requires admin auth.

    Args:
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import require_admin
    require_admin(authorization)
    try:
        with get_session() as session:
            rows = (
                session.query(MarketErrorLog)
                .order_by(MarketErrorLog.timestamp.desc())
                .limit(min(limit, 200))
                .all()
            )
            return {
                "errors": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "component": r.component,
                        "error_message": r.error_message,
                        "context_ticker": r.context_ticker,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error log query failed: {e}")


# ── /api/v1/market/institutional-leaderboard ─────────────────────────────────

@router.get("/api/v1/market/institutional-leaderboard", response_model=InstitutionalLeaderboardResponseLocal)
async def institutional_leaderboard_endpoint():
    """
    Top-performing mutual funds sorted by 1-year return.
Proxies DII floor support intelligence. 15-min TTL cache.
Raises 503 on DataHarvestingError.

    Args:

    Returns:
        Any: The response.
    """
    try:
        raw = await asyncio.get_event_loop().run_in_executor(None, fetch_institutional_flow)
    except DataHarvestingError:
        raise
    except Exception as exc:
        raise DataHarvestingError(str(exc)) from exc

    raw_funds = raw.get("top_funds", []) if isinstance(raw, dict) else []
    funds = [
        MutualFundEntry(
            fund_name=f.get("fund_name", f.get("name", "")),
            amc=f.get("amc"),
            return_1y_pct=f.get("return_1y_pct", f.get("1y_return")),
            return_3y_pct=f.get("return_3y_pct", f.get("3y_return")),
            aum_crores=f.get("aum_crores"),
            category=f.get("category"),
        )
        for f in raw_funds
    ]
    # Sort by 1-year return descending (highest alpha first)
    funds.sort(key=lambda f: f.return_1y_pct or 0.0, reverse=True)

    return InstitutionalLeaderboardResponseLocal(
        top_funds=funds,
        fetched_at=_dt.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Earnings Intelligence Endpoints  (/api/v1/earnings/*)
# iOS EarningsDashboardView tabs: Progress | Calendar | Feed | Screeners | Variance | Post-Result
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/v1/earnings/progress")
async def earnings_progress_endpoint():
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_session() as session:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
            rows = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date >= cutoff
            ).all()
            reported = len(set(r.ticker for r in rows))
            rev_vals, prof_vals = [], []
            for r in rows:
                try:
                    fj = json.loads(r.full_json or "{}")
                    fs = fj.get("fundamentals_snapshot", {})
                    rev_g = fs.get("revenue_growth_yoy")
                    prof_g = fs.get("net_profit_growth_yoy")
                    if rev_g is not None and -200 < rev_g < 500:
                        rev_vals.append(rev_g)
                    if prof_g is not None and -200 < prof_g < 500:
                        prof_vals.append(prof_g)
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    continue
        return {
            "reported": reported,
            "total": max(reported, 50),
            "yoy_revenue_growth_pct": round(sum(rev_vals) / len(rev_vals), 2) if rev_vals else None,
            "yoy_net_profit_growth_pct": round(sum(prof_vals) / len(prof_vals), 2) if prof_vals else None,
            "fetched_at": now_iso,
        }
    except Exception as e:
        logging.info(f"[EARNINGS/PROGRESS] {e}")
        return {"reported": 0, "total": 50, "yoy_revenue_growth_pct": None, "yoy_net_profit_growth_pct": None, "fetched_at": now_iso}


def _build_yfinance_fallback_earnings(tickers: list[str], now_iso: str) -> tuple[list[dict], str]:
    """
    Build earnings-like results from yfinance quarterly financials when no
    AnalysisHistory records exist. For each ticker, fetches quarterly financials
    and computes revenue_growth_pct / net_profit_growth_pct from YoY comparisons
    (current quarter vs same quarter last year).

    Returns (results: list[dict], diagnostic: str).
    diagnostic is non-empty only when yfinance also returned no useful data.
    """
    import math
    import time
    import random

    results: list[dict] = []
    errors: list[str] = []
    known_companies: dict[str, str] = {
        "RELIANCE": "Reliance Industries Ltd",
        "TCS": "Tata Consultancy Services Ltd",
        "HDFCBANK": "HDFC Bank Ltd",
        "INFY": "Infosys Ltd",
        "ICICIBANK": "ICICI Bank Ltd",
        "SBIN": "State Bank of India",
        "BAJFINANCE": "Bajaj Finance Ltd",
        "LT": "Larsen & Toubro Ltd",
        "WIPRO": "Wipro Ltd",
        "SUNPHARMA": "Sun Pharmaceutical Industries Ltd",
        "TITAN": "Titan Company Ltd",
        "MARUTI": "Maruti Suzuki India Ltd",
    }

    import concurrent.futures

    def _fetch_one(ticker: str):
        """Fetch and build earnings result for one ticker. Returns (result_dict_or_None, error_str_or_None)."""
        try:
            full_ticker = _to_ns(ticker)
            t_obj, fin = _get_quarterly_fin(full_ticker)

            if fin is None or fin.empty:
                return None, f"{ticker}: no quarterly financial data from yfinance"

            # Extract key rows
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            profit_row = fin.loc["Net Income"] if "Net Income" in fin.index else None

            if rev_row is None and profit_row is None:
                return None, f"{ticker}: missing Total Revenue and Net Income rows"

            cols = list(fin.columns)
            if len(cols) == 0:
                return None, f"{ticker}: no quarter columns in financials"

            # Most recent quarter
            latest_col = cols[0]
            latest_label = latest_col.strftime("Q%qFY%y") if hasattr(latest_col, 'strftime') else str(latest_col)[:7]
            result_date = latest_col.strftime("%Y-%m-%d") if hasattr(latest_col, 'strftime') else now_iso[:10]

            revenue = float(rev_row[latest_col]) / 1e7 if rev_row is not None and latest_col in rev_row.index else 0.0
            net_profit = float(profit_row[latest_col]) / 1e7 if profit_row is not None and latest_col in profit_row.index else 0.0
            revenue = 0.0 if math.isnan(revenue) or math.isinf(revenue) else round(revenue, 2)
            net_profit = 0.0 if math.isnan(net_profit) or math.isinf(net_profit) else round(net_profit, 2)

            # Same quarter last year (4 quarters back)
            prev_col = cols[4] if len(cols) > 4 else (cols[-1] if len(cols) > 0 else None)
            revenue_prev = 0.0
            net_profit_prev = 0.0
            if prev_col is not None:
                rp = float(rev_row[prev_col]) / 1e7 if rev_row is not None and prev_col in rev_row.index else 0.0
                np = float(profit_row[prev_col]) / 1e7 if profit_row is not None and prev_col in profit_row.index else 0.0
                revenue_prev = 0.0 if math.isnan(rp) or math.isinf(rp) else round(rp, 2)
                net_profit_prev = 0.0 if math.isnan(np) or math.isinf(np) else round(np, 2)

            # YoY growth from quarterly comparison
            revenue_growth_pct = round(((revenue - revenue_prev) / max(abs(revenue_prev), 1)) * 100, 2)
            net_profit_growth_pct = round(((net_profit - net_profit_prev) / max(abs(net_profit_prev), 1)) * 100, 2)

            # LTP from yfinance info
            ltp = 0.0
            company_name = known_companies.get(ticker, ticker)
            try:
                info = _yf_fetch_info(full_ticker)
                if info:
                    cn = info.get("longName") or info.get("shortName")
                    if cn:
                        company_name = cn
                    lp = info.get("regularMarketPrice") or info.get("currentPrice")
                    if lp and not math.isnan(float(lp)):
                        ltp = round(float(lp), 2)
            except Exception as e:
                import logging
                logging.warning(f"Swallowed exception: {e}")

            # EPS from quarterly data
            eps = None
            eps_prev = None
            try:
                eps_candidates = ["Diluted EPS", "Basic EPS", "Diluted Earnings Per Share"]
                eps_row = None
                for candidate in eps_candidates:
                    if candidate in fin.index:
                        eps_row = fin.loc[candidate]
                        break
                if eps_row is not None:
                    if latest_col in eps_row.index:
                        ev = float(eps_row[latest_col])
                        if not (math.isnan(ev) or math.isinf(ev)):
                            eps = round(ev, 2)
                    if prev_col is not None and prev_col in eps_row.index:
                        pev = float(eps_row[prev_col])
                        if not (math.isnan(pev) or math.isinf(pev)):
                            eps_prev = round(pev, 2)
            except Exception as e:
                import logging
                logging.warning(f"Swallowed exception: {e}")

            item = {
                "ticker": ticker,
                "company_name": company_name,
                "quarter": latest_label,
                "result_date": result_date,
                "market_cap": "large_cap",
                "revenue": revenue,
                "revenue_prev": revenue_prev,
                "net_profit": net_profit,
                "net_profit_prev": net_profit_prev,
                "gross_profit": None,
                "gross_profit_prev": None,
                "eps": eps,
                "eps_prev": eps_prev,
                "ltp": ltp,
                "change_percent": 0.0,
                "is_consolidated": True,
                "reported_at": None,
                "revenue_growth_pct": revenue_growth_pct,
                "net_profit_growth_pct": net_profit_growth_pct,
            }
            return item, None

        except Exception as e:
            log_earnings_error("earnings_feed_yfinance_fallback", str(e), failed_ticker=ticker)
            return None, f"{ticker}: {str(e)[:120]}"

    # Parallel fetch with 45-second overall timeout (12 tickers * 3 retries each = 36+ yfinance calls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in tickers}
        for fut in concurrent.futures.as_completed(futures, timeout=45):
            ticker = futures[fut]
            try:
                item, err = fut.result(timeout=0)
                if item:
                    results.append(item)
                if err:
                    errors.append(err)
            except Exception as e:
                import logging
                logging.warning(f"Caught exception: {e}")
                errors.append(f"{ticker}: timed out or executor error (yfinance slow)")

    diagnostic = ""
    if not results:
        ticker_list_preview = ", ".join(tickers[:6])
        if errors:
            error_list = "; ".join(errors[:3])
            diagnostic = (
                f"No analysis records in database and yfinance fallback also returned no data. "
                f"Tried {len(tickers)} tickers ({ticker_list_preview}...). "
                f"Errors: {error_list}. Run an analysis first to populate earnings data."
            )
        else:
            diagnostic = (
                f"No analysis records in database and yfinance fallback also returned no data. "
                f"Tried {len(tickers)} tickers ({ticker_list_preview}...). "
                f"Run an analysis first to populate earnings data."
            )

    return results, diagnostic


@router.get("/api/v1/earnings/feed")
async def earnings_feed_endpoint(market_cap: str = "all", sort: str = "latest"):
    """
    Ranked earnings feed — returns results categorized by sort parameter:
  - "latest":      most recently reported (default)
  - "best_performer":   highest positive profit variance
  - "worst_performer":  highest negative profit variance
Each result includes revenue_growth_pct and net_profit_growth_pct for sorting.
Falls back to yfinance quarterly data when no AnalysisHistory records exist.
Adds data_source and diagnostic fields for transparency.

    Args:
        market_cap (str): The market_cap.
        sort (str): The sort.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    data_source = "database"
    diagnostic = None

    try:
        with get_session() as session:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
            rows = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date >= cutoff
            ).order_by(AnalysisHistory.created_at.desc()).all()
            seen: set = set()
            results = []
            for r in rows:
                if r.ticker in seen:
                    continue
                seen.add(r.ticker)
                item = _earnings_result_from_row(r, now_iso)
                if item["revenue"] == 0 and item["net_profit"] == 0:
                    continue
                # Compute growth metrics for sorting
                rev_growth = round(((item["revenue"] - item["revenue_prev"]) / max(abs(item["revenue_prev"]), 1)) * 100, 2)
                profit_growth = round(((item["net_profit"] - item["net_profit_prev"]) / max(abs(item["net_profit_prev"]), 1)) * 100, 2)
                item["revenue_growth_pct"] = rev_growth
                item["net_profit_growth_pct"] = profit_growth
                results.append(item)

        # Fallback: when no DB results, build sample data from yfinance
        if not results:
            fallback_tickers = [
                "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
                "SBIN", "BAJFINANCE", "LT", "WIPRO", "SUNPHARMA",
                "TITAN", "MARUTI"
            ]
            results, fb_diagnostic = _build_yfinance_fallback_earnings(fallback_tickers, now_iso)
            if results:
                data_source = "yfinance_fallback"
            else:
                data_source = "empty"
                diagnostic = fb_diagnostic

        # Sort by category
        if sort == "best_performer":
            results.sort(key=lambda x: x.get("net_profit_growth_pct", 0), reverse=True)
        elif sort == "worst_performer":
            results.sort(key=lambda x: x.get("net_profit_growth_pct", 0))
        # "latest" keeps default order (most recent first)

        response: dict = {
            "sort": sort,
            "latest": results[:30],
            "best_performers": sorted(results, key=lambda x: x.get("net_profit_growth_pct", 0), reverse=True)[:10],
            "worst_performers": sorted(results, key=lambda x: x.get("net_profit_growth_pct", 0))[:10],
            "results": results[:30],
            "count": len(results[:30]),
            "data_source": data_source,
            "fetched_at": now_iso,
        }
        if diagnostic:
            response["diagnostic"] = diagnostic
        return response

    except Exception as e:
        log_earnings_error("earnings_feed", str(e))
        return {
            "sort": sort, "latest": [], "best_performers": [], "worst_performers": [],
            "results": [], "count": 0, "data_source": "empty", "error": str(e),
            "diagnostic": f"Earnings feed endpoint failed with error: {str(e)[:200]}. Run an analysis first to populate earnings data.",
            "fetched_at": now_iso
        }


@router.get("/api/v1/earnings/calendar")
async def earnings_calendar_day_endpoint(date: str = None, ticker: str = None):
    """
    Historical earnings calendar — returns results for a date with 7-day
price-action sparkline data per ticker. Pass ?ticker=SYM to filter.

Each result includes:
  - earnings metadata (ticker, revenue, profit, eps, etc.)
  - sparkline: list of 7 closing prices preceding the result date
  - price_change_7d_pct: % change over the 7-day window

    Args:
        date (str): The date.
        ticker (str): The ticker.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with get_session() as session:
            query = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date == target_date
            )
            if ticker:
                query = query.filter(AnalysisHistory.ticker == ticker.upper())
            rows = query.all()

            results = []
            for r in rows:
                item = _earnings_result_from_row(r, now_iso)
                # Fetch 7-day price history for sparkline
                sparkline: list[float] = []
                price_change_7d: float | None = None
                try:
                    from services.nse_data_provider import get_price_history
                    df = get_price_history(r.ticker, period_days=14)  # extra buffer
                    if df is not None and len(df) >= 2:
                        closes = df["Close"].dropna().tail(7).tolist()
                        sparkline = [round(float(c), 2) for c in closes]
                        if len(sparkline) >= 2:
                            price_change_7d = round((sparkline[-1] - sparkline[0]) / sparkline[0] * 100, 2)
                except Exception as price_err:
                    log_earnings_error("earnings_calendar_price", str(price_err), failed_ticker=r.ticker)

                item["sparkline"] = sparkline
                item["price_change_7d_pct"] = price_change_7d
                results.append(item)

        # Also scan upcoming earnings from yfinance for tickers without DB entries
        if not ticker and len(results) < 5:
            try:
                upcoming = _scan_upcoming_earnings(target_date)
                results.extend(upcoming)
            except Exception as scan_err:
                log_earnings_error("earnings_calendar_scan", str(scan_err))

        return {
            "date": target_date,
            "results": results,
            "count": len(results),
            "fetched_at": now_iso,
        }
    except Exception as e:
        log_earnings_error("earnings_calendar", str(e))
        return {"date": target_date, "results": [], "count": 0,
                "error": str(e), "fetched_at": now_iso}


@router.get("/api/v1/earnings/estimates")
async def earnings_estimates_endpoint(ticker: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    ticker = ticker.upper()
    try:
        ns = _to_ns(ticker)
        info = _yf_fetch_info(ns)
        rev_est = info.get("revenueEstimate") or info.get("totalRevenue")
        eps_est = info.get("forwardEps")
        revenue_actual = net_profit_actual = eps_actual = None
        with get_session() as session:
            latest = session.query(AnalysisHistory).filter(
                AnalysisHistory.ticker == ticker
            ).order_by(AnalysisHistory.created_at.desc()).first()
            if latest:
                try:
                    fj = json.loads(latest.full_json or "{}")
                    fs = fj.get("fundamentals_snapshot", {})
                    revenue_actual = fs.get("revenue_crores")
                    net_profit_actual = fs.get("net_profit_crores")
                    eps_actual = fs.get("eps")
                except Exception as e:
                    import logging
                    logging.warning(f"Swallowed exception: {e}")
        return {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "revenue_estimate": float(rev_est) / 1e7 if rev_est else None,
            "revenue_actual": float(revenue_actual) if revenue_actual else None,
            "net_profit_estimate": None,
            "net_profit_actual": float(net_profit_actual) if net_profit_actual else None,
            "eps_estimate": float(eps_est) if eps_est else None,
            "eps_actual": float(eps_actual) if eps_actual else None,
        }
    except Exception as e:
        logging.info(f"[EARNINGS/ESTIMATES] {ticker}: {e}")
        return {"ticker": ticker, "company_name": ticker, "revenue_estimate": None, "revenue_actual": None,
                "net_profit_estimate": None, "net_profit_actual": None, "eps_estimate": None, "eps_actual": None}


@router.get("/api/v1/earnings/post-result-movers")
async def post_result_movers_endpoint():
    now_iso = datetime.now(timezone.utc).isoformat()
    movers = []
    try:
        with get_session() as session:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
            rows = session.query(AnalysisHistory).filter(
                AnalysisHistory.analysis_date >= cutoff
            ).order_by(AnalysisHistory.created_at.desc()).all()
            seen: set = set()
            for r in rows:
                if r.ticker in seen or len(movers) >= 15:
                    continue
                seen.add(r.ticker)
                try:
                    ns = _to_ns(r.ticker)
                    t_obj = yf.Ticker(ns)
                    hist = t_obj.history(period="5d")
                    if hist.empty or len(hist) < 2:
                        continue
                    ltp = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[0])
                    change_pct = round((ltp - prev) / prev * 100, 2) if prev > 0 else 0.0
                    vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None
                    fj = json.loads(r.full_json or "{}")
                    movers.append({
                        "ticker": r.ticker,
                        "company_name": fj.get("company_name") or r.ticker,
                        "result_date": r.analysis_date or now_iso[:10],
                        "ltp": ltp,
                        "change_percent": change_pct,
                        "volume": vol,
                    })
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    continue
        movers.sort(key=lambda x: abs(x["change_percent"]), reverse=True)
        return {"movers": movers, "fetched_at": now_iso}
    except Exception as e:
        logging.info(f"[EARNINGS/POST-RESULT-MOVERS] {e}")
        return {"movers": [], "fetched_at": now_iso}


from pydantic import BaseModel as _BaseModelLocal

class EarningsAlertCreateRequest(_BaseModelLocal):
    user_id: int
    ticker: str
    earnings_date: str


@router.get("/api/v1/earnings/alerts")
def earnings_alerts_get_endpoint(user_id: int = 0):
    """
    Return all earnings alerts for a given user.
Pass ?user_id=<id> to filter. Returns empty list if none.

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        with get_session() as session:
            if user_id > 0:
                rows = session.query(EarningsAlert).filter(
                    EarningsAlert.user_id == user_id
                ).order_by(EarningsAlert.earnings_date.asc()).all()
            else:
                rows = session.query(EarningsAlert).order_by(EarningsAlert.earnings_date.asc()).limit(100).all()
            return {
                "alerts": [
                    {
                        "id": r.id,
                        "user_id": r.user_id,
                        "ticker": r.ticker,
                        "earnings_date": r.earnings_date,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        log_market_error("earnings_alerts_get", str(e))
        return {"alerts": [], "count": 0, "error": str(e), "fetched_at": datetime.now(timezone.utc).isoformat()}


@router.post("/api/v1/earnings/alerts")
def earnings_alerts_post_endpoint(body: EarningsAlertCreateRequest, user_id: int = Depends(require_auth)):
    """
    Create an earnings date alert for a user+ticker combination.
Deduplicates — if same user/ticker/date already exists, returns 200 with existing.

    Args:
        body (EarningsAlertCreateRequest): The body.
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    ticker = body.ticker.upper().strip()
    try:
        with get_session() as session:
            # Dedup check
            existing = session.query(EarningsAlert).filter(
                EarningsAlert.user_id == user_id,
                EarningsAlert.ticker == ticker,
                EarningsAlert.earnings_date == body.earnings_date,
            ).first()
            if existing:
                return {
                    "id": existing.id,
                    "user_id": existing.user_id,
                    "ticker": existing.ticker,
                    "earnings_date": existing.earnings_date,
                    "created_at": existing.created_at.isoformat() if existing.created_at else None,
                    "status": "already_exists",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }

            entry = EarningsAlert(
                user_id=user_id,
                ticker=ticker,
                earnings_date=body.earnings_date,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return {
                "id": entry.id,
                "user_id": entry.user_id,
                "ticker": entry.ticker,
                "earnings_date": entry.earnings_date,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "status": "created",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        log_market_error("earnings_alerts_post", str(e), context_ticker=ticker)
        raise HTTPException(status_code=500, detail=f"Failed to create earnings alert: {e}")


@router.delete("/api/v1/earnings/alerts/{alert_id}")
def earnings_alerts_delete_endpoint(alert_id: int, user_id: int = Depends(require_auth)):
    """
    Delete a specific earnings alert by ID. Verifies alert belongs to authenticated user.

    Args:
        alert_id (int): The alert_id.
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        with get_session() as session:
            entry = session.query(EarningsAlert).filter(
                EarningsAlert.id == alert_id,
                EarningsAlert.user_id == user_id
            ).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Alert not found" if user_id else "Alert not found or not authorized")
            session.delete(entry)
            session.commit()
            return {"deleted": True, "alert_id": alert_id, "fetched_at": datetime.now(timezone.utc).isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        log_market_error("earnings_alerts_delete", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {e}")


# ── /api/v1/admin/earnings-errors ──────────────────────────────────────────────

@router.get("/api/v1/admin/earnings-errors")
def admin_earnings_errors_endpoint(limit: int = 50, authorization: str = Header(None)):
    """
    Admin diagnostic endpoint — returns recent earnings_error_logs entries.
Requires admin auth.

    Args:
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import require_admin
    require_admin(authorization)
    try:
        with get_session() as session:
            rows = (
                session.query(EarningsErrorLog)
                .order_by(EarningsErrorLog.timestamp.desc())
                .limit(min(limit, 200))
                .all()
            )
            return {
                "errors": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "module": r.module,
                        "error_trace": r.error_trace,
                        "failed_ticker": r.failed_ticker,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Earnings error log query failed: {e}")


# ---------------------------------------------------------------------------
# F&O Option Chain
# ---------------------------------------------------------------------------

@router.get("/api/v1/options/chain/{ticker}")
def get_option_chain_metrics_endpoint(ticker: str, current_price: float = 0):
    """
    Returns pre-computed F&O derivatives metrics (PCR, Max Pain, OI Skew).
Cached 15 minutes. Returns error dict if NSE is unreachable.

    Args:
        ticker (str): The ticker.
        current_price (float): The current_price.

    Returns:
        Any: The response.
    """
    from services.options_scraper import fetch_option_chain, compute_derivatives_metrics
    raw_chain = fetch_option_chain(ticker.upper())
    if not raw_chain:
        return {"error": "Option chain unavailable from NSE", "ticker": ticker, "metrics": None}
    metrics = compute_derivatives_metrics(raw_chain, current_price=current_price)
    return {"ticker": ticker.upper(), "metrics": metrics}


# ═══════════════════════════════════════════════════════════════════════════════
# Ideas Workspace — Verified Advisor Directory & Advisory Feed
# ═══════════════════════════════════════════════════════════════════════════════

# Real SEBI-registered research analysts who publish public market commentary.
SEBI_ADVISORS = [
    {
        "name": "Rajesh Palviya",
        "sebi": "INH000002347",
        "experience": 18,
        "framework": "Technical Analysis, Volume Profile, Options Data",
        "bio": (
            "Rajesh Palviya is Head of Technical & Derivatives Research at Axis Securities. "
            "He specializes in reading institutional order flow, volume profile analysis, and "
            "options market internals. His daily market outlook — published on the Axis Securities "
            "YouTube channel — covers Nifty/Bank Nifty levels, sector rotation, and derivatives "
            "data interpretation. Palviya's methodology centres on identifying high-probability "
            "zones where institutional accumulation or distribution is visible through volume "
            "anomalies and open interest build-up."
        ),
    },
    {
        "name": "Anand James",
        "sebi": "INH000003819",
        "experience": 16,
        "framework": "Wyckoff Method, Elliott Wave, Intermarket Analysis",
        "bio": (
            "Anand James is Chief Market Strategist at Geojit Financial Services. His analytical "
            "framework combines classical Wyckoff accumulation/distribution schematics with Elliott "
            "Wave counts to identify structural market phases. James is known for his intermarket "
            "approach — correlating currency, commodity, and bond market signals with equity index "
            "positioning. His research notes frequently appear on Geojit's official platforms."
        ),
    },
    {
        "name": "Sneha Seth",
        "sebi": "INH000008241",
        "experience": 14,
        "framework": "Derivatives Analytics, PCR, Max Pain Theory",
        "bio": (
            "Sneha Seth is a SEBI-registered research analyst specializing in derivatives market "
            "structure. She uses options chain analysis, put-call ratios, and max pain theory to "
            "gauge market sentiment and identify strike-level concentration. Her work focuses on "
            "decoding institutional hedging behaviour through weekly and monthly expiry data "
            "patterns published across financial media platforms."
        ),
    },
    {
        "name": "Gaurav Bissa",
        "sebi": "INH000006853",
        "experience": 15,
        "framework": "Price Action, Ichimoku Cloud, Momentum",
        "bio": (
            "Gaurav Bissa is a technical research analyst known for his clean price action "
            "methodology. He employs Ichimoku Kinko Hyo overlays, momentum oscillators, and "
            "multi-timeframe analysis to filter noise and identify trend continuations. His "
            "commentary — published through LKP Securities and financial news channels — "
            "emphasizes risk-reward ratios and stop-loss discipline."
        ),
    },
    {
        "name": "Nagaraj Shetti",
        "sebi": "INH000009712",
        "experience": 20,
        "framework": "Classical Chart Patterns, Fibonacci, Market Cycles",
        "bio": (
            "Nagaraj Shetti is a senior technical research analyst at HDFC Securities with two "
            "decades of market experience. His framework relies on classical chart patterns — "
            "head and shoulders, double tops/bottoms, flags, and wedges — combined with Fibonacci "
            "retracement and extension levels. Shetti's daily notes cover Nifty, Bank Nifty, and "
            "high-conviction stock picks with clearly defined entry, target, and stop-loss levels."
        ),
    },
    {
        "name": "Chandan Taparia",
        "sebi": "INH000011523",
        "experience": 13,
        "framework": "Options Strategies, F&O Data Analysis",
        "bio": (
            "Chandan Taparia is a derivatives analyst at Motilal Oswal Financial Services. He "
            "specializes in futures and options data interpretation — tracking rollover percentages, "
            "open interest shifts, and implied volatility surfaces to construct options-based "
            "trading strategies. His daily F&O commentary is widely followed by retail traders "
            "for Nifty and stock-specific derivative trade ideas."
        ),
    },
    {
        "name": "Milan Vaishnav",
        "sebi": "INH000013092",
        "experience": 17,
        "framework": "Relative Strength, Sector Rotation, Market Breadth",
        "bio": (
            "Milan Vaishnav is a CMT charterholder and founder of Gemstone Equity Research. "
            "His analytical approach centres on relative strength analysis, sector rotation "
            "dynamics, and market breadth indicators. Vaishnav's research identifies leadership "
            "shifts across sectors using relative rotation graphs (RRG) and advance-decline "
            "data, helping investors allocate capital to outperforming segments."
        ),
    },
    {
        "name": "Shubham Agarwal",
        "sebi": "INH000014768",
        "experience": 12,
        "framework": "Quantitative Momentum, Mean Reversion, Algo Trading",
        "bio": (
            "Shubham Agarwal is a SEBI-registered quantitative research analyst specializing in "
            "systematic trading strategies. His work integrates momentum factor models, mean "
            "reversion signals, and volatility regime filters to construct rule-based portfolios. "
            "Agarwal publishes research on backtested quantitative strategies through his advisory "
            "platform, focusing on risk-adjusted return optimization."
        ),
    },
]


def _populate_advisor_biographies() -> int:
    """Insert SEBI_ADVISORS into the database if the table is empty.
    Returns the number of rows inserted (0 if already populated)."""
    try:
        with get_session() as session:
            if session.query(AdvisorBiography).count() > 0:
                return 0
            count = 0
            for a in SEBI_ADVISORS:
                session.add(AdvisorBiography(
                    advisor_name=a["name"],
                    sebi_reg_number=a["sebi"],
                    experience_years=a["experience"],
                    analytical_framework=a["framework"],
                    full_biography_text=a["bio"],
                ))
                count += 1
            session.commit()
            return count
    except Exception as e:
        logging.info(f"[IDEAS] Failed to populate advisor biographies: {e}")
        return 0


# ── GET /api/v1/ideas/advisors ─────────────────────────────────────────────

@router.get("/api/v1/ideas/advisors")
def ideas_advisors_endpoint():
    """
    Returns verified SEBI-registered research analysts with full biographies.
Auto-populates the table from the built-in SEBI_ADVISORS list if empty.
Response: { "advisors": [...], "count": N, "fetched_at": "..." }

    Args:

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        _populate_advisor_biographies()
        with get_session() as session:
            rows = session.query(AdvisorBiography).order_by(
                AdvisorBiography.experience_years.desc()
            ).all()
            return {
                "advisors": [
                    {
                        "id": r.id,
                        "advisor_name": r.advisor_name,
                        "sebi_reg_number": r.sebi_reg_number,
                        "experience_years": r.experience_years,
                        "analytical_framework": r.analytical_framework,
                        "full_biography_text": r.full_biography_text,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": now_iso,
            }
    except Exception as e:
        log_ideas_error("ideas_advisors", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch advisors: {e}")


# ── GET /api/v1/ideas/feed ─────────────────────────────────────────────────

@router.get("/api/v1/ideas/feed")
def ideas_feed_endpoint(limit: int = 20, sentiment: str = "all"):
    """
    Returns recent TextAdvisoryInsight rows joined with advisor names.
Filter by sentiment: ?sentiment=all (default), bullish, or bearish.
Falls back gracefully if no insights exist.
Response: { "insights": [{id, advisor_name, timestamp, content_text,
                          target_ticker, extracted_sentiment}], "count": N }

    Args:
        limit (int): The limit.
        sentiment (str): The sentiment.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    sentiment = sentiment.lower()
    try:
        with get_session() as session:
            q = session.query(TextAdvisoryInsight, AdvisorBiography.advisor_name).join(
                AdvisorBiography,
                TextAdvisoryInsight.advisor_id == AdvisorBiography.id,
                isouter=True,
            )
            if sentiment == "bullish":
                q = q.filter(TextAdvisoryInsight.extracted_sentiment == "BULLISH")
            elif sentiment == "bearish":
                q = q.filter(TextAdvisoryInsight.extracted_sentiment == "BEARISH")

            rows = q.order_by(TextAdvisoryInsight.timestamp.desc()).limit(
                min(limit, 100)
            ).all()

            insights = []
            for insight, advisor_name in rows:
                insights.append({
                    "id": insight.id,
                    "advisor_name": advisor_name or "Unknown Advisor",
                    "timestamp": insight.timestamp.isoformat() if insight.timestamp else None,
                    "content_text": insight.content_text,
                    "target_ticker": insight.target_ticker,
                    "extracted_sentiment": insight.extracted_sentiment,
                })

            return {
                "insights": insights,
                "count": len(insights),
                "sentiment_filter": sentiment,
                "fetched_at": now_iso,
            }
    except Exception as e:
        log_ideas_error("ideas_feed", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch ideas feed: {e}")


# ── GET /api/v1/admin/ideas-errors ─────────────────────────────────────────

@router.get("/api/v1/admin/ideas-errors")
def admin_ideas_errors_endpoint(limit: int = 50, authorization: str = Header(None)):
    """
    Admin diagnostic endpoint — returns recent IdeasErrorLog entries.
Requires admin auth.
Response: { "errors": [...], "count": N }

    Args:
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import require_admin
    require_admin(authorization)
    try:
        with get_session() as session:
            rows = (
                session.query(IdeasErrorLog)
                .order_by(IdeasErrorLog.timestamp.desc())
                .limit(min(limit, 200))
                .all()
            )
            return {
                "errors": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "module": r.module,
                        "error_trace": r.error_trace,
                        "context_ticker": r.context_ticker,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ideas error log query failed: {e}")


# ── /api/v1/market/top-movers ─────────────────────────────────────────────────

# NIFTY 50 tickers — well-covered by yfinance, fast enough for a single request
_NIFTY50_TICKERS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC",
    "SBIN", "BAJFINANCE", "BHARTIARTL", "KOTAKBANK", "AXISBANK", "ASIANPAINT",
    "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO", "HCLTECH", "TECHM",
    "ONGC", "POWERGRID", "NTPC", "COALINDIA", "JSWSTEEL", "TATASTEEL", "HINDALCO",
    "GRASIM", "ADANIENT", "ADANIPORTS", "BAJAJ-AUTO", "BAJAJFINSV", "BPCL",
    "BRITANNIA", "CIPLA", "DIVISLAB", "DRREDDY", "EICHERMOT", "HDFCLIFE",
    "HEROMOTOCO", "INDUSINDBK", "LT", "M&M", "NESTLEIND", "SBILIFE",
    "SHRIRAMFIN", "TATACONSUM", "TATAMOTORS", "TRENT", "UPL",
]


@router.get("/api/v1/market/top-movers")
async def top_movers_endpoint():
    """
    Returns top gainers, losers, active-by-value, active-by-volume from NIFTY 50.
Each list is capped at 10 entries. Uses yfinance batch download (fast).
Response: {
    "gainers": [...], "losers": [...],
    "active_by_value": [...], "active_by_volume": [...],
    "fetched_at": str
}

    Args:

    Returns:
        Any: The response.
    """
    from services.disk_cache import get as _dc_get, set as _dc_set
    cache_key = "top_movers_today"
    cached = _dc_get("market_pulse", cache_key)
    if cached:
        return cached

    try:
        symbols = [f"{t}.NS" for t in _NIFTY50_TICKERS]
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: yf.download(
                symbols,
                period="2d",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            ),
        )

        movers = []
        for sym in symbols:
            try:
                ticker_base = sym.replace(".NS", "")
                if sym in raw.columns.get_level_values(0):
                    df = raw[sym].dropna()
                else:
                    continue
                if len(df) < 2:
                    continue
                close_today = float(df["Close"].iloc[-1])
                close_prev = float(df["Close"].iloc[-2])
                vol_today = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0.0
                change_abs = close_today - close_prev
                change_pct = (change_abs / close_prev * 100) if close_prev else 0.0
                value = close_today * vol_today  # traded value in INR

                # Fetch name from yfinance info (best effort)
                movers.append({
                    "ticker": ticker_base,
                    "name": ticker_base,
                    "price": round(close_today, 2),
                    "change_pct": round(change_pct, 2),
                    "change_abs": round(change_abs, 2),
                    "volume": int(vol_today),
                    "value": round(value, 0),
                })
            except Exception as e:
                import logging
                logging.warning(f"Caught exception: {e}")
                continue

        if not movers:
            empty_result = {
                "gainers": [], "losers": [],
                "active_by_value": [], "active_by_volume": [],
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
            _dc_set("market_pulse", cache_key, empty_result)
            return empty_result

        gainers = sorted(movers, key=lambda x: x["change_pct"], reverse=True)[:10]
        losers = sorted(movers, key=lambda x: x["change_pct"])[:10]
        active_by_value = sorted(movers, key=lambda x: x["value"], reverse=True)[:10]
        active_by_volume = sorted(movers, key=lambda x: x["volume"], reverse=True)[:10]

        result = {
            "gainers": gainers,
            "losers": losers,
            "active_by_value": active_by_value,
            "active_by_volume": active_by_volume,
            "fetched_at": _dt.now(timezone.utc).isoformat(),
        }
        # Cache for 15 minutes (market data refreshes frequently)
        _dc_set("market_pulse", cache_key, result)
        return result

    except Exception as exc:
        log_market_error("top_movers", str(exc))
        raise HTTPException(status_code=500, detail=f"Top movers fetch failed: {exc}")

@router.get("/market/sentiment-trend/{ticker}")
def sentiment_trend(ticker: str, days: int = 30):
    """
    30-Day Rolling News Sentiment Chart per Ticker.

    Args:
        ticker (str): The ticker.
        days (int): The days.

    Returns:
        Any: The response.
    """
    try:
        from services.sentiment_engine import get_sentiment_trend
        trend = get_sentiment_trend(ticker, days)
        return {"ticker": ticker, "trend": trend}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/market/screener")
def run_screener(preset: str = "52w_breakout"):
    """
    Screener endpoint.

    Args:
        preset (str): The preset.

    Returns:
        Any: The response.
    """
    try:
        import yfinance as yf
        if preset == "52w_breakout":
            # Just a minimal set of top NSE tickers to avoid rate limiting
            tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS", "SBI.NS", "BHARTIARTL.NS"]
            results = []
            for t in tickers:
                try:
                    info = yf.Ticker(t).info
                    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                    high_52w = info.get("fiftyTwoWeekHigh")
                    volume = info.get("volume")
                    avg_volume = info.get("averageVolume")
                    name = info.get("shortName", t)
                    
                    if current_price and high_52w and volume and avg_volume:
                        if current_price > 0.98 * high_52w and volume > avg_volume * 1.2:
                            pct_from_high = (high_52w - current_price) / high_52w * 100
                            volume_ratio = volume / avg_volume
                            results.append({
                                "ticker": t,
                                "name": name,
                                "current_price": round(current_price, 2),
                                "week52_high": round(high_52w, 2),
                                "pct_from_high": round(pct_from_high, 2),
                                "volume_ratio": round(volume_ratio, 2)
                            })
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    continue
            return {"preset": preset, "results": results}
        else:
            return {"preset": preset, "results": []}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal server error")
