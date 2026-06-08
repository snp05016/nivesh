import json
import logging
import time
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
