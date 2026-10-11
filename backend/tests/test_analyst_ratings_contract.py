"""CMKT-10: /analyst-ratings always carries buy/hold/sell, which the iOS
AnalystRatingsResponse decodes as non-optional Ints, and reads the current
yfinance recommendations schema (period/strongBuy/buy/hold/sell/strongSell).
"""
from types import SimpleNamespace

import pandas as pd
import pytest

import routers.market as market_router
import services.market_service as market_service


@pytest.fixture
def cache_writes(monkeypatch):
    writes = []
    monkeypatch.setattr(market_router, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(market_router, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(market_router, "_dcache_set",
                        lambda ns, key, value, ttl=None: writes.append(ttl))
    return writes


def _fake_yf(monkeypatch, recommendations: pd.DataFrame, upgrades_downgrades: pd.DataFrame) -> None:
    ticker = SimpleNamespace(recommendations=recommendations, upgrades_downgrades=upgrades_downgrades)
    monkeypatch.setattr(market_service, "yf", SimpleNamespace(Ticker=lambda _sym: ticker))


def test_empty_ratings_has_counts(client, monkeypatch, cache_writes):
    _fake_yf(monkeypatch, pd.DataFrame(), pd.DataFrame())

    resp = client.get("/analyst-ratings", params={"ticker": "TCS"})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ratings": [], "consensus": None, "buy": 0, "hold": 0, "sell": 0}
    assert cache_writes == [900]  # uncovered stocks are re-checked sooner


def test_recommendation_summary_counts(client, monkeypatch, cache_writes):
    recs = pd.DataFrame([
        {"period": "0m", "strongBuy": 5, "buy": 10, "hold": 6, "sell": 2, "strongSell": 1},
        {"period": "-1m", "strongBuy": 1, "buy": 1, "hold": 20, "sell": 0, "strongSell": 0},
    ])
    grades = pd.DataFrame(
        [{"Firm": "Alpha Securities", "ToGrade": "Buy", "FromGrade": "Hold", "Action": "up"},
         {"Firm": "Beta Capital", "ToGrade": "Neutral", "FromGrade": "", "Action": "init"}],
        index=pd.DatetimeIndex(["2026-09-15", "2026-10-02"], name="GradeDate"),
    )
    _fake_yf(monkeypatch, recs, grades)

    resp = client.get("/analyst-ratings", params={"ticker": "TCS"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["buy"], body["hold"], body["sell"]) == (15, 6, 3)
    assert body["consensus"] == "BUY"
    assert body["ratings"] == [
        {"firm": "Beta Capital", "grade": "Neutral", "period": "Oct 2026"},
        {"firm": "Alpha Securities", "grade": "Buy", "period": "Sep 2026"},
    ]
    assert cache_writes == [3600]


@pytest.mark.parametrize("buy, hold, sell, expected", [
    (1, 5, 1, "HOLD"), (0, 1, 4, "SELL"), (3, 3, 0, "HOLD"), (0, 0, 0, None),
])
def test_consensus_rules(monkeypatch, buy, hold, sell, expected):
    recs = pd.DataFrame([{"period": "0m", "strongBuy": 0, "buy": buy, "hold": hold,
                          "sell": sell, "strongSell": 0}])
    _fake_yf(monkeypatch, recs, pd.DataFrame())
    assert market_service.analyst_ratings("TCS.NS")["consensus"] == expected
