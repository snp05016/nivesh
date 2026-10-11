"""Contract: /api/v1/market/dashboard-pulse passes fetch_momentum's lists through (REL-25)."""


def test_dashboard_pulse_returns_scraper_momentum(client, monkeypatch):
    from routers import market

    entry = {
        "ticker": "TCS",
        "last_price": 4000.0,
        "ma20": 3950.0,
        "ma50": 3900.0,
        "sparkline": [1, 2, 3],
        "trend_date": "2026-10-09",
        "crossover": "golden_cross",
    }
    monkeypatch.setattr(market, "fetch_momentum", lambda: {
        "bullish": [entry],
        "bearish": [],
        "fetched_at": "2026-10-09T10:00:00Z",
    })
    monkeypatch.setattr(market, "fetch_market_pulse", lambda: {})
    monkeypatch.setattr(market, "fetch_yoy_aggregate_indicators", lambda: {})
    monkeypatch.setattr(market, "_build_cap_index_grid", lambda: [])

    resp = client.get("/api/v1/market/dashboard-pulse")

    assert resp.status_code == 200
    momentum = resp.json()["momentum"]
    assert momentum["bullish"] == [entry]
    assert momentum["bearish"] == []
    assert momentum["fetched_at"] == "2026-10-09T10:00:00Z"
