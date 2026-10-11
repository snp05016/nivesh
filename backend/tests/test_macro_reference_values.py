"""FAKE-07: macro reference values are never invented.

India VIX is live or null (never a 16.0 "historical average"), and the RBI repo
rate comes from operator config with an as-of date, or is null.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

import routers.market as market_router
import services.scraper as scraper
from config import settings

_BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture
def vix_down(monkeypatch):
    # Every yfinance quote (USD/INR, Brent, ^INDIAVIX) returns no price.
    monkeypatch.setattr(market_router.yf, "Ticker", lambda *_a, **_k: SimpleNamespace(info={}))
    monkeypatch.setattr(scraper, "fetch_market_pulse", lambda: {})


@pytest.fixture
def repo_unset(monkeypatch):
    monkeypatch.setattr(settings, "RBI_REPO_RATE_PCT", None)
    monkeypatch.setattr(settings, "RBI_REPO_RATE_AS_OF", None)
    monkeypatch.setattr(settings, "RBI_POLICY_STANCE", None)


def test_vix_unavailable_not_16(client, vix_down, repo_unset):
    strip = client.get("/macro-strip")
    assert strip.status_code == 200, strip.text
    body = strip.json()
    assert body["india_vix"] is None
    assert body["india_vix_source"] == "unavailable"

    ctx = client.get("/macro-context/TCS")
    assert ctx.status_code == 200, ctx.text
    data = ctx.json()
    assert data["macro_strip"]["india_vix"] is None
    assert data["market_mood"]["score"] is None
    assert data["market_mood"]["zone"] is None


def test_repo_from_config(client, vix_down, monkeypatch):
    monkeypatch.setattr(settings, "RBI_REPO_RATE_PCT", 5.5)
    monkeypatch.setattr(settings, "RBI_REPO_RATE_AS_OF", "2026-08-06")
    monkeypatch.setattr(settings, "RBI_POLICY_STANCE", "Neutral")

    body = client.get("/macro-strip").json()
    assert body["rbi_repo_rate_pct"] == 5.5
    assert body["rbi_repo_rate_as_of"] == "2026-08-06"
    assert body["rbi_source"] == "config"

    data = client.get("/macro-context/HDFCBANK", params={"sector": "Banking"}).json()
    assert data["macro_strip"]["rbi_repo_rate_pct"] == 5.5
    repo_rows = [i for i in data["stock_impact"] if i["factor"] == "RBI Repo Rate"]
    assert repo_rows and repo_rows[0]["value"] == "5.5%"


def test_repo_unset_is_null(client, vix_down, repo_unset):
    body = client.get("/macro-strip").json()
    assert body["rbi_repo_rate_pct"] is None
    assert body["rbi_source"] == "unavailable"

    data = client.get("/macro-context/HDFCBANK", params={"sector": "Banking"}).json()
    assert data["macro_strip"]["rbi_repo_rate_pct"] is None
    assert not [i for i in data["stock_impact"] if i["factor"] == "RBI Repo Rate"]


def test_no_repo_literals():
    for rel in ("routers/market.py", "routers/portfolio.py"):
        src = (_BACKEND / rel).read_text()
        assert "6.50" not in src, rel
        assert '"rbi_repo_rate_pct", 6.5' not in src, rel
        assert "INDIA_VIX_HISTORICAL_AVG" not in src, rel
