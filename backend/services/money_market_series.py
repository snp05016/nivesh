"""Market series from the research engine for money features (journal scores, 31-Jan-2018 FMV).

Both lookups return ``{key: result}`` or None when the engine cannot answer (no key, error,
timeout); callers treat None as "unavailable", never as zero. Final results are cached for
7 days; pending ones are not. User-visible numbers are shown only while ``display_allowed()``.
Nothing here calls an LLM.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, Optional

from repositories.research_repo import normalize_symbol
from services import disk_cache
from services.research import config as research_config
from services.research.client import MLEngineClient, MLEngineError

logger = logging.getLogger(__name__)

CHUNK = 1000
CACHE_NS = "money_series"
CACHE_TTL = 7 * 86400
BENCHMARK_LABEL = "Nifty 50 price index (excludes dividends)"


def display_allowed() -> bool:
    """True only while the research engine is fully on (Stage 3, licence confirmed)."""
    try:
        return research_config.CONFIG.mode == "on"
    except Exception:
        return False


def _client() -> Optional[MLEngineClient]:
    cfg = research_config.CONFIG
    if not cfg.ml_engine_api_key:
        return None
    return MLEngineClient()


def _clean(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    if out.get("symbol"):
        out["symbol"] = normalize_symbol(out["symbol"])
    for field in ("start", "date"):
        if isinstance(out.get(field), date):
            out[field] = out[field].isoformat()
    return out


def _cache_key(item: dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()


def _lookup(
    items: Sequence[dict[str, Any]],
    call: Callable[[MLEngineClient, list[dict[str, Any]]], dict[str, Any]],
) -> Optional[dict[str, dict[str, Any]]]:
    try:
        cleaned = [_clean(i) for i in items]
        results: dict[str, dict[str, Any]] = {}
        todo: list[dict[str, Any]] = []
        for item in cleaned:
            hit = disk_cache.get(CACHE_NS, _cache_key(item))
            if isinstance(hit, dict):
                results[item["key"]] = hit
            else:
                todo.append(item)
        if todo:
            client = _client()
            if client is None:
                return None
            for i in range(0, len(todo), CHUNK):
                chunk = todo[i:i + CHUNK]
                by_key = {r["key"]: r for r in call(client, chunk).get("results") or [] if isinstance(r, dict) and "key" in r}
                for item in chunk:
                    res = by_key.get(item["key"])
                    if res is None:
                        continue
                    results[item["key"]] = res
                    if res.get("status") != "pending":
                        disk_cache.set(CACHE_NS, _cache_key(item), res, ttl=CACHE_TTL)
        return results
    except MLEngineError as exc:
        logger.warning("money_market_series engine error: %s", type(exc).__name__)
    except Exception as exc:
        logger.warning("money_market_series failed: %s", type(exc).__name__)
    return None


def window_returns(items: Sequence[dict[str, Any]]) -> Optional[dict[str, dict[str, Any]]]:
    """Stock and Nifty 50 return over ``sessions`` from ``start`` per item key (engine /series/window-returns)."""
    return _lookup(items, lambda c, chunk: c.series_window_returns(chunk))


def raw_highs(items: Sequence[dict[str, Any]]) -> Optional[dict[str, dict[str, Any]]]:
    """Raw high and close on or just before ``date`` per item key (engine /series/raw-high)."""
    return _lookup(items, lambda c, chunk: c.series_raw_highs(chunk))
