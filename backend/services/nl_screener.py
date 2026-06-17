import json
import logging
import yfinance as yf
from typing import Any

from services.llm_utils import deepseek_chat
from helpers import _extract_json_from_text
from services.disk_cache import get, set

logger = logging.getLogger(__name__)

# Maps common user terms to yfinance sector strings
_SECTOR_ALIASES: dict[str, list[str]] = {
    "it": ["technology"],
    "tech": ["technology"],
    "software": ["technology"],
    "information technology": ["technology"],
    "banking": ["financial services"],
    "bank": ["financial services"],
    "finance": ["financial services"],
    "nbfc": ["financial services"],
    "insurance": ["financial services"],
    "fintech": ["financial services"],
    "pharma": ["healthcare"],
    "pharmaceutical": ["healthcare"],
    "health": ["healthcare"],
    "hospital": ["healthcare"],
    "fmcg": ["consumer defensive"],
    "consumer staple": ["consumer defensive"],
    "consumer goods": ["consumer defensive", "consumer cyclical"],
    "auto": ["consumer cyclical"],
    "automobile": ["consumer cyclical"],
    "retail": ["consumer cyclical"],
    "hospitality": ["consumer cyclical"],
    "energy": ["energy"],
    "oil": ["energy"],
    "gas": ["energy"],
    "power": ["utilities"],
    "utility": ["utilities"],
    "electricity": ["utilities"],
    "metal": ["basic materials", "materials"],
    "steel": ["basic materials", "materials"],
    "mining": ["basic materials", "materials"],
    "cement": ["basic materials", "materials"],
    "infrastructure": ["industrials"],
    "engineering": ["industrials"],
    "construction": ["industrials"],
    "telecom": ["communication services"],
    "telecommunication": ["communication services"],
    "media": ["communication services"],
    "real estate": ["real estate"],
    "realty": ["real estate"],
    "chemical": ["basic materials", "materials"],
    "defence": ["industrials"],
    "defense": ["industrials"],
}

# Broad NSE universe covering large, mid, and small cap across all sectors
_INDIA_STOCK_UNIVERSE = [
    # NIFTY 50 — Large Cap
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BAJFINANCE.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
    "ONGC.NS", "POWERGRID.NS", "NTPC.NS", "COALINDIA.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "GRASIM.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "INDUSINDBK.NS", "LT.NS", "M&M.NS", "NESTLEIND.NS", "SBILIFE.NS",
    "SHRIRAMFIN.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TRENT.NS", "UPL.NS",
    # NIFTY Next 50 / Upper Mid Cap
    "ADANIGREEN.NS", "ADANITRANS.NS", "AMBUJACEM.NS", "APOLLOHOSP.NS", "BANDHANBNK.NS",
    "BIOCON.NS", "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS", "COLPAL.NS",
    "CONCOR.NS", "DABUR.NS", "DLF.NS", "FEDERALBNK.NS", "GAIL.NS",
    "GODREJCP.NS", "HAVELLS.NS", "IDFCFIRSTB.NS", "INDUSTOWER.NS", "IOC.NS",
    "IRCTC.NS", "LTIM.NS", "LUPIN.NS", "MUTHOOTFIN.NS", "NAUKRI.NS",
    "PAGEIND.NS", "PGHH.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
    "SBICARD.NS", "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TVSMOTOR.NS",
    "VEDL.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "ZOMATO.NS", "PAYTM.NS",
    # Mid Cap — Banking & Finance
    "AUBANK.NS", "CITYUNIONB.NS", "EQUITASBNK.NS", "ESAFSFB.NS", "FINPIPE.NS",
    "KARURVYSYA.NS", "LICHSGFIN.NS", "MANAPPURAM.NS", "POONAWALLA.NS", "RBLBANK.NS",
    "SOUTHBANK.NS", "UJJIVANSFB.NS", "YESBANK.NS",
    # Mid Cap — IT & Tech
    "COFORGE.NS", "HEXAWARE.NS", "KPITTECH.NS", "MPHASIS.NS", "PERSISTENT.NS",
    "TATAELXSI.NS", "ZENSAR.NS", "ZENSARTECH.NS", "INFY.NS", "LTTS.NS",
    # Mid Cap — Pharma & Healthcare
    "ALKEM.NS", "AUROPHARMA.NS", "GLENMARK.NS", "GRANULES.NS", "IPCA.NS",
    "JBCHEPHARM.NS", "LAURUSLABS.NS", "NATCOPHARM.NS", "PFIZER.NS", "SANOFI.NS",
    "STAR.NS", "THYROCARE.NS", "ZYDUSLIFE.NS",
    # Mid Cap — Consumer & FMCG
    "BAJAJELEC.NS", "EMAMILTD.NS", "GODREJIND.NS", "MARICO.NS", "MCDOWELL-N.NS",
    "RADICO.NS", "TATAPOWER.NS", "UNITED SPIRITS.NS", "VBL.NS",
    # Mid Cap — Auto & Ancillary
    "APOLLOTYRE.NS", "ASHOKLEY.NS", "BALKRISIND.NS", "BHARATFORG.NS",
    "CEATLTD.NS", "ESCORTS.NS", "EXIDEIND.NS", "MOTHERSON.NS", "SONACOMS.NS",
    "SUNDRMFAST.NS", "TVSSRICHAK.NS",
    # Mid Cap — Infrastructure & Engineering
    "ABB.NS", "AIAENG.NS", "BHEL.NS", "BEL.NS", "CUMMINSIND.NS",
    "GNFC.NS", "GRINDWELL.NS", "HAL.NS", "IRFC.NS", "KNRCON.NS",
    "NPTC.NS", "PNCINFRA.NS", "POLYCAB.NS", "RATNAMANI.NS", "THERMAX.NS",
    # Mid Cap — Metals & Materials
    "APL.NS", "HLEGLAS.NS", "JINDALSTEL.NS", "JSWENERGY.NS", "NMDC.NS",
    "SAILSTEEL.NS", "SANDUMA.NS", "WELSPUNLIV.NS",
    # Mid Cap — Cement & Real Estate
    "ACC.NS", "DALMIACEMT.NS", "GODREJPROP.NS", "JKCEMENT.NS", "MAHINDCIE.NS",
    "OBEROI.NS", "PRESTIGE.NS", "RAMCOCEM.NS", "SOBHA.NS",
    # Small Cap — Diverse
    "AARTIIND.NS", "AEGISLOG.NS", "APLLTD.NS", "ASTRAL.NS", "AVANTIFEED.NS",
    "BASF.NS", "CDSL.NS", "DEEPAKNTR.NS", "GICRE.NS", "GESHIP.NS",
    "HINDCOPPER.NS", "ICICIGI.NS", "IDBI.NS", "INDHOTEL.NS", "IRCON.NS",
    "JUBLFOOD.NS", "KFINTECH.NS", "LICI.NS", "MAXHEALTH.NS", "MCX.NS",
    "METROPOLIS.NS", "NAUKRI.NS", "NIACL.NS", "PATANJALI.NS", "PCBL.NS",
    "RECLTD.NS", "ROUTE.NS", "SAFARI.NS", "SENCO.NS", "SULA.NS",
    "TANLA.NS", "TEJASNET.NS", "TRENT.NS", "VARUNBEV.NS", "ZYDUSWELL.NS",
]

