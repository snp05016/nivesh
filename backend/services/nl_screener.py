import json
import logging
from typing import Any

from sqlalchemy import or_

from database import get_session
from models.db_models import StockUniverse
from services.llm_utils import deepseek_chat
from helpers import _extract_json_from_text
from services.disk_cache import get as cache_get, set as cache_set

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

def _get_target_sectors(filter_sector: str) -> list[str]:
    """Map a user's sector term to yfinance sector strings, using aliases.
    Only includes the raw term if it exactly matches an alias (not as substring
    to avoid matching 'it' against 'Utilities', 'Healthcare', etc.)."""
    fs = filter_sector.lower().strip()
    targets = []
    for alias, mapped_targets in _SECTOR_ALIASES.items():
        if alias in fs or fs in alias:
            targets.extend(mapped_targets)
    # Only include raw term as a direct match (not ILIKE substring — avoids false positives)
    if not targets:
        targets = [fs]
    return list(set(targets))


def _parse_float(val: Any) -> float | None:
    """Safely coerce a filter value (possibly stringified) to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def process_nl_query(query: str) -> dict[str, Any]:
    cache_key = f"nl_screener_{hash(query)}"
    cached = cache_get("screener", cache_key)
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

    results = []
    
    try:
        with get_session() as session:
            sql_query = session.query(StockUniverse)
            
            # Helper to add filters safely
            def _f(key: str) -> float | None:
                return _parse_float(filters.get(key))

            pe_max = _f("pe_max")
            if pe_max is not None: sql_query = sql_query.filter(StockUniverse.pe_ratio <= pe_max)
            
            pe_min = _f("pe_min")
            if pe_min is not None: sql_query = sql_query.filter(StockUniverse.pe_ratio >= pe_min)

            cap_min = _f("market_cap_min")
            if cap_min is not None: sql_query = sql_query.filter(StockUniverse.market_cap >= cap_min * 1e7)
            
            cap_max = _f("market_cap_max")
            if cap_max is not None: sql_query = sql_query.filter(StockUniverse.market_cap <= cap_max * 1e7)

            promo_min = _f("promoter_holding_min")
            if promo_min is not None: sql_query = sql_query.filter(StockUniverse.promoter_holding >= promo_min)

            fii_min = _f("fii_holding_min")
            if fii_min is not None: sql_query = sql_query.filter(StockUniverse.fii_holding >= fii_min)

            dii_min = _f("dii_holding_min")
            if dii_min is not None: sql_query = sql_query.filter(StockUniverse.dii_holding >= dii_min)

            roce_min = _f("roce_min")
            if roce_min is not None: sql_query = sql_query.filter(StockUniverse.roce >= roce_min)

            roe_min = _f("roe_min")
            if roe_min is not None: sql_query = sql_query.filter(StockUniverse.roe >= roe_min)

            de_max = _f("debt_to_equity_max")
            if de_max is not None: sql_query = sql_query.filter(StockUniverse.debt_to_equity <= de_max)

            div_min = _f("dividend_yield_min")
            if div_min is not None: sql_query = sql_query.filter(StockUniverse.dividend_yield >= div_min)

            ebitda_min = _f("ebitda_margin_min")
            if ebitda_min is not None: sql_query = sql_query.filter(StockUniverse.ebitda_margin >= ebitda_min)

            p3m_min = _f("price_change_3m_min")
            if p3m_min is not None: sql_query = sql_query.filter(StockUniverse.price_change_3m >= p3m_min)

            p1y_min = _f("price_change_1y_min")
            if p1y_min is not None: sql_query = sql_query.filter(StockUniverse.price_change_1y >= p1y_min)

            rsi_min = _f("rsi_min")
            if rsi_min is not None: sql_query = sql_query.filter(StockUniverse.rsi >= rsi_min)

            rsi_max = _f("rsi_max")
            if rsi_max is not None: sql_query = sql_query.filter(StockUniverse.rsi <= rsi_max)

            filter_sector = filters.get("sector")
            if filter_sector:
                targets = _get_target_sectors(str(filter_sector))
                conditions = [StockUniverse.sector.ilike(f"%{t}%") for t in targets]
                sql_query = sql_query.filter(or_(*conditions))
                
            keyword = filters.get("keyword")
            if keyword:
                kw = str(keyword)
                sql_query = sql_query.filter(
                    or_(
                        StockUniverse.company_name.ilike(f"%{kw}%"),
                        StockUniverse.industry.ilike(f"%{kw}%")
                    )
                )

            # Execute the optimized SQL query
            matching_stocks = sql_query.all()
            
            for stock in matching_stocks:
                results.append({
                    "ticker": stock.ticker,
                    "company": stock.company_name or stock.ticker,
                    "score": 100.0,
                    "reason": "Matches Database Criteria",
                    "sector": stock.sector or "Unknown"
                })
    except Exception as e:
        logger.error(f"Database query failed for NL Screener: {e}")

    # Convert all filter values to strings for iOS compatibility
    stringified_filters = {str(k): str(v) for k, v in filters.items()}

    response_data = {
        "parsed_filters": stringified_filters,
        "results": results
    }
    
    cache_set("screener", cache_key, response_data, ttl=3600) # Cache for 1hr
    return response_data
