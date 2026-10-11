"""TEST-21: the rate limiter stays live but its state is reset between tests.

The middleware counts a request before the route runs, so an invalid /analyze body
(422) still consumes the 10/hour bucket without creating jobs or touching the DB.
"""
from core import rate_limiter


def test_limiter_state_starts_empty():
    assert len(rate_limiter._rate_limit_store) == 0


def test_analyze_limit_is_live_within_one_test(client):
    statuses = [client.post("/analyze", json={}).status_code for _ in range(11)]
    assert 429 not in statuses[:10]
    assert statuses[10] == 429


def test_analyze_bucket_reset_after_previous_test(client):
    # Runs after the test above exhausted the bucket; the conftest fixture must reset it.
    assert client.post("/analyze", json={}).status_code != 429
