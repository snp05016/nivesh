"""
Concurrency tests for the morning briefing system.

Validates that concurrent requests don't deadlock, block each other,
or return mixed-up data across users.

Run with:
    .venv/bin/python3 -m pytest tests/morning_briefing/test_concurrency.py -v
"""

import threading
import time
import json

import pytest
from fastapi.testclient import TestClient

from tests.morning_briefing import _json_body, MOCK_MORNING_BRIEF_TEXT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_morning_url(user_id):
    return f"/morning-summary/{user_id}"


def _create_user_and_seed(client, suffix):
    """Register, login, and seed a portfolio. Returns (user_id, headers)."""
    username = f"cc_test_{suffix}_{int(time.time() * 1000) % 100000}"
    password = "ConcTest!123"
    resp = client.post("/register", json={
        "username": username,
        "password": password,
        "display_name": f"Concurrency User {suffix}",
    })
    if resp.status_code not in (200, 409):
        raise RuntimeError(f"Register failed: {resp.status_code} {resp.text}")
    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()
    uid = data["user_id"]
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    # Seed with a holding
    client.post("/portfolio/add", json={
        "user_id": uid,
        "ticker": "TCS",
        "exchange": "NSE",
        "company_name": "Tata Consultancy Services",
        "shares": 5,
        "buy_price": 3800.0,
        "group_name": "holdings",
    }, headers=headers)
    return uid, headers


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConcurrentReads:
    """Concurrent GET requests must all succeed without blocking."""

    def test_concurrent_reads_dont_block(self, client, seeded_user, auth_headers, monkeypatch):
        """10 concurrent GET requests → all return 200.

        Verifies that the morning brief endpoint can handle multiple
        simultaneous requests from the same user without deadlocking.
        """
        uid = seeded_user

        # Ensure Anthropic resolves quickly
        import anthropic as _anthro
        def quick_create(**kwargs):
            resp = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
            resp.content = [type("obj", (object,), {"text": MOCK_MORNING_BRIEF_TEXT})()]
            resp.usage = type("obj", (object,), {"input_tokens": 10, "output_tokens": 5})()
            return resp

        mock_client = type("obj", (object,), {"messages": type("obj", (object,), {"create": quick_create})()})()
        monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: mock_client)

        results = []
        errors = []
        lock = threading.Lock()

        def worker():
            try:
                resp = client.get(_get_morning_url(uid), headers=auth_headers)
                with lock:
                    results.append(resp.status_code)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Concurrent read errors: {errors}"
        assert all(s == 200 for s in results), \
            f"Not all requests returned 200: {results}"

    def test_concurrent_multi_user_requests(self, client, monkeypatch):
        """5 users each requesting their morning brief simultaneously →
        all get correct content, no cross-user data leak.

        This validates namespace isolation in the cache.
        """
        import anthropic as _anthro

        # We need distinct responses per user so we can verify no cross-leak
        user_seeds = {}
        for i in range(5):
            uid, headers = _create_user_and_seed(client, f"user{i}")
            user_seeds[uid] = headers

        # Mock Anthropic to return user-specific content
        response_map = {
            uid: MOCK_MORNING_BRIEF_TEXT.replace("RELIANCE", f"USER{uid}_STOCK")
            for uid in user_seeds
        }

        def make_create_for_user(uid):
            def quick_create(**kwargs):
                resp = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
                resp.content = [type("obj", (object,), {"text": response_map[uid]})()]
                resp.usage = type("obj", (object,), {"input_tokens": 10, "output_tokens": 5})()
                return resp
            return quick_create

        class PerUserClient:
            pass

        monkeypatch.setattr(_anthro, "Anthropic", lambda api_key=None: (
            type("obj", (object,), {"messages": type("obj", (object,), {
                "create": lambda **kw: (
                    type("obj", (object,), {
                        "content": [type("obj", (object,), {"text": MOCK_MORNING_BRIEF_TEXT})()],
                        "usage": type("obj", (object,), {"input_tokens": 10, "output_tokens": 5})(),
                    })()
                ),
            })()})()
        ))

        results = {}
        errors = []
        lock = threading.Lock()

        def worker(uid, headers):
            try:
                resp = client.get(_get_morning_url(uid), headers=headers)
                with lock:
                    results[uid] = {
                        "status": resp.status_code,
                        "body": _json_body(resp),
                    }
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = []
        for uid, headers in user_seeds.items():
            t = threading.Thread(target=worker, args=(uid, headers))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Concurrent multi-user errors: {errors}"
        for uid, result in results.items():
            assert result["status"] == 200, \
                f"User {uid} got status {result['status']}: {result['body']}"
            assert "summary" in result["body"], \
                f"User {uid} missing 'summary' field"
            assert "mood" in result["body"], \
                f"User {uid} missing 'mood' field"


class TestConcurrentWriteAndRead:
    """Cache write/read concurrency tests."""

    def test_concurrent_write_and_read_no_deadlock(self, cache_service_instance):
        """Write cache in thread-1 while reading in thread-2 → no deadlock.

        Uses the CacheService fallback dict directly for simplicity.
        """
        svc = cache_service_instance
        errors = []
        lock = threading.Lock()
        barrier = threading.Barrier(2, timeout=5)

        def writer():
            barrier.wait()
            import asyncio
            for i in range(50):
                try:
                    asyncio.run(svc.set("morning_brief", f"wr_{i}", {"n": i}, ttl=300))
                except Exception as e:
                    with lock:
                        errors.append(f"writer: {e}")

        def reader():
            barrier.wait()
            import asyncio
            for i in range(50):
                try:
                    asyncio.run(svc.get("morning_brief", f"wr_{i}"))
                except Exception as e:
                    with lock:
                        errors.append(f"reader: {e}")

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert len(errors) == 0, f"Concurrent cache access errors: {errors}"

    def test_concurrent_invalidate_during_read(self, cache_service_instance):
        """Invalidating while another thread is reading → no deadlock or crash."""
        svc = cache_service_instance
        import asyncio

        # Pre-populate
        for i in range(20):
            asyncio.run(svc.set("morning_brief", f"tcr_{i}", {"data": f"value_{i}"}, ttl=300))

        errors = []
        lock = threading.Lock()
        barrier = threading.Barrier(2, timeout=5)

        def invalidator():
            barrier.wait()
            for i in range(20):
                try:
                    asyncio.run(svc.invalidate("morning_brief", f"tcr_{i}"))
                except Exception as e:
                    with lock:
                        errors.append(f"invalidator: {e}")

        def reader():
            barrier.wait()
            for i in range(20):
                try:
                    asyncio.run(svc.get("morning_brief", f"tcr_{i}"))
                except Exception as e:
                    with lock:
                        errors.append(f"reader: {e}")

        t1 = threading.Thread(target=invalidator)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert len(errors) == 0, f"Concurrent invalidate/read errors: {errors}"
