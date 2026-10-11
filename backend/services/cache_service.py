"""Shared cache: Redis (sync redis-py client, pooled) with a bounded in-process
TTLCache fallback when Redis is unreachable.

Sync call sites (services.disk_cache) use get_sync/set_sync/invalidate_sync
directly — no thread or event loop per call (ARCH-09). The async methods are
thin wrappers kept for async callers and tests.
"""
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Optional, TypeVar

import redis
from cachetools import TTLCache


# ── pandas/numpy-safe JSON encoder ──────────────────────────────────────────
# redis-py 5+ validates argument types strictly. Pandas Timestamp / numpy
# scalars fail json.dumps AND fail raw Redis set() calls.
# We provide a custom encoder and a safe-dumps wrapper used everywhere.


class _SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that converts common scientific/ML types to native Python."""

    def default(self, o):
        try:
            import pandas as _pd
            import numpy as _np
            if isinstance(o, (_pd.Timestamp, _pd.Timedelta)):
                return str(o)
            if isinstance(o, _np.integer):
                return int(o)
            if isinstance(o, _np.floating):
                if _np.isnan(o):
                    return None
                return float(o)
            if isinstance(o, _np.ndarray):
                return o.tolist()
        except ImportError:
            pass
        return super().default(o)


def _safe_json_dumps(obj: Any) -> str:
    """Serialize to JSON, handling pandas/numpy types."""
    return json.dumps(obj, cls=_SafeJSONEncoder)


logger = logging.getLogger(__name__)

_REDIS_BACKOFF_S = 30.0  # after a connection error, skip Redis for this long
_DEFAULT_TTL = 600       # namespaces missing from ttl_map
_now = time.monotonic    # indirection so tests can control the clock
_critical_logged = False  # REDIS_URL-set-but-down CRITICAL fires once per process


class CacheService:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        # One pooled client per process; redis-py's client is thread-safe.
        self._client = redis.Redis(
            connection_pool=redis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=1,
            )
        )
        self._down_until = 0.0
        # Fallback: "{ns}:{key}" -> (expiry_monotonic, value). Bounded (Fixes #106).
        self._fallback_cache: TTLCache = TTLCache(maxsize=4096, ttl=86400)
        self._lock = threading.Lock()

        self.ttl_map = {
            "quick-info": 900,   # Fixes #108: matched to settings.QUICK_INFO_TTL
            "sector": 900,
            "analysis": 21600,
            "yfinance": 21600,
            "bhavcopy": 86400,
            "options": 900,
            "news_processed": 43200,
            "morning_brief": 86400,
            "market_pulse": 900,
            "market": 900,
            "asm_gsm": 21600,
            "indices": 300,
            "macro_impact": 3600,
            "ml_signal": 3600,
            "piotroski": 86400,
            "screener": 3600,
            "stock_history": 3600,
            "quote": 60,
            "yf_info": 900,
            "yf_hist": 21600,
        }

    # ── Redis availability ────────────────────────────────────────────────
    def _redis(self) -> Optional[redis.Redis]:
        """The pooled client, or None while in backoff after a failure."""
        return None if _now() < self._down_until else self._client

    def _redis_failed(self, op: str, exc: Exception) -> None:
        global _critical_logged
        if isinstance(exc, redis.RedisError):
            self._down_until = _now() + _REDIS_BACKOFF_S
            # SILENT-11: an explicitly configured Redis that is down means every
            # worker silently keeps its own cache; say so loudly, once per process.
            if os.getenv("REDIS_URL") and not _critical_logged:
                _critical_logged = True
                logger.critical("REDIS_URL configured but Redis unreachable - using per-process memory cache")
        logger.warning(f"Redis {op} error, falling back to memory: {exc}")

    # ── Sync API (used by services.disk_cache) ────────────────────────────
    def get_sync(self, namespace: str, key: str) -> Optional[Any]:
        full_key = f"{namespace}:{key}"
        r = self._redis()
        if r is not None:
            try:
                val = r.get(full_key)
                return json.loads(val) if val else None
            except Exception as e:
                self._redis_failed("get", e)
        with self._lock:
            entry = self._fallback_cache.get(full_key)
            if entry is None:
                return None
            expiry, val = entry
            if _now() < expiry:
                return val
            self._fallback_cache.pop(full_key, None)
        return None

    def set_sync(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        full_key = f"{namespace}:{key}"
        if ttl is None:
            ttl = self.ttl_map.get(namespace, _DEFAULT_TTL)
        r = self._redis()
        if r is not None:
            try:
                r.set(full_key, _safe_json_dumps(value), ex=ttl)
                return
            except Exception as e:
                self._redis_failed("set", e)
        with self._lock:
            self._fallback_cache[full_key] = (_now() + ttl, value)

    def invalidate_sync(self, namespace: str, key: str) -> None:
        full_key = f"{namespace}:{key}"
        r = self._redis()
        if r is not None:
            try:
                r.delete(full_key)
            except Exception as e:
                self._redis_failed("delete", e)
        # Always drop any fallback copy too, so a value cached during an
        # outage cannot resurface after Redis comes back.
        with self._lock:
            self._fallback_cache.pop(full_key, None)

    def stats(self) -> dict:
        r = self._redis()
        if r is not None:
            try:
                info = r.info("stats")
                return {
                    "backend": "redis",
                    "hits": info.get("keyspace_hits", 0),
                    "misses": info.get("keyspace_misses", 0),
                }
            except Exception as e:
                self._redis_failed("info", e)
        with self._lock:
            return {"backend": "memory", "entries": len(self._fallback_cache)}

    # ── Async API (thin wrappers) ─────────────────────────────────────────
    async def get(self, namespace: str, key: str) -> Optional[Any]:
        return self.get_sync(namespace, key)

    async def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.set_sync(namespace, key, value, ttl)

    async def invalidate(self, namespace: str, key: str) -> None:
        self.invalidate_sync(namespace, key)


cache = CacheService()


def sync_get(namespace: str, key: str) -> Optional[Any]:
    return cache.get_sync(namespace, key)


def sync_set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    cache.set_sync(namespace, key, value, ttl)


def stats() -> dict:
    return cache.stats()


_T = TypeVar("_T")
# ponytail: per-process single-flight; cross-worker needs a Redis SET NX lock.
# One lock per in-flight key (refcounted, dropped when idle): striped locks let a
# nested cached_call on a different key (sector/performance -> quote/^CNXIT run
# from a pool thread) land on the held stripe and deadlock.
_SF_GUARD = threading.Lock()
_SF_LOCKS: dict[tuple[str, str], list] = {}  # (namespace, key) -> [Lock, users]


def _sf_enter(k: tuple[str, str]) -> list:
    with _SF_GUARD:
        entry = _SF_LOCKS.get(k)
        if entry is None:
            entry = _SF_LOCKS[k] = [threading.Lock(), 0]
        entry[1] += 1
    entry[0].acquire()
    return entry


def _sf_exit(k: tuple[str, str], entry: list) -> None:
    entry[0].release()
    with _SF_GUARD:
        entry[1] -= 1
        if entry[1] == 0:
            del _SF_LOCKS[k]


def cached_call(
    namespace: str,
    key: str,
    fn: Callable[[], _T],
    ttl: Optional[int] = None,
    cache_if: Callable[[_T], bool] = bool,
    negative_ttl: int = 0,
) -> _T:
    """Cache-aside with single flight: concurrent misses on one key run fn() once.

    A result failing cache_if (empty/partial) is cached only for negative_ttl
    seconds (0 = not at all), so a transient upstream failure is neither
    pinned for the full TTL nor recomputed by every caller.
    """
    hit = cache.get_sync(namespace, key)
    if hit is not None:
        return hit
    k = (namespace, key)
    entry = _sf_enter(k)
    try:
        hit = cache.get_sync(namespace, key)
        if hit is not None:
            return hit
        value = fn()
        if cache_if(value):
            cache.set_sync(namespace, key, value, ttl)
        elif negative_ttl > 0 and value is not None:
            cache.set_sync(namespace, key, value, negative_ttl)
        return value
    finally:
        _sf_exit(k, entry)
