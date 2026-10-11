"""Single loader for the NSE/BSE stock universe (backend/data/nse_bse_symbols.json).

Every backend consumer (search, advisor-consensus, stock financials) reads the
directory from here instead of embedding its own copy (ARCH-10). The iOS app
bundles a byte copy of the same JSON (scripts/refresh_nse_symbols.py writes both).
"""
import functools
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PATH = Path(__file__).resolve().parent.parent / "data" / "nse_bse_symbols.json"


@functools.lru_cache(maxsize=1)
def entries() -> tuple[dict, ...]:
    """All entries as {ticker, company_name, sector, exchange}, deduped by ticker."""
    try:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("stock_universe: failed to load %s: %s", _PATH, e)
        return ()
    seen: set[str] = set()
    out = []
    for e in raw:
        ticker = e["ticker"]
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append({
            "ticker": ticker,
            "company_name": e["name"],
            "sector": e["sector"],
            "exchange": e.get("exchange", "NSE"),
        })
    return tuple(out)


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    return {e["ticker"]: e for e in entries()}


def by_ticker(ticker: str) -> Optional[dict]:
    return _index().get((ticker or "").strip().upper())


def sector_for(ticker: str, default: str = "Unknown") -> str:
    entry = by_ticker(ticker)
    return entry["sector"] if entry else default
