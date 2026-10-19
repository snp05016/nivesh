from helpers import (
    verify_access_token, EXCHANGE_SUFFIX, _resolve_ticker, _to_ns, _yf_price, _dcache_get,
    _dcache_set, _quick_info_cache, _QUICK_INFO_TTL, EarningsSyncRatioResponse,
    YoYAggregateResponse, InstitutionalLeaderboardResponse, NetWorthSnapshotResponse, User,
    Portfolio, NetWorthLedger, log_market_error, _check_rate_limit, _get_indices_data,
    _get_asm_gsm_lists, _nse_session, format_indian_currency,
)

from services.market_service import (
    _get_quarterly_fin, _yf_fetch_info, _fmt_inr_crores, _safe_float, get_rbi_policy,
    analyst_ratings, quarterly_rows, holdings_from_info,
    SECTOR_TICKERS,
)
from services.cache_service import cached_call
from concurrent.futures import ThreadPoolExecutor

import json
import logging
import os
import time
import asyncio
import random
import math
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, Request
import yfinance as yf
from services.scraper import (
    fetch_market_pulse, fetch_momentum, fetch_macro_alternatives, fetch_institutional_flow,
    fetch_yoy_aggregate_indicators,
)
from services.options_scraper import fetch_option_chain, compute_derivatives_metrics
from services.nse_data_provider import get_price_history
from services.market_calendar import market_status

router = APIRouter(tags=["Market Data"])


@router.get("/market-indices")
def market_indices_endpoint():
    return _get_indices_data()


_NIFTY_HISTORY_BUCKETS = (30, 90, 180, 365, 730, 1825, 3650)


def _trim_nifty_prices(payload: dict, days: int) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return {**payload, "prices": [p for p in payload.get("prices", []) if p.get("date", "") >= cutoff]}


@router.get("/nifty-history")
def nifty_history_endpoint(days: int = Query(365, ge=1, le=3650)):
    # Fetch and cache per bucket, not per raw `days`, so callers cannot mint
    # unbounded cache keys and Yahoo downloads (REL-23).
    bucket = next(b for b in _NIFTY_HISTORY_BUCKETS if b >= days)
    cache_key = f"nifty_history_{bucket}"
    cached = _dcache_get("market", cache_key)
    if cached is not None:
        return _trim_nifty_prices(cached, days)
    try:
        import time
        import random
        hist = None
        for attempt in range(3):
            try:
                t = yf.Ticker("^NSEI")
                hist = t.history(period=f"{bucket}d")
                if not hist.empty:
                    break
            except Exception as e:
                logging.info(f"[YF] Nifty history attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))

        if hist is None or hist.empty:
            # [] would read as "no history"; iOS treats non-2xx as unavailable.
            raise HTTPException(status_code=503, detail="NIFTY history unavailable")

        result = []
        for date, row in hist.iterrows():
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2)
            })
        payload = {"prices": result}
        _dcache_set("market", cache_key, payload, ttl=1800)
        return _trim_nifty_prices(payload, days)
    except HTTPException:
        raise
    except Exception:
        logging.exception("[NIFTY-HISTORY] failed")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/dividends/{ticker}")
def dividend_history_endpoint(ticker: str, exchange: str = "NSE"):
    try:
        resolved_ticker = _resolve_ticker(ticker, exchange)
        t = yf.Ticker(resolved_ticker)
        divs = t.dividends
        
        current_price = None
        try:
            fast = t.fast_info
            current_price = getattr(fast, "last_price", None)
        except Exception as e:
            logging.warning("[dividends] fast_info unavailable for %s: %s", resolved_ticker, e)

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
        result = quarterly_rows(fin)  # last 8 quarters, in crores
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
                                    "fii": fii,  # None when unknown, not a fake 0
                                    "dii": dii,
                                })
                        except Exception as e:
                            logging.warning("[quarterly-financials] skipping malformed history row for %s: %s", ticker, e)
            promoter_history = list(reversed(promoter_history[:4]))
        except Exception as e:
            logging.warning("[quarterly-financials] promoter history unavailable for %s: %s", ticker, e)
            promoter_history = []

        payload = {"quarters": result, "promoter_history": promoter_history}
        if result:  # SILENT-11: an empty (failed) fetch must not be cached for an hour
            _dcache_set("market", cache_key, payload, ttl=3600)
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


