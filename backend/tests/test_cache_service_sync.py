"""ARCH-09 regression: the sync cache path uses one pooled redis-py client.

No thread / event loop per call, REDIS_URL honoured, a dead Redis is skipped
for a backoff window, and the in-process fallback honours per-entry TTLs.
No Redis server is needed: the client methods are patched.
"""
import importlib.util
import os
import threading

import pytest
import redis

import services.cache_service as cs
from services.cache_service import CacheService


def _redis_down(svc, monkeypatch, calls=None):
    """Make every Redis op on svc raise ConnectionError (optionally counting calls)."""
    def _down(*_a, **_k):
        if calls is not None:
            calls.append(1)
        raise redis.ConnectionError("redis down")
    for op in ("get", "set", "delete", "info"):
        monkeypatch.setattr(svc._client, op, _down)


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cs, "_now", lambda: now[0])
    return now


def _load_real_disk_cache():
    """tests/conftest.py swaps services.disk_cache for a MagicMock; load the real file."""
    path = os.path.join(os.path.dirname(cs.__file__), "disk_cache.py")
    spec = importlib.util.spec_from_file_location("_real_disk_cache", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_thread_per_call(monkeypatch):
    svc = CacheService(redis_url="redis://localhost:19999")
    _redis_down(svc, monkeypatch)

    def _no_threads(*_a, **_k):
        raise AssertionError("cache access must not spawn a thread")

    monkeypatch.setattr(threading, "Thread", _no_threads)

    svc.set_sync("ns", "k", {"v": 1}, ttl=60)
    assert svc.get_sync("ns", "k") == {"v": 1}
    svc.invalidate_sync("ns", "k")
    assert svc.get_sync("ns", "k") is None


def test_disk_cache_proxies_to_singleton_without_threads(monkeypatch):
    svc = CacheService(redis_url="redis://localhost:19999")
    _redis_down(svc, monkeypatch)
    monkeypatch.setattr(cs, "cache", svc)
    disk_cache = _load_real_disk_cache()

    def _no_threads(*_a, **_k):
        raise AssertionError("cache access must not spawn a thread")

    monkeypatch.setattr(threading, "Thread", _no_threads)

    disk_cache.set("quick-info", "TCS", {"price": 1.0})
    assert disk_cache.get("quick-info", "TCS") == {"price": 1.0}
    disk_cache.invalidate("quick-info", "TCS")
    assert disk_cache.get("quick-info", "TCS") is None
    assert not hasattr(disk_cache, "purge_expired")


def test_pool_reused(monkeypatch):
    svc = CacheService(redis_url="redis://localhost:19999")
    client, pool = svc._client, svc._client.connection_pool
    seen = []

    def _get(full_key):
        seen.append(full_key)
        return '{"a": 1}'

    monkeypatch.setattr(svc._client, "get", _get)

    assert svc.get_sync("ns", "k") == {"a": 1}
    assert svc.get_sync("ns", "k") == {"a": 1}
    assert seen == ["ns:k", "ns:k"]
    assert svc._client is client
    assert svc._client.connection_pool is pool


def test_redis_url_honoured(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6380/0")
    kwargs = CacheService()._client.connection_pool.connection_kwargs
    assert kwargs["host"] == "example"
    assert kwargs["port"] == 6380


def test_backoff_skips_redis_after_failure(monkeypatch, clock):
    svc = CacheService(redis_url="redis://localhost:19999")
    calls = []
    _redis_down(svc, monkeypatch, calls)

    assert svc.get_sync("ns", "k") is None
    assert len(calls) == 1

    clock[0] += 10  # inside the 30 s backoff
    svc.get_sync("ns", "k")
    svc.set_sync("ns", "k", 1)
    assert len(calls) == 1

    clock[0] += 25  # 35 s after the failure: Redis is retried
    svc.get_sync("ns", "k")
    assert len(calls) == 2


def test_ttl_expiry_in_fallback(monkeypatch, clock):
    svc = CacheService(redis_url="redis://localhost:19999")
    _redis_down(svc, monkeypatch)

    svc.set_sync("morning_brief", "1", "alive", ttl=1)
    assert svc.get_sync("morning_brief", "1") == "alive"

    clock[0] += 2
    assert svc.get_sync("morning_brief", "1") is None


def test_stats_reports_memory_backend_when_redis_down(monkeypatch):
    svc = CacheService(redis_url="redis://localhost:19999")
    _redis_down(svc, monkeypatch)
    svc.set_sync("ns", "k", 1, ttl=60)
    assert svc.stats() == {"backend": "memory", "entries": 1}


def test_fallback_bounded_per_entry(monkeypatch):
    """REL-13: the fallback evicts per entry, not per namespace."""
    svc = CacheService(redis_url="redis://localhost:19999")
    _redis_down(svc, monkeypatch)
    maxsize = int(svc._fallback_cache.maxsize)
    for i in range(maxsize + 500):
        svc.set_sync("ns", f"k{i}", i, ttl=60)
    assert len(svc._fallback_cache) <= maxsize
    assert svc.get_sync("ns", f"k{maxsize + 499}") == maxsize + 499
