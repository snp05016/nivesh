import json
import logging
import yfinance as yf
from typing import Any

from services.llm_utils import deepseek_chat, DEEPSEEK_MODEL
from helpers import _extract_json_from_text
from services.disk_cache import get, set

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You parse natural language stock screening queries into structured filters. Return ONLY valid JSON.
Available filters: sector, industry, pe_max, pe_min, market_cap_min, market_cap_max, promoter_holding_min, fii_holding_min, dii_holding_min, roce_min, roe_min, debt_to_equity_max, ebitda_margin_min, dividend_yield_min, price_change_3m_min, price_change_1y_min, rsi_min, rsi_max, keyword (free text search in company name/description).
If user mentions a company by name (e.g. 'like HDFC Bank'), extract that company's metrics as reference values.

Return ONLY a JSON object with a "parsed_filters" key containing the filters, and an optional "reference_company" key if a company was mentioned."""

def _evaluate_stock(info: dict, filters: dict) -> tuple[bool, str, float]:
    """Evaluate a stock info dictionary against the parsed filters."""
    score = 1.0
    reasons = []
    
    metrics = {
        "pe": info.get("trailingPE"),
        "market_cap": info.get("marketCap"),
        "promoter_holding": info.get("heldPercentInsiders", 0) * 100 if info.get("heldPercentInsiders") else None,
        "roce": info.get("returnOnEquity", 0) * 100 if info.get("returnOnEquity") else None, # using ROE as proxy since yf doesn't always have ROCE
        "debt_to_equity": info.get("debtToEquity", 0) / 100 if info.get("debtToEquity") else None,
        "dividend_yield": info.get("dividendYield", 0) * 100 if info.get("dividendYield") else None,
        "sector": info.get("sector"),
    }
    
    # Evaluate each filter
    if filters.get("pe_max") and metrics["pe"]:
        if metrics["pe"] > filters["pe_max"]: return False, "", 0.0
        reasons.append(f"PE {metrics['pe']:.1f} < {filters['pe_max']}")
        
    if filters.get("pe_min") and metrics["pe"]:
        if metrics["pe"] < filters["pe_min"]: return False, "", 0.0
        reasons.append(f"PE {metrics['pe']:.1f} > {filters['pe_min']}")
        
    if filters.get("promoter_holding_min") and metrics["promoter_holding"]:
        if metrics["promoter_holding"] < filters["promoter_holding_min"]: return False, "", 0.0
        reasons.append(f"Promoter Holding {metrics['promoter_holding']:.1f}% > {filters['promoter_holding_min']}%")
        
    if filters.get("roce_min") and metrics["roce"]:
        if metrics["roce"] < filters["roce_min"]: return False, "", 0.0
        reasons.append(f"ROCE/ROE {metrics['roce']:.1f}% > {filters['roce_min']}%")
        
    if filters.get("debt_to_equity_max") and metrics["debt_to_equity"] is not None:
        if metrics["debt_to_equity"] > filters["debt_to_equity_max"]: return False, "", 0.0
        reasons.append(f"D/E {metrics['debt_to_equity']:.2f} < {filters['debt_to_equity_max']}")

    if filters.get("sector") and metrics["sector"]:
        if filters["sector"].lower() not in metrics["sector"].lower():
            return False, "", 0.0
        reasons.append(f"Sector matches {filters['sector']}")
        
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

    query_parts = ["SELECT ticker FROM stock_universe WHERE 1=1"]
    params = {}
    
    if filters.get("pe_max") is not None:
        query_parts.append("AND pe <= :pe_max")
        params["pe_max"] = filters["pe_max"]
    if filters.get("pe_min") is not None:
        query_parts.append("AND pe >= :pe_min")
        params["pe_min"] = filters["pe_min"]
    if filters.get("market_cap_min") is not None:
        query_parts.append("AND market_cap >= :market_cap_min")
        params["market_cap_min"] = filters["market_cap_min"]
    if filters.get("market_cap_max") is not None:
        query_parts.append("AND market_cap <= :market_cap_max")
        params["market_cap_max"] = filters["market_cap_max"]
    if filters.get("promoter_holding_min") is not None:
        query_parts.append("AND promoter_holding >= :promoter_holding_min")
        params["promoter_holding_min"] = filters["promoter_holding_min"]
    if filters.get("fii_holding_min") is not None:
        query_parts.append("AND fii_holding >= :fii_holding_min")
        params["fii_holding_min"] = filters["fii_holding_min"]
    if filters.get("dii_holding_min") is not None:
        query_parts.append("AND dii_holding >= :dii_holding_min")
        params["dii_holding_min"] = filters["dii_holding_min"]
    if filters.get("roce_min") is not None:
        query_parts.append("AND roce >= :roce_min")
        params["roce_min"] = filters["roce_min"]
    if filters.get("roe_min") is not None:
        query_parts.append("AND roe >= :roe_min")
        params["roe_min"] = filters["roe_min"]
    if filters.get("debt_to_equity_max") is not None:
        query_parts.append("AND debt_to_equity <= :debt_to_equity_max")
        params["debt_to_equity_max"] = filters["debt_to_equity_max"]
    if filters.get("ebitda_margin_min") is not None:
        query_parts.append("AND ebitda_margin >= :ebitda_margin_min")
        params["ebitda_margin_min"] = filters["ebitda_margin_min"]
    if filters.get("dividend_yield_min") is not None:
        query_parts.append("AND dividend_yield >= :dividend_yield_min")
        params["dividend_yield_min"] = filters["dividend_yield_min"]
    if filters.get("price_change_3m_min") is not None:
        query_parts.append("AND price_change_3m >= :price_change_3m_min")
        params["price_change_3m_min"] = filters["price_change_3m_min"]
    if filters.get("price_change_1y_min") is not None:
        query_parts.append("AND price_change_1y >= :price_change_1y_min")
        params["price_change_1y_min"] = filters["price_change_1y_min"]
    if filters.get("rsi_min") is not None:
        query_parts.append("AND rsi >= :rsi_min")
        params["rsi_min"] = filters["rsi_min"]
    if filters.get("rsi_max") is not None:
        query_parts.append("AND rsi <= :rsi_max")
        params["rsi_max"] = filters["rsi_max"]
    if filters.get("sector"):
        query_parts.append("AND LOWER(sector) LIKE :sector")
        params["sector"] = f"%{filters['sector'].lower()}%"
    if filters.get("industry"):
        query_parts.append("AND LOWER(industry) LIKE :industry")
        params["industry"] = f"%{filters['industry'].lower()}%"
    if filters.get("keyword"):
        query_parts.append("AND (LOWER(company_name) LIKE :kw OR LOWER(description) LIKE :kw)")
        params["kw"] = f"%{filters['keyword'].lower()}%"
    
    query_parts.append("ORDER BY market_cap DESC LIMIT 10")
    sql_query = " ".join(query_parts)

    tickers = []
    try:
        from database import get_session
        from sqlalchemy import text
        with get_session() as session:
            rows = session.execute(text(sql_query), params).fetchall()
            tickers = [row[0] for row in rows]
    except Exception as e:
        logger.error(f"DB query failed: {e}")

    # Fallback if DB is empty or fails
    if not tickers:
        tickers = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", 
            "ITC.NS", "SBI.NS", "BHARTIARTL.NS", "SUNPHARMA.NS", "CIPLA.NS", 
            "HINDUNILVR.NS", "BAJFINANCE.NS", "KOTAKBANK.NS", "MARUTI.NS"
        ]
    
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
    
    response_data = {
        "parsed_filters": filters,
        "results": results
    }
    
    set("screener", cache_key, response_data, ttl=3600) # Cache for 1hr
    return response_data