_MACRO_SYMBOLS = (
    ("usd_inr", "USDINR=X"),
    ("crude_oil_usd", "CL=F"),
    ("brent_oil_usd", "BZ=F"),  # India imports Brent-priced oil, more relevant than WTI
    ("india_vix", "^INDIAVIX"),  # fear gauge for Indian retail markets
)


def _macro_quote(sym: str):
    """Last price for one macro symbol, or None. Never raises."""
    try:
        info = yf.Ticker(sym).info or {}
        v = info.get("regularMarketPrice") or info.get("currentPrice")
        return round(float(v), 2) if v and math.isfinite(float(v)) else None
    except Exception as e:
        logging.warning(f"[macro-strip] {sym} quote failed: {e}")
        return None


def _compute_macro_strip() -> dict:
    """The four quotes fetched concurrently; a failed one is null, never invented."""
    with ThreadPoolExecutor(max_workers=len(_MACRO_SYMBOLS)) as ex:
        prices = list(ex.map(_macro_quote, [sym for _, sym in _MACRO_SYMBOLS]))
    result: dict = {key: price for (key, _), price in zip(_MACRO_SYMBOLS, prices)}
    result["india_vix_source"] = "live" if result["india_vix"] is not None else "unavailable"
    return result


@router.get("/macro-strip")
def macro_strip_endpoint():
    """
    Returns USD/INR rate, crude oil price, India VIX and RBI repo rate for the context strip.

    Single-flight cached for 5 min (PERF-10); a strip without USD/INR is kept
    only 30 s so a transient Yahoo failure is retried soon.

    Returns:
        Any: The response.
    """
    try:
        result = dict(cached_call(
            "market", "macro_strip", _compute_macro_strip, ttl=300,
            cache_if=lambda r: r.get("usd_inr") is not None, negative_ttl=30,
        ))
        # RBI repo rate — operator-maintained config value with as-of date (not cached)
        result.update(get_rbi_policy())
        return result
    except Exception as e:
        logging.error(f"[macro-strip] failed: {e}", exc_info=True)
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
                result["macro_strip"]["india_vix_source"] = "live"
        except Exception as e:
            result["macro_strip"]["_error"] = str(e)
        result["macro_strip"].setdefault("india_vix", None)
        result["macro_strip"].setdefault("india_vix_source", "unavailable")
        result["macro_strip"].update(get_rbi_policy())

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
        vix_val = result["macro_strip"].get("india_vix")
        fii_bias = result["fii_dii_trend"].get("bias", "NEUTRAL")
        if vix_val is None:
            zone = None; score = None
        elif vix_val > 25 and fii_bias == "FII_SELLING":
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
            "interpretation": interp_map.get(zone, "") if zone else "Unavailable: India VIX feed down",
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

        repo = result["macro_strip"].get("rbi_repo_rate_pct")
        if repo is not None:
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
                        logging.warning("[macro-context] unreadable cached analysis for %s: %s", ticker, e)
        except Exception as e:
            logging.warning("[macro-context] AI summary lookup failed for %s: %s", ticker, e)

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


