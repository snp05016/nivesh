"""
Nivesh Disk Cache (Replaced by Redis CacheService)
-----------------
This file is now a proxy to services.cache_service.
It provides backward compatibility for sync routes calling get() and set().
"""
from typing import Any, Optional
from services.cache_service import sync_get, sync_set, cache

CACHE_ROOT = "/var/cache/nivesh"  # Dummy for backwards compat

def get(namespace: str, key: str) -> Optional[Any]:
    return sync_get(namespace, key)

def set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    sync_set(namespace, key, value, ttl)

def invalidate(namespace: str, key: str) -> None:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            del cache._fallback_cache[namespace][key]
        return
    loop.run_until_complete(cache.invalidate(namespace, key))

def purge_expired() -> dict:
    return {"deleted": 0, "kept": 0}

def stats() -> dict:
    return {"hits": 0, "misses": 0}
