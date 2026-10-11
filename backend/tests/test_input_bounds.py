"""REL-23: numeric query params, list bodies and param-keyed caches are bounded.

Out-of-range values return 422 instead of being processed (huge `days` used to
overflow timedelta into a 500), nifty-history caches per bucket instead of per
raw `days`, and oversized request bodies are refused with 413.
"""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import routers.market as market
from helpers import BatchAnalyzeRequest
from routers.strategy import BacktestRequest


@pytest.mark.parametrize("path", [
    "/nifty-history?days=0",
    "/nifty-history?days=1000000000",
    "/api/v1/expert-posts?limit=0",
    "/api/v1/expert-posts?limit=-1",
    "/search?q=tc&limit=1000000000",
    "/market/sentiment-trend/TCS?days=100000",
])
def test_query_bounds_422(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("path", [
    "/api/v1/notifications?limit=1000",
    "/api/v1/notifications?limit=0",
    "/api/v1/portfolio/valuation-history?user_id={uid}&days=1000000000",
    "/portfolio/history/{uid}?days=0",
])
def test_authed_query_bounds_422(client, auth_headers, test_user_id, path):
    resp = client.get(path.format(uid=test_user_id), headers=auth_headers)
    assert resp.status_code == 422, resp.text


def test_batch_tickers_max():
    with pytest.raises(ValidationError):
        BatchAnalyzeRequest(tickers=["TCS"] * 21)


def test_backtest_years_bound():
    with pytest.raises(ValidationError):
        BacktestRequest(ticker="TCS", strategy_id="x", years=500)
    assert BacktestRequest(ticker="TCS", strategy_id="x").years == 5


def test_body_too_large_413(client):
    resp = client.post("/login", content=b"x" * 1_048_577,
                       headers={"content-type": "application/json"})
    assert resp.status_code == 413


def test_nifty_history_bucket_cache_key(client, monkeypatch):
    today = datetime.now(timezone.utc).date()
    recent = (today - timedelta(days=10)).isoformat()
    older = (today - timedelta(days=250)).isoformat()
    payload = {"prices": [{"date": older, "close": 1.0}, {"date": recent, "close": 2.0}]}
    keys = []

    def _get(ns, key):
        keys.append((ns, key))
        return payload

    monkeypatch.setattr(market, "_dcache_get", _get)

    short = client.get("/nifty-history?days=200")
    long = client.get("/nifty-history?days=300")

    assert short.status_code == long.status_code == 200
    assert keys == [("market", "nifty_history_365"), ("market", "nifty_history_365")]
    # Each response is trimmed to the requested window.
    assert [p["date"] for p in short.json()["prices"]] == [recent]
    assert [p["date"] for p in long.json()["prices"]] == [older, recent]