SYSTEM_PROMPT = """You parse natural language stock screening queries into structured filters. Return ONLY valid JSON.
Available filters: sector, industry, pe_max, pe_min, market_cap_min, market_cap_max, promoter_holding_min, fii_holding_min, dii_holding_min, roce_min, roe_min, debt_to_equity_max, ebitda_margin_min, dividend_yield_min, price_change_3m_min, price_change_1y_min, rsi_min, rsi_max, keyword (free text search in company name/description).

IMPORTANT: For market cap, output values in Crores (Cr) based on these standard definitions:
- Mega Cap: > 100000
- Large Cap: 20000 to 100000
- Upper Mid Cap: 10000 to 20000
- Lower Mid Cap: 5000 to 10000
- Mid Cap: 5000 to 20000
- Upper Small Cap: 2000 to 5000
- Lower Small Cap: 500 to 2000
- Small Cap: 500 to 5000
- Micro Cap: < 500

Example: "mid cap stocks" -> {"market_cap_min": 5000, "market_cap_max": 20000}
If user mentions a company by name (e.g. 'like HDFC Bank'), extract that company's metrics as reference values.

Return ONLY a JSON object with a "parsed_filters" key containing the filters, and an optional "reference_company" key if a company was mentioned."""

def _sector_matches(filter_sector: str, yf_sector: str) -> bool:
    """Check if a user's sector term matches the yfinance sector string, using aliases."""
    fs = filter_sector.lower().strip()
    ys = yf_sector.lower().strip()
    # Direct substring match
    if fs in ys or ys in fs:
        return True
    # Alias lookup: map common terms to yfinance sector names
    for alias, targets in _SECTOR_ALIASES.items():
        if alias in fs or fs in alias:
            if any(t in ys or ys in t for t in targets):
                return True
    return False


