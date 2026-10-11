"""
Nivesh Disk Cache (Replaced by Redis CacheService)
-----------------
This file is now a proxy to services.cache_service.
It provides backward compatibility for sync routes calling get() and set().
"""
from typing import Any, Optional
from services import cache_service

# cache_service.cache is looked up at call time so tests can swap the singleton.

def get(namespace: str, key: str) -> Optional[Any]:
    return cache_service.cache.get_sync(namespace, key)

def set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
    cache_service.cache.set_sync(namespace, key, value, ttl)

def invalidate(namespace: str, key: str) -> None:
    cache_service.cache.invalidate_sync(namespace, key)

def stats() -> dict:
    return cache_service.cache.stats()
