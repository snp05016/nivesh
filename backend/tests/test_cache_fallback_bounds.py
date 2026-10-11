"""OPS-18: the no-Redis fallback stays bounded and never serves expired entries,
and the scheduler no longer runs jobs against the removed disk cache.

No Redis server is needed: the client methods are patched to fail.
"""
import os

import redis

import services.cache_service as cs
from services.cache_service import CacheService


def test_single_namespace_bounded_and_expired_not_returned(monkeypatch):
    svc = CacheService(redis_url="redis://localhost:19999")

    def _down(*_a, **_k):
        raise redis.ConnectionError("redis down")

    for op in ("get", "set", "delete", "info"):
        monkeypatch.setattr(svc._client, op, _down)
    now = [1000.0]
    monkeypatch.setattr(cs, "_now", lambda: now[0])

    for i in range(10_000):
        svc.set_sync("stock_history", f"T{i}", i, ttl=60)
    assert len(svc._fallback_cache) <= svc._fallback_cache.maxsize
    assert svc.get_sync("stock_history", "T9999") == 9999

    now[0] += 61
    assert svc.get_sync("stock_history", "T9999") is None


def test_scheduler_has_no_disk_cache_jobs():
    path = os.path.join(os.path.dirname(cs.__file__), "harvest_worker.py")
    src = open(path, encoding="utf-8").read()
    for dead in ("CACHE_ROOT", "purge_expired", "_run_premarket_cache_warm", "_run_cache_purge"):
        assert dead not in src, dead
