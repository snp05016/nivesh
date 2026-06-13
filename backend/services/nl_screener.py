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

    # Map to custom logic by fetching a subset of top NSE tickers to evaluate
    tickers = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", 
        "ITC.NS", "SBI.NS", "BHARTIARTL.NS", "SUNPHARMA.NS", "CIPLA.NS", 
        "HINDUNILVR.NS", "BAJFINANCE.NS", "KOTAKBANK.NS", "MARUTI.NS"
    ]
    
    results = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
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
        except Exception:
            continue
            
    # Sort results by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    response_data = {
        "parsed_filters": filters,
        "results": results
    }
    
    set("screener", cache_key, response_data, ttl=3600) # Cache for 1hr
    return response_data
