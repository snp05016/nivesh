"""PERF-20: advisor-consensus does no dead analysis_history scan, bounds `days`
and serves repeat calls from the cache.

Uses the conftest sqlite test DB; services.disk_cache is a MagicMock there, so
the cache helpers bound in routers.advisor_consensus are patched per test.
"""
from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy import event

import database

_URL = "/api/v1/portfolio/advisor-consensus"


@contextmanager
def _capture_sql():
    statements: list[str] = []

    def _before(conn, cursor, statement, params, context, executemany):
        statements.append(statement.lower())

    event.listen(database.ENGINE, "before_cursor_execute", _before)
    try:
        yield statements
    finally:
        event.remove(database.ENGINE, "before_cursor_execute", _before)


def test_no_analysis_history_query(client, auth_headers):
    with patch("routers.advisor_consensus._dcache_get", return_value=None), \
            patch("routers.advisor_consensus._dcache_set"), _capture_sql() as sql:
        resp = client.get(f"{_URL}?days=7", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert any("advisor_insights" in s for s in sql), sql
    assert not any("analysis_history" in s for s in sql), sql


def test_days_bounded(client, auth_headers):
    with patch("routers.advisor_consensus._dcache_get", return_value=None), \
            patch("routers.advisor_consensus._dcache_set"):
        assert client.get(f"{_URL}?days=100000", headers=auth_headers).status_code == 422
        assert client.get(f"{_URL}?days=0", headers=auth_headers).status_code == 422
        assert client.get(f"{_URL}?days=30", headers=auth_headers).status_code == 200


def test_result_cached_per_window(client, auth_headers):
    store: dict = {}

    def _get(ns, key):
        return store.get((ns, key))

    def _set(ns, key, value, ttl=None):
        store[(ns, key)] = value

    with patch("routers.advisor_consensus._dcache_get", side_effect=_get), \
            patch("routers.advisor_consensus._dcache_set", side_effect=_set) as setter:
        first = client.get(f"{_URL}?days=5", headers=auth_headers)
        assert first.status_code == 200, first.text
        assert setter.call_args.kwargs["ttl"] == 600
        with _capture_sql() as sql:
            second = client.get(f"{_URL}?days=5", headers=auth_headers)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert not any("advisor_insights" in s for s in sql), sql
