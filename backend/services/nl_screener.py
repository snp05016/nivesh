import hashlib
import json
import logging
import operator
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

Example: "mid cap stocks" -> {"parsed_filters": {"market_cap_min": 5000, "market_cap_max": 20000}}
Return ONLY a JSON object with a "parsed_filters" key containing the filters."""

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


class NLQueryUnavailable(Exception):
    """The LLM call failed (outage, quota, timeout); the query was never parsed."""


class NLQueryNotUnderstood(Exception):
    """The LLM reply had no usable filter, so there is nothing to screen on."""


# Numeric filters: key -> (column, comparison, multiplier applied to the parsed value).
# Market cap is parsed in Crores and stored in absolute INR (1 Cr = 1e7).
_NUMERIC_FILTERS: dict[str, tuple[Any, Any, float]] = {
    "pe_max": (StockUniverse.pe_ratio, operator.le, 1),
    "pe_min": (StockUniverse.pe_ratio, operator.ge, 1),
    "market_cap_min": (StockUniverse.market_cap, operator.ge, 1e7),
    "market_cap_max": (StockUniverse.market_cap, operator.le, 1e7),
    "promoter_holding_min": (StockUniverse.promoter_holding, operator.ge, 1),
    "fii_holding_min": (StockUniverse.fii_holding, operator.ge, 1),
    "dii_holding_min": (StockUniverse.dii_holding, operator.ge, 1),
    "roce_min": (StockUniverse.roce, operator.ge, 1),
    "roe_min": (StockUniverse.roe, operator.ge, 1),
    "debt_to_equity_max": (StockUniverse.debt_to_equity, operator.le, 1),
    "dividend_yield_min": (StockUniverse.dividend_yield, operator.ge, 1),
    "ebitda_margin_min": (StockUniverse.ebitda_margin, operator.ge, 1),
    "price_change_3m_min": (StockUniverse.price_change_3m, operator.ge, 1),
    "price_change_1y_min": (StockUniverse.price_change_1y, operator.ge, 1),
    "rsi_min": (StockUniverse.rsi, operator.ge, 1),
    "rsi_max": (StockUniverse.rsi, operator.le, 1),
}

_MAX_RESULTS = 100


def _cache_key(query: str) -> str:
    """Process-independent key: builtin hash() of a str is salted per process."""
    return "nl_screener_" + hashlib.sha256(query.strip().lower().encode()).hexdigest()


def _build_conditions(filters: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    """Turn parsed filters into SQL conditions; also return the filters actually applied."""
    conditions: list[Any] = []
    applied: dict[str, Any] = {}

    for key, (column, compare, scale) in _NUMERIC_FILTERS.items():
        value = _parse_float(filters.get(key))
        if value is not None:
            conditions.append(compare(column, value * scale))
            applied[key] = filters[key]

    filter_sector = filters.get("sector")
    if filter_sector:
        targets = _get_target_sectors(str(filter_sector))
        conditions.append(or_(*[StockUniverse.sector.ilike(f"%{t}%") for t in targets]))
        applied["sector"] = filter_sector

    industry = filters.get("industry")
    if industry:
        conditions.append(StockUniverse.industry.ilike(f"%{industry}%"))
        applied["industry"] = industry

    keyword = filters.get("keyword")
    if keyword:
        kw = str(keyword)
        conditions.append(or_(
            StockUniverse.company_name.ilike(f"%{kw}%"),
            StockUniverse.industry.ilike(f"%{kw}%"),
        ))
        applied["keyword"] = keyword

    return conditions, applied


def process_nl_query(query: str) -> dict[str, Any]:
    if not query.strip():
        raise NLQueryNotUnderstood("empty query")

    cache_key = _cache_key(query)
    cached = cache_get("screener", cache_key)
    if cached:
        return cached

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

    try:
        raw_text = deepseek_chat(messages, temperature=0.0)
    except Exception as e:
        logger.error(f"NL screener LLM call failed: {e}")
        raise NLQueryUnavailable(str(e)) from e

    try:
        parsed_data = json.loads(_extract_json_from_text(raw_text))
        filters = parsed_data.get("parsed_filters", {})
    except Exception as e:
        logger.warning(f"Failed to parse NL query: {e}")
        raise NLQueryNotUnderstood(str(e)) from e
    if not isinstance(filters, dict):
        raise NLQueryNotUnderstood("parsed_filters is not an object")

    conditions, applied = _build_conditions(filters)
    if not applied:
        # No recognised filter: screening would return the whole universe as "matches".
        raise NLQueryNotUnderstood(f"no supported filter in {sorted(filters)}")

    try:
        with get_session() as session:
            matching_stocks = (
                session.query(StockUniverse)
                .filter(*conditions)
                .order_by(StockUniverse.market_cap.desc().nullslast())
                .limit(_MAX_RESULTS)
                .all()
            )
    except Exception as e:
        logger.error(f"Database query failed for NL Screener: {e}")
        raise

    # Every returned row satisfies every applied filter, so 100 is exact, not a placeholder.
    reason = f"Matches all {len(applied)} parsed filters"
    results = [
        {
            "ticker": stock.ticker,
            "company": stock.company_name or stock.ticker,
            "score": 100.0,
            "reason": reason,
            "sector": stock.sector or "Unknown",
        }
        for stock in matching_stocks
    ]

    # Only report filters that were applied; values are strings for iOS compatibility.
    response_data = {
        "parsed_filters": {str(k): str(v) for k, v in applied.items()},
        "results": results
    }

    cache_set("screener", cache_key, response_data, ttl=3600) # Cache for 1hr
    return response_data
