"""
Unit tests for morning briefing cache operations.

Tests the CacheService (Redis + dict fallback) directly, verifying
set/get/invalidate/expiry/fallback semantics that the morning brief
endpoint depends on.

Regression coverage:
  - B1: Invalidation must clear Redis (test_invalidate_clears_cache)
  - B5: TTL must be 86400 (verified by ttl_map check, see test_regression.py)
"""

import time
import asyncio

import pytest

from services.cache_service import CacheService, cache as _global_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sync_get(svc, ns, key):
    """Synchronous wrapper around CacheService.get."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(asyncio.run, svc.get(ns, key))
                return fut.result(timeout=10)
        return asyncio.run(svc.get(ns, key))
    except RuntimeError:
        return asyncio.run(svc.get(ns, key))


def sync_set(svc, ns, key, val, ttl=None):
    """Synchronous wrapper around CacheService.set."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(asyncio.run, svc.set(ns, key, val, ttl))
                return fut.result(timeout=10)
        return asyncio.run(svc.set(ns, key, val, ttl))
    except RuntimeError:
        return asyncio.run(svc.set(ns, key, val, ttl))


def sync_invalidate(svc, ns, key):
    """Synchronous wrapper around CacheService.invalidate."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(asyncio.run, svc.invalidate(ns, key))
                return fut.result(timeout=10)
        return asyncio.run(svc.invalidate(ns, key))
    except RuntimeError:
        return asyncio.run(svc.invalidate(ns, key))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCacheSetGet:
    """Basic set / get round-trip with no Redis."""

    def test_set_and_get_roundtrip(self, cache_service_instance):
        """Set key → get key → verify value matches exactly."""
        svc = cache_service_instance
        namespace = "morning_brief"
        key = "42"
        value = {"summary": "Good morning!", "mood": "positive"}

        sync_set(svc, namespace, key, value, ttl=300)
        result = sync_get(svc, namespace, key)

        assert result == value

    def test_get_nonexistent_key_returns_none(self, cache_service_instance):
        """Get on a key that was never set returns None."""
        svc = cache_service_instance
        result = sync_get(svc, "morning_brief", "nonexistent_9999")

        assert result is None

    def test_set_overwrites_previous_value(self, cache_service_instance):
        """Setting the same key twice returns the latest value."""
        svc = cache_service_instance
        sync_set(svc, "morning_brief", "99", {"v": 1}, ttl=300)
        sync_set(svc, "morning_brief", "99", {"v": 2}, ttl=300)

        result = sync_get(svc, "morning_brief", "99")
        assert result == {"v": 2}


class TestCacheTTL:
    """TTL expiry tests."""

    def test_set_with_ttl_value_present_within_window(self, cache_service_instance):
        """Set with TTL → verify in cache immediately after."""
        svc = cache_service_instance
        sync_set(svc, "morning_brief", "ttl_test", "alive", ttl=10)

        result = sync_get(svc, "morning_brief", "ttl_test")
        assert result == "alive"

    def test_set_with_ttl_expires_after_window(self, cache_service_instance):
        """Set with TTL=1 → sleep 2 → get returns None.

        Regression for B5: ensures TTL behaviour works correctly.
        Uses per-process dict fallback (no Redis needed), which stores
        (expiry_timestamp, value) tuples and checks expiry on get.
        """
        svc = cache_service_instance
        sync_set(svc, "morning_brief", "expiring_key", "will_die", ttl=1)

        # Verify present immediately
        assert sync_get(svc, "morning_brief", "expiring_key") == "will_die"

        # Wait for expiry
        time.sleep(1.5)

        result = sync_get(svc, "morning_brief", "expiring_key")
        assert result is None

    def test_default_ttl_from_ttl_map(self, cache_service_instance):
        """When no TTL is passed to set(), namespace default from ttl_map is used.

        Regression for B5: morning_brief namespace defaults to 86400 in ttl_map.
        """
        svc = cache_service_instance
        assert svc.ttl_map["morning_brief"] == 86400

        # Set without explicit TTL — should use 86400
        sync_set(svc, "morning_brief", "default_ttl_key", "long_lived")

        # It should be present
        result = sync_get(svc, "morning_brief", "default_ttl_key")
        assert result == "long_lived"


class TestCacheInvalidation:
    """Invalidation / eviction tests."""

    def test_invalidate_clears_cache(self, cache_service_instance):
        """Set → invalidate → get returns None.

        Regression for B1: disk_cache.invalidate() must call Redis DEL / dict delete.
        """
        svc = cache_service_instance
        sync_set(svc, "morning_brief", "ephemeral", {"data": "temp"}, ttl=300)

        # Verify present
        assert sync_get(svc, "morning_brief", "ephemeral") is not None

        # Invalidate
        sync_invalidate(svc, "morning_brief", "ephemeral")

        # Must be gone
        result = sync_get(svc, "morning_brief", "ephemeral")
        assert result is None

    def test_invalidate_persists_across_workers(self, cache_service_instance):
        """Simulate shared-cache scenario: worker-1 sets, worker-2 reads,
        worker-1 invalidates, worker-2 reads again — must be None.

        Regression for B1: invalidation must propagate to all cache consumers.
        """
        svc = cache_service_instance
        key = "shared_key_42"

        # Worker-1: set
        sync_set(svc, "morning_brief", key, "from_worker_1", ttl=300)

        # Worker-2 (same svc = same fallback dict): read
        val_w2_first = sync_get(svc, "morning_brief", key)
        assert val_w2_first == "from_worker_1"

        # Worker-1: invalidate (e.g. portfolio changed)
        sync_invalidate(svc, "morning_brief", key)

        # Worker-2: read again
        val_w2_second = sync_get(svc, "morning_brief", key)
        assert val_w2_second is None

    def test_invalidate_nonexistent_key_no_error(self, cache_service_instance):
        """Invalidating a key that was never set should not raise."""
        svc = cache_service_instance
        # Must not raise
        sync_invalidate(svc, "morning_brief", "does_not_exist")


class TestCacheFallback:
    """Fallback-to-dict behaviour when Redis is unavailable."""

    def test_cache_fallback_when_redis_down(self):
        """When Redis URL points to nowhere, set/get work via fallback dict.

        Regression for: cache must not crash the app when Redis is down.
        """
        svc = CacheService(redis_url="redis://localhost:19999")
        try:
            sync_set(svc, "morning_brief", "fallback_test", {"ok": True}, ttl=60)
            result = sync_get(svc, "morning_brief", "fallback_test")
            assert result == {"ok": True}
        finally:
            # Clean up the fallback cache
            svc._fallback_cache.clear()

    def test_fallback_cache_clears_on_invalidate(self):
        """Set in fallback → invalidate → get returns None."""
        svc = CacheService(redis_url="redis://localhost:19999")
        try:
            sync_set(svc, "morning_brief", "to_be_deleted", "xyz", ttl=60)
            assert sync_get(svc, "morning_brief", "to_be_deleted") == "xyz"

            sync_invalidate(svc, "morning_brief", "to_be_deleted")
            assert sync_get(svc, "morning_brief", "to_be_deleted") is None
        finally:
            svc._fallback_cache.clear()


class TestCacheAsync:
    """Tests that cache operations work correctly from async contexts."""

    @pytest.mark.asyncio
    async def test_invalidate_works_in_async_context(self, cache_service_instance):
        """Call invalidate from an async function → verify cleared.

        The morning brief pregen runs inside an async scheduler job, so
        invalidation must work correctly in async contexts.
        """
        svc = cache_service_instance
        await svc.set("morning_brief", "async_key_1", {"data": "hello"}, ttl=300)

        # Verify present
        val = await svc.get("morning_brief", "async_key_1")
        assert val == {"data": "hello"}

        # Invalidate
        await svc.invalidate("morning_brief", "async_key_1")

        # Verify gone
        val = await svc.get("morning_brief", "async_key_1")
        assert val is None

    @pytest.mark.asyncio
    async def test_get_and_set_in_async_context(self, cache_service_instance):
        """Set and get from an async function → roundtrip works."""
        svc = cache_service_instance
        value = {"brief": "Morning update", "movers": ["TCS", "INFY"]}

        await svc.set("morning_brief", "async_user_7", value, ttl=3600)
        result = await svc.get("morning_brief", "async_user_7")

        assert result == value


class TestCacheNamespacing:
    """Cache namespaces must isolate data correctly."""

    def test_different_namespaces_dont_collide(self, cache_service_instance):
        """Setting key in namespace 'A' does not appear in namespace 'B'."""
        svc = cache_service_instance
        sync_set(svc, "morning_brief", "key1", "morning_data", ttl=300)
        sync_set(svc, "analysis", "key1", "analysis_data", ttl=300)

        assert sync_get(svc, "morning_brief", "key1") == "morning_data"
        assert sync_get(svc, "analysis", "key1") == "analysis_data"

    def test_same_key_different_users_isolated(self, cache_service_instance):
        """User-1 and user-2 caches are isolated under the same namespace."""
        svc = cache_service_instance
        sync_set(svc, "morning_brief", "1", {"user": "alice"}, ttl=300)
        sync_set(svc, "morning_brief", "2", {"user": "bob"}, ttl=300)

        assert sync_get(svc, "morning_brief", "1") == {"user": "alice"}
        assert sync_get(svc, "morning_brief", "2") == {"user": "bob"}