@router.get("/analyst-ratings")
def analyst_ratings_endpoint(ticker: str, exchange: str = "NSE"):
    cache_key = f"analyst_ratings_{ticker.upper()}_{exchange.upper()}"
    cached = _dcache_get("market", cache_key)
    if cached is not None:
        return cached
    try:
        full_ticker = _resolve_ticker(ticker, exchange)
        payload = analyst_ratings(full_ticker)
        covered = payload["buy"] + payload["hold"] + payload["sell"] > 0
        _dcache_set("market", cache_key, payload, ttl=3600 if covered else 900)
        return payload
    except Exception as e:
        logging.error(f"[analyst-ratings] failed for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
            logging.warning(f"Caught exception: {e}")
            continue
    return {"sectors": results}


# ---------------------------------------------------------------------------
# Stock Directory Search
# ---------------------------------------------------------------------------

# Single loader for the NSE/BSE directory (ARCH-10): services/stock_universe.
from services import stock_universe

_NSE_DIRECTORY = list(stock_universe.entries())

# Pre-process for fast search: lowercase index (entries are already deduped by ticker)
_NSE_DIR_INDEX = [
    {**e, "_t": e["ticker"].lower(), "_n": e["company_name"].lower(), "_s": e["sector"].lower()}
    for e in _NSE_DIRECTORY
]


@router.get("/search")
def search_endpoint(q: str = "", limit: int = Query(20, ge=1, le=100)):
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


def _sector_row(ticker: str, name: str):
    """One sector index row from its 5-day close history, or None. Never raises."""
    try:
        current, prev = _yf_price(ticker)
    except Exception as e:
        logging.warning(f"[sector-performance] {ticker} failed: {e}")
        return None
    if current is None or prev is None or not math.isfinite(current) or not math.isfinite(prev) or prev == 0:
        return None
    change_abs = round(current - prev, 2)
    return {
        "name": name,
        "ticker": ticker,
        "value": round(current, 2),
        "change_abs": change_abs,
        "change_pct": round((change_abs / prev) * 100, 2),
    }


def _compute_sector_performance() -> dict:
    with ThreadPoolExecutor(max_workers=len(SECTOR_TICKERS)) as ex:
        rows = list(ex.map(lambda tn: _sector_row(*tn), SECTOR_TICKERS))
    sectors = [r for r in rows if r is not None]
    return {
        "sectors": sorted(sectors, key=lambda x: abs(x["change_pct"]), reverse=True),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sector-performance")
def sector_performance_endpoint():
    """Sector index moves. Single-flight cached 10 min; a result with fewer than
    half the sectors is kept only 60 s instead of pinning a partial view (PERF-10)."""
    return cached_call(
        "sector", "performance", _compute_sector_performance, ttl=600,
        cache_if=lambda r: len(r["sectors"]) >= len(SECTOR_TICKERS) // 2, negative_ttl=60,
    )


# ---------------------------------------------------------------------------
# v1 Market Intelligence Routes (Firecrawl + fallback scraping, 15-min cache)
# ---------------------------------------------------------------------------

@router.get("/api/v1/market/status")
def market_status_endpoint():
    """NSE open/closed for the Home status pill, honouring exchange holidays and special sessions."""
    return market_status()

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
        logging.warning("Market pulse unavailable: %s", e)
        raise HTTPException(status_code=502, detail="Market pulse temporarily unavailable")

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
        logging.warning("Momentum data unavailable: %s", e)
        raise HTTPException(status_code=502, detail="Momentum data temporarily unavailable")

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
        logging.warning("Macro data unavailable: %s", e)
        raise HTTPException(status_code=502, detail="Macro data temporarily unavailable")


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
    # Shareholding + D/E, shared with /quick-info so both agree (CMKT-08).
    holdings = holdings_from_info({})
    roe_pct = None
    roce_pct = None
    ebitda_margin_pct = None
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

        holdings = holdings_from_info(info)

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
            quarterly_data["quarters"] = quarterly_rows(fin)
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
                        logging.warning("[stock-profile] skipping malformed history row for %s: %s", ticker, e)
            quarterly_data["promoter_history"] = list(
                reversed(quarterly_data["promoter_history"][:4])
            )
    except Exception as e:
        logging.warning("[stock-profile] promoter history unavailable for %s: %s", ticker, e)
        quarterly_data["promoter_history"] = []
        errors.append("promoter_history_unavailable")

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
        **holdings,
        "roe_pct": _clean_num(roe_pct),
        "roce_pct": _clean_num(roce_pct),
        "ebitda_margin_pct": _clean_num(ebitda_margin_pct),
        "week_52_high": _clean_num(week_52_high),
        "week_52_low": _clean_num(week_52_low),
        "market_cap_crores": _clean_num(market_cap_crores),
        "description": description,
        "price_history": _sanitize_for_json(price_history_data),
        "quarterly_financials": _sanitize_for_json(quarterly_data),
        "errors": errors,
    }

    # A partial profile (errors non-empty) is kept 60 s so it refreshes once upstream recovers (PERF-18, CMKT-04).
    _dcache_set("market", cache_key, result, ttl=60 if errors else 900)
    return result


# ── Pydantic response schemas (must precede endpoints that reference them) ────
from pydantic import BaseModel as _BaseModel
from typing import List as _List, Optional as _Optional


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
        logging.warning("Dashboard fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Market dashboard temporarily unavailable")


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

    # fetch_market_pulse (Firecrawl extract and yfinance fallback) puts breadth at the
    # top level; there is no "breadth" sub-dict (CMKT-03).
    advances = int(pulse_raw.get("advances") or 0)
    declines = int(pulse_raw.get("declines") or 0)
    breadth_ratio = pulse_raw.get("breadth_ratio")
    if breadth_ratio is None and declines > 0:
        breadth_ratio = round(advances / declines, 2)
    pulse_section = {
        "indices": pulse_raw.get("indices", []),
        "advances": advances,
        "declines": declines,
        "unchanged": int(pulse_raw.get("unchanged") or 0),
        "breadth_ratio": breadth_ratio,
        "breadth_sample_size": pulse_raw.get("breadth_sample_size"),
        "fetched_at": now_iso,
    }

    # fetch_momentum entries already carry the iOS MomentumTicker fields (ticker,
    # last_price, ma20, ma50, sparkline, trend_date, crossover), so pass them through.
    mom = momentum_raw if isinstance(momentum_raw, dict) else {}
    bullish = list(mom.get("bullish") or [])
    bearish = list(mom.get("bearish") or [])

    # ── SECTION 1: Live Reporting Sync ───────────────────────────────────────
    # No exchange-wide results-filing source exists (filings_extractor only sees
    # the latest ~100 filings), so this is reported as unavailable, never as a
    # count over an invented denominator.

    # ── SECTION 2: YoY Market Health ─────────────────────────────────────────
    # Null unless both YoY figures were actually computed; source and sample
    # size travel with the numbers so the UI can label them honestly.
    yoy_health: dict | None = None
    try:
        yoy_raw = await asyncio.get_event_loop().run_in_executor(None, fetch_yoy_aggregate_indicators)
        if yoy_raw and yoy_raw.get("revenue_yoy_pct") is not None and yoy_raw.get("net_profit_yoy_pct") is not None:
            yoy_health = {
                "revenue_yoy_pct": round(float(yoy_raw["revenue_yoy_pct"]), 2),
                "net_profit_yoy_pct": round(float(yoy_raw["net_profit_yoy_pct"]), 2),
                "companies_reported": int(yoy_raw.get("companies_reported") or 0),
                "sample_size": yoy_raw.get("sample_size"),
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
        "momentum": {"bullish": bullish, "bearish": bearish,
                     "fetched_at": mom.get("fetched_at", now_iso)},
        "live_reporting_sync": None,
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
                logging.warning("[cap-grid] skipping ticker: %s", e)

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


# ---------------------------------------------------------------------------
# F&O Option Chain
# ---------------------------------------------------------------------------

@router.get("/api/v1/options/chain/{ticker}")
def get_option_chain_metrics_endpoint(ticker: str, current_price: float = 0):
    """
    Returns pre-computed F&O derivatives metrics (PCR, Max Pain, OI Skew).
Cached 15 minutes. Raises 503 if NSE is unreachable.

    Args:
        ticker (str): The ticker.
        current_price (float): The current_price.

    Returns:
        Any: The response.
    """
    from services.options_scraper import fetch_option_chain, compute_derivatives_metrics
    raw_chain = fetch_option_chain(ticker.upper())
    if not raw_chain:
        raise HTTPException(status_code=503, detail="Option chain temporarily unavailable from NSE")
    metrics = compute_derivatives_metrics(raw_chain, current_price=current_price)
    return {"ticker": ticker.upper(), "metrics": metrics}


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
def top_movers_endpoint():
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
        raw = yf.download(
            symbols,
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
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
                logging.warning(f"Caught exception: {e}")
                continue

        if not movers:
            empty_result = {
                "gainers": [], "losers": [],
                "active_by_value": [], "active_by_volume": [],
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
            # Upstream failure, not a real empty market: keep it 60 s only (PERF-18).
            _dc_set("market_pulse", cache_key, empty_result, ttl=60)
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
        _dc_set("market_pulse", cache_key, result, ttl=900)
        return result

    except Exception as exc:
        log_market_error("top_movers", str(exc))
        raise HTTPException(status_code=500, detail=f"Top movers fetch failed: {exc}")

@router.get("/market/sentiment-trend/{ticker}")
def sentiment_trend(ticker: str, days: int = Query(30, ge=1, le=365)):
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
                    logging.warning(f"Caught exception: {e}")
                    continue
            return {"preset": preset, "results": results}
        else:
            return {"preset": preset, "results": []}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal server error")
