import json
import logging
import time
import hashlib
import threading
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional
import redis.asyncio as redis
import asyncio

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._fallback_cache: dict[str, dict[str, tuple[float, Any]]] = {}
        
        self.ttl_map = {
            "quick-info": 300,
            "sector": 900,
            "analysis": 21600,
            "yfinance": 21600,
            "bhavcopy": 86400,
            "options": 900,
            "news_processed": 43200,
            "morning_brief": 86400,
        }

    async def get_redis(self) -> Optional[redis.Redis]:
        if self._redis is None:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to dict: {e}")
                self._redis = None
        return self._redis

    async def get(self, namespace: str, key: str) -> Optional[Any]:
        r = await self.get_redis()
        full_key = f"{namespace}:{key}"
        
        if r:
            try:
                val = await r.get(full_key)
                if val:
                    return json.loads(val)
                return None
            except Exception as e:
                logger.warning(f"Redis get error, falling back: {e}")
                
        # fallback
        if namespace in self._fallback_cache and key in self._fallback_cache[namespace]:
            expiry, val = self._fallback_cache[namespace][key]
            if time.time() < expiry:
                return val
            else:
                del self._fallback_cache[namespace][key]
        return None

    async def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        r = await self.get_redis()
        full_key = f"{namespace}:{key}"
        
        if ttl is None:
            ttl = self.ttl_map.get(namespace, 3600)
            
        if r:
            try:
                await r.set(full_key, json.dumps(value), ex=ttl)
                return
            except Exception as e:
                logger.warning(f"Redis set error, falling back: {e}")
                
        # fallback
        if namespace not in self._fallback_cache:
            self._fallback_cache[namespace] = {}
        self._fallback_cache[namespace][key] = (time.time() + ttl, value)

    async def invalidate(self, namespace: str, key: str) -> None:
        r = await self.get_redis()
        full_key = f"{namespace}:{key}"
        
        if r:
            try:
                await r.delete(full_key)
                return
            except Exception:
                pass
                
        if namespace in self._fallback_cache and key in self._fallback_cache[namespace]:
            del self._fallback_cache[namespace][key]

cache = CacheService()

def sync_get(namespace: str, key: str) -> Optional[Any]:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        # Fallback to dict if we are in a running loop and cannot await
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            expiry, val = cache._fallback_cache[namespace][key]
            if time.time() < expiry:
                return val
            del cache._fallback_cache[namespace][key]
        return None
    return loop.run_until_complete(cache.get(namespace, key))

def sync_set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        if namespace not in cache._fallback_cache:
            cache._fallback_cache[namespace] = {}
        cache._fallback_cache[namespace][key] = (time.time() + (ttl or cache.ttl_map.get(namespace, 3600)), value)
        return
    loop.run_until_complete(cache.set(namespace, key, value, ttl))


# ─────────────────────────────────────────────────────────────────────────────
# UnifiedCacheService — consolidates disk/memory/DB cache fragmentation
# (rank_59) — sync interface, no Redis dependency required
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedCacheService:
    """Single sync interface for all caching needs.

    Lookup order: memory (LRU) → disk (JSON files) → None.
    Writes always populate memory; disk persistence is optional via
    ``persist=True`` on set().
    """

    def __init__(
        self,
        cache_dir: str = None,
        memory_maxsize: int = 256,
        default_ttl: int = 3600,
    ):
        self._memory: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._maxsize = memory_maxsize
        self._default_ttl = default_ttl
        self._cache_dir = Path(cache_dir or os.getenv("CACHE_DIR", "cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, namespace: str = "default") -> Any:
        """Get from memory first, then disk. Returns None on miss or expiry."""
        full_key = self._make_key(namespace, key)

        with self._lock:
            if full_key in self._memory:
                value, ts, ttl = self._memory[full_key]
                if time.monotonic() - ts < ttl:
                    self._memory.move_to_end(full_key)
                    return value
                del self._memory[full_key]

        return self._get_from_disk(full_key)

    def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: int = None,
        persist: bool = False,
    ) -> None:
        """Store in memory LRU. Optionally persist to disk."""
        full_key = self._make_key(namespace, key)
        effective_ttl = ttl if ttl is not None else self._default_ttl

        with self._lock:
            self._memory[full_key] = (value, time.monotonic(), effective_ttl)
            self._memory.move_to_end(full_key)
            while len(self._memory) > self._maxsize:
                self._memory.popitem(last=False)

        if persist:
            self._write_to_disk(full_key, value, effective_ttl)

    def delete(self, key: str, namespace: str = "default") -> None:
        """Evict from memory (disk file left to TTL-expire naturally)."""
        full_key = self._make_key(namespace, key)
        with self._lock:
            self._memory.pop(full_key, None)

    def clear_namespace(self, namespace: str) -> int:
        """Evict all memory entries belonging to namespace. Returns count."""
        prefix = f"{namespace}:"
        with self._lock:
            keys_to_del = [k for k in self._memory if k.startswith(prefix)]
            for k in keys_to_del:
                del self._memory[k]
        return len(keys_to_del)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def _disk_path(self, full_key: str) -> Path:
        hash_key = hashlib.md5(full_key.encode()).hexdigest()
        return self._cache_dir / f"{hash_key}.json"

    def _get_from_disk(self, full_key: str) -> Any:
        try:
            cache_file = self._disk_path(full_key)
            if cache_file.exists():
                with open(cache_file) as f:
                    data = json.load(f)
                age = time.time() - data.get("ts", 0)
                if age < data.get("ttl", self._default_ttl):
                    return data.get("value")
        except Exception:
            pass
        return None

    def _write_to_disk(self, full_key: str, value: Any, ttl: int) -> None:
        try:
            cache_file = self._disk_path(full_key)
            with open(cache_file, "w") as f:
                json.dump({"ts": time.time(), "ttl": ttl, "value": value}, f)
        except Exception:
            pass


# Singleton — use this for sync/non-async call sites that cannot await CacheService
unified_cache = UnifiedCacheService()
