"""
Nivesh Disk Cache (Replaced by Redis CacheService)
-----------------
This file is now a proxy to services.cache_service.
It provides backward compatibility for sync routes calling get() and set().
"""
from typing import Any, Optional
from services.cache_service import sync_get, sync_set, cache, _run_async_in_thread

CACHE_ROOT = "/var/cache/nivesh"  # Dummy for backwards compat

def get(namespace: str, key: str) -> Optional[Any]:
    return sync_get(namespace, key)

def set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    sync_set(namespace, key, value, ttl)

def invalidate(namespace: str, key: str) -> None:
    try:
        _run_async_in_thread(cache.invalidate(namespace, key))
    except Exception:
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            del cache._fallback_cache[namespace][key]

def purge_expired() -> dict:
    return {"deleted": 0, "kept": 0}

def stats() -> dict:
    return {"hits": 0, "misses": 0}