def _parse_float(val: Any) -> float | None:
    """Safely coerce a filter value (possibly stringified) to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _evaluate_stock(info: dict, filters: dict) -> tuple[bool, str, float]:
    """Evaluate a stock info dictionary against the parsed filters."""
    score = 1.0
    reasons = []

    pe = info.get("trailingPE")
    market_cap = info.get("marketCap")
    # yfinance heldPercentInsiders is 0-1; multiply by 100 for %
    promoter_raw = info.get("heldPercentInsiders")
    promoter_pct = promoter_raw * 100 if promoter_raw is not None else None
    roe_raw = info.get("returnOnEquity")
    roe_pct = roe_raw * 100 if roe_raw is not None else None
    # yfinance debtToEquity is already a ratio (e.g. 0.5 means 50%)
    de = info.get("debtToEquity")
    div_raw = info.get("dividendYield")
    div_pct = div_raw * 100 if div_raw is not None else None
    sector = info.get("sector") or ""

    def _f(key: str) -> float | None:
        return _parse_float(filters.get(key))

    pe_max = _f("pe_max")
    pe_min = _f("pe_min")
    if pe_max is not None and pe is not None:
        if pe > pe_max:
            return False, "", 0.0
        reasons.append(f"PE {pe:.1f} ≤ {pe_max}")
    if pe_min is not None and pe is not None:
        if pe < pe_min:
            return False, "", 0.0
        reasons.append(f"PE {pe:.1f} ≥ {pe_min}")

    promo_min = _f("promoter_holding_min")
    if promo_min is not None and promoter_pct is not None:
        if promoter_pct < promo_min:
            return False, "", 0.0
        reasons.append(f"Promoter {promoter_pct:.1f}% ≥ {promo_min}%")

    roce_min = _f("roce_min")
    roe_min = _f("roe_min")
    effective_roe_min = roce_min if roce_min is not None else roe_min
    if effective_roe_min is not None and roe_pct is not None:
        if roe_pct < effective_roe_min:
            return False, "", 0.0
        reasons.append(f"ROE {roe_pct:.1f}% ≥ {effective_roe_min}%")

    de_max = _f("debt_to_equity_max")
    if de_max is not None and de is not None:
        if de > de_max:
            return False, "", 0.0
        reasons.append(f"D/E {de:.2f} ≤ {de_max}")

    div_min = _f("dividend_yield_min")
    if div_min is not None and div_pct is not None:
        if div_pct < div_min:
            return False, "", 0.0
        reasons.append(f"Div yield {div_pct:.1f}% ≥ {div_min}%")

    cap_min = _f("market_cap_min")
    cap_max = _f("market_cap_max")
    # Filter values are in Crores; yfinance marketCap is in absolute INR
    # 1 Crore = 10^7
    if cap_min is not None and market_cap is not None:
        if market_cap < cap_min * 1e7:
            return False, "", 0.0
        reasons.append(f"MCap > {cap_min:,.0f}Cr")
    if cap_max is not None and market_cap is not None:
        if market_cap > cap_max * 1e7:
            return False, "", 0.0
        reasons.append(f"MCap < {cap_max:,.0f}Cr")

    filter_sector = filters.get("sector") or ""
    if filter_sector and sector:
        if not _sector_matches(filter_sector, sector):
            return False, "", 0.0
        reasons.append(f"Sector: {sector}")

    if not reasons:
        reasons.append("Matches general criteria")

    return True, ", ".join(reasons), score * 100

def process_nl_query(query: str) -> dict[str, Any]:
    cache_key = f"nl_screener_{hash(query)}"
    cached = get("screener", cache_key)
    if cached:
        return cached

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]
    
    try:
        raw_text = deepseek_chat(messages, temperature=0.0)
        json_str = _extract_json_from_text(raw_text)
        parsed_data = json.loads(json_str)
        filters = parsed_data.get("parsed_filters", {})
    except Exception as e:
        logger.error(f"Failed to parse NL query: {e}")
        filters = {}

    # Narrow universe to ~60 stocks when a sector filter is present so yfinance
    # calls stay fast. Without a sector filter use the full NIFTY-50 + Next-50.
    sector_filter = filters.get("sector", "").lower().strip()
    if sector_filter:
        # Use the full universe and let _evaluate_stock do sector filtering
        tickers = _INDIA_STOCK_UNIVERSE
    else:
        # No sector requested — use the first 100 (large + upper-mid cap) for speed
        tickers = _INDIA_STOCK_UNIVERSE[:100]

    import asyncio
    async def fetch_ticker_info(t: str) -> tuple[str, dict]:
        try:
            return t, await asyncio.to_thread(lambda: yf.Ticker(t).info)
        except Exception:
            return t, {}

    async def fetch_all(ts: list[str]):
        tasks = [fetch_ticker_info(t) for t in ts]
        return await asyncio.gather(*tasks)
    
    try:
        # Avoid "asyncio.run() cannot be called from a running event loop"
        # in case router is running in one
        loop = asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
        ticker_infos = loop.run_until_complete(fetch_all(tickers))
    except RuntimeError:
        ticker_infos = asyncio.run(fetch_all(tickers))

    results = []
    for t, info in ticker_infos:
        if not info or "shortName" not in info:
            continue
        
        is_match, reason, score = _evaluate_stock(info, filters)
        if is_match:
            results.append({
                "ticker": t,
                "company": info.get("shortName", t),
                "score": round(score, 1),
                "reason": reason,
                "sector": info.get("sector", "Unknown")
            })
            
    # Sort results by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # Convert all filter values to strings for iOS compatibility
    stringified_filters = {str(k): str(v) for k, v in filters.items()}

    response_data = {
        "parsed_filters": stringified_filters,
        "results": results
    }
    
    set("screener", cache_key, response_data, ttl=3600) # Cache for 1hr
    return response_data
