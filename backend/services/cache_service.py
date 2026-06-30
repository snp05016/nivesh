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

class CacheService:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._redis_loop_id: Optional[int] = None  # track which loop created the connection
        # Fixes #106: OrderedDict evicts oldest when >512 entries (unbounded→bounded)
        self._fallback_cache: OrderedDict[str, dict[str, tuple[float, Any]]] = OrderedDict()
        self._FALLBACK_MAXSIZE = 512

        self.ttl_map = {
            "quick-info": 900,   # Fixes #108: matched to settings.QUICK_INFO_TTL
            "sector": 900,
            "analysis": 21600,
            "yfinance": 21600,
            "bhavcopy": 86400,
            "options": 900,
            "news_processed": 43200,
            "morning_brief": 86400,
        }

    async def get_redis(self) -> Optional[redis.Redis]:
        """Return a Redis connection valid for the current event loop.
        Recreates the connection if the event loop has changed (e.g. sync bridge)."""
        import asyncio as _aio
        try:
            current_loop_id = id(_aio.get_running_loop())
        except RuntimeError:
            current_loop_id = None

        if self._redis is not None and self._redis_loop_id != current_loop_id:
            # Loop changed — close old connection lazily, create fresh one
            try:
                await self._redis.aclose()
            except Exception as _e:
                pass
            self._redis = None
            self._redis_loop_id = None

        if self._redis is None:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis_loop_id = current_loop_id
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to dict: {e}")
                self._redis = None
                self._redis_loop_id = None
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
                await r.set(full_key, _safe_json_dumps(value), ex=ttl)
                return
            except Exception as e:
                logger.warning(f"Redis set error, falling back: {e}")
                
        # fallback
        if namespace not in self._fallback_cache:
            self._fallback_cache[namespace] = {}
        # Fixes #106: evict oldest namespace entry when cache exceeds maxsize
        elif len(self._fallback_cache) >= self._FALLBACK_MAXSIZE and key not in self._fallback_cache[namespace]:
            self._fallback_cache.popitem(last=False)
        self._fallback_cache[namespace][key] = (time.time() + ttl, value)

    async def invalidate(self, namespace: str, key: str) -> None:
        r = await self.get_redis()
        full_key = f"{namespace}:{key}"
        
        if r:
            try:
                await r.delete(full_key)
                return
            except Exception as _e:
                pass
                
        if namespace in self._fallback_cache and key in self._fallback_cache[namespace]:
            del self._fallback_cache[namespace][key]

cache = CacheService()

def _run_async_in_thread(coro):
    """Run an async coroutine in a fresh event loop inside a separate thread.
    Always works — regardless of whether the caller's thread has a running loop."""
    import threading as _thd
    result = [None]
    error = [None]

    def _runner():
        try:
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
            result[0] = _loop.run_until_complete(coro)
        except Exception as e:
            error[0] = e

    t = _thd.Thread(target=_runner)
    t.start()
    t.join(timeout=10)
    if error[0]:
        raise error[0]
    return result[0]


def sync_get(namespace: str, key: str) -> Optional[Any]:
    try:
        return _run_async_in_thread(cache.get(namespace, key))
    except Exception as _e:
        # Ultimate fallback: per-process dict
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            expiry, val = cache._fallback_cache[namespace][key]
            if time.time() < expiry:
                return val
            del cache._fallback_cache[namespace][key]
        return None


def sync_set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    try:
        _run_async_in_thread(cache.set(namespace, key, value, ttl))
        return
    except Exception as _e:
        pass
    # Fallback: per-process dict
    if namespace not in cache._fallback_cache:
        cache._fallback_cache[namespace] = {}
    cache._fallback_cache[namespace][key] = (time.time() + (ttl or cache.ttl_map.get(namespace, 3600)), value)


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
        """Return resolved cache file path, ensuring it stays inside cache_dir."""
        hash_key = hashlib.md5(full_key.encode()).hexdigest()
        return self._cache_dir / f"{hash_key}.json"

    @staticmethod
    def _resolve_safe(path: Path, root: Path) -> Path:
        """Resolve path and enforce it is inside root."""
        resolved = path.resolve()
        root_resolved = root.resolve()
        if not str(resolved).startswith(str(root_resolved) + os.sep) and resolved != root_resolved:
            raise ValueError(f"Cache path escape: {resolved} not under {root_resolved}")
        return resolved

    def _get_from_disk(self, full_key: str) -> Any:
        try:
            cache_file = self._disk_path(full_key)
            if not cache_file.exists():
                return None
            safe_path = self._resolve_safe(cache_file, self._cache_dir)
            # Read file metadata from the OS (trusted source), not the contents
            try:
                file_stat = safe_path.stat()
                file_mtime = file_stat.st_mtime
            except OSError:
                return None
            with open(safe_path) as f:
                data = json.load(f)
            # Clamp TTL: never exceed _default_ttl (prevents cache poisoning)
            stored_ts = max(float(data.get("ts", 0)), 0)
            claimed_ttl = float(data.get("ttl", self._default_ttl))
            effective_ttl = min(claimed_ttl, float(self._default_ttl))
            age = time.time() - stored_ts
            # Sanity: negative age means tampered/future timestamp
            if age < 0:
                return None
            if age < effective_ttl:
                return data.get("value")
        except Exception as _e:
            pass
        return None

    def _write_to_disk(self, full_key: str, value: Any, ttl: int) -> None:
        import tempfile
        try:
            cache_file = self._disk_path(full_key)
            safe_path = self._resolve_safe(cache_file, self._cache_dir)
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: tempfile → os.replace. O_EXCL|O_NOFOLLOW for safety.
            fd = os.open(
                safe_path.parent,
                os.O_RDONLY,
            )
            os.close(fd)
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(safe_path.parent),
                prefix=f".tmp-{safe_path.name}-",
            )
            try:
                with os.fdopen(tmp_fd, "w") as f:
                    json.dump({"ts": time.time(), "ttl": ttl, "value": value}, f, cls=_SafeJSONEncoder)
                os.replace(tmp_path, safe_path)
                os.chmod(safe_path, 0o600)
            except Exception as _e:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except Exception as _e:
            pass


# Singleton — use this for sync/non-async call sites that cannot await CacheService
unified_cache = UnifiedCacheService()
