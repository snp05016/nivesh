"""Existence check for LLM-emitted tickers against the instrument universe (LLM-21).

LLMs suggest stale, renamed or foreign symbols (HDFC after its merger, AAPL). Every
sanitizer that passes an LLM ticker to the user runs it through validate_tickers.
"""
import time
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from repositories.research_repo import normalize_symbol

_TTL_SECONDS = 3600
_cache: dict = {"symbols": None, "at": 0.0}


def _universe(session: Optional[Session] = None) -> set[str]:
    """Normalised stock_universe tickers; the static NSE list while the table is empty.

    Memoised for an hour when read through get_session (session=None).
    """
    if session is None:
        if _cache["symbols"] is not None and time.monotonic() - _cache["at"] < _TTL_SECONDS:
            return _cache["symbols"]
        from database import get_session
        with get_session() as s:
            symbols = _universe(s)
        _cache.update(symbols=symbols, at=time.monotonic())
        return symbols

    from models.db_models import StockUniverse
    symbols = {normalize_symbol(t) for (t,) in session.query(StockUniverse.ticker).all()} - {""}
    if not symbols:
        from services.yfinance_client import NSE_TICKERS
        symbols = {normalize_symbol(t) for t in NSE_TICKERS}
    return symbols


def validate_tickers(symbols: Iterable[object], session: Optional[Session] = None) -> tuple[list[str], list[str]]:
    """Split symbols into (valid, invalid), both normalised ('reliance.ns' -> 'RELIANCE'),
    deduplicated and in input order. Blank entries are dropped."""
    universe = _universe(session)
    valid: list[str] = []
    invalid: list[str] = []
    for raw in symbols:
        sym = normalize_symbol(str(raw) if raw is not None else "")
        if not sym or sym in valid or sym in invalid:
            continue
        (valid if sym in universe else invalid).append(sym)
    return valid, invalid
