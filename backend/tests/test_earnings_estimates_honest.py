"""FAKE-10: earnings 'estimates' are consensus figures or null.

TTM actual revenue (totalRevenue) and 12-month forward EPS are not quarterly
estimates, and LLM snapshot fields are not reported actuals.
"""
import routers.market as market_router


def test_estimates_do_not_substitute_actuals(client, monkeypatch):
    monkeypatch.setattr(
        market_router, "_yf_fetch_info",
        lambda _sym: {"totalRevenue": 9.6e12, "forwardEps": 120.0, "longName": "Reliance"},
    )
    resp = client.get("/api/v1/earnings/estimates", params={"ticker": "RELIANCE"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["company_name"] == "Reliance"
    assert body["revenue_estimate"] is None
    assert body["eps_estimate"] is None
    for key in ("revenue_actual", "net_profit_actual", "eps_actual", "net_profit_estimate"):
        assert body[key] is None, key
    assert "degraded" not in body


def test_genuine_revenue_estimate_is_kept(client, monkeypatch):
    monkeypatch.setattr(
        market_router, "_yf_fetch_info",
        lambda _sym: {"revenueEstimate": 2.5e11, "longName": "Reliance"},
    )
    body = client.get("/api/v1/earnings/estimates", params={"ticker": "RELIANCE"}).json()
    assert body["revenue_estimate"] == 2.5e11 / 1e7
