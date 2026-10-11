"""FAKE-08: earnings reporting progress is never fabricated.

/earnings/progress used to count the app's own analyses over a hardcoded 50;
sync-ratio and dashboard-pulse must not turn a missing count into numbers.
"""
import routers.earnings as earnings_router
import routers.market as market_router


def test_progress_is_unavailable(client):
    resp = client.get("/api/v1/earnings/progress")
    assert resp.status_code == 503
    assert "reported" not in resp.text


def test_sync_ratio_without_declared_count_is_503(client, monkeypatch):
    monkeypatch.setattr(
        earnings_router, "fetch_earnings_sync_ratio",
        lambda: {"declared_count": None, "total_expected": 5042, "source": "unavailable"},
    )
    resp = client.get("/api/v1/earnings/sync-ratio")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Results-declared count unavailable"


def test_dashboard_pulse_has_no_live_reporting_sync(client, monkeypatch):
    monkeypatch.setattr(market_router, "fetch_market_pulse", lambda: {})
    monkeypatch.setattr(market_router, "fetch_momentum", lambda: {})
    monkeypatch.setattr(market_router, "fetch_yoy_aggregate_indicators", lambda: {})
    monkeypatch.setattr(market_router, "_build_cap_index_grid", lambda: [])
    resp = client.get("/api/v1/market/dashboard-pulse")
    assert resp.status_code == 200, resp.text
    assert resp.json()["live_reporting_sync"] is None
