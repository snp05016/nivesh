"""Backend route and API contract coverage for high-risk Nivesh endpoints."""

from __future__ import annotations

import uuid

from main import app
from tests.conftest import REGISTER_CONSENT


CRITICAL_ROUTES = {
    ("POST", "/login"),
    ("POST", "/register"),
    ("POST", "/analyze"),
    ("GET", "/analyze/active"),
    ("GET", "/quick-info"),
    ("GET", "/api/v1/home-feed"),
    ("GET", "/api/v1/technical-signals"),
    ("GET", "/portfolio/{user_id}"),
    ("POST", "/portfolio/add"),
    ("POST", "/portfolio"),
    ("DELETE", "/portfolio/remove"),
    ("PUT", "/portfolio/update"),
    ("PUT", "/portfolio/note"),
    ("POST", "/trade-journal"),
    ("GET", "/trade-journal/{user_id}"),
    ("PUT", "/trade-journal/{entry_id}"),
    ("DELETE", "/trade-journal/{entry_id}"),
    ("GET", "/market-indices"),
    ("GET", "/search"),
    ("GET", "/api/v1/market/stock-history"),
    ("GET", "/api/v1/stock-profile"),
    ("GET", "/api/v1/market/pulse"),
    ("GET", "/api/v1/market/momentum"),
    ("GET", "/api/v1/market/dashboard"),
    ("GET", "/api/v1/earnings/feed"),
    ("GET", "/api/v1/earnings/calendar"),
    ("GET", "/api/v1/earnings/alerts"),
    ("POST", "/api/v1/earnings/alerts"),
    ("POST", "/alerts/add"),
    ("GET", "/alerts/{user_id}"),
    ("DELETE", "/alerts/remove"),
    ("POST", "/watchlist/add"),
    ("GET", "/watchlist/{user_id}"),
    ("DELETE", "/watchlist/remove"),
    ("POST", "/api/v1/copilot/chat"),
    ("POST", "/api/v1/screener/natural-language"),
    ("POST", "/api/v1/portfolio/stress-test"),
    ("GET", "/api/v1/market/sector-rotation"),
    ("GET", "/portfolio/correlation"),
    ("POST", "/api/v1/options/payoff"),
    ("GET", "/harvester/feed"),
    ("GET", "/harvester/governance/{ticker}"),
    ("GET", "/harvester/sources"),
    ("GET", "/harvester/search"),
    ("GET", "/harvester/stats"),
}


def _register_and_login(client, suffix: str) -> tuple[int, dict[str, str]]:
    username = f"audit_{suffix}_{uuid.uuid4().hex[:8]}"
    password = "AuditPass!123"
    register = client.post(
        "/register",
        json={"username": username, "password": password, "display_name": "Audit User", **REGISTER_CONSENT},
    )
    assert register.status_code == 200, register.text

    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def test_critical_route_inventory_matches_current_fastapi_app():
    actual = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if method not in {"HEAD", "OPTIONS"}
    }

    missing = sorted(CRITICAL_ROUTES - actual)
    assert missing == []


def test_openapi_schema_exposes_unprefixed_and_api_v1_route_families(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/login" in paths
    assert "/portfolio/{user_id}" in paths
    assert "/api/v1/stock-profile" in paths
    assert "/api/v1/options/payoff" in paths
    assert paths["/login"]["post"]["tags"] == ["Authentication"]


def test_auth_rejects_invalid_credentials(client):
    response = client.post("/login", json={"username": "missing", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_register_duplicate_username_returns_400(client):
    username = f"dup_{uuid.uuid4().hex[:10]}"
    payload = {"username": username, "password": "AuditPass!123", "display_name": "Duplicate", **REGISTER_CONSENT}
    first = client.post("/register", json=payload)
    second = client.post("/register", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400
    assert "exists" in second.json()["detail"].lower()


def test_portfolio_add_validates_ownership_and_positive_numbers(client):
    user_id, headers = _register_and_login(client, "portfolio")
    other_user_id, other_headers = _register_and_login(client, "other")

    payload = {
        "user_id": user_id,
        "ticker": "TCS",
        "exchange": "NSE",
        "company_name": "Tata Consultancy Services",
        "shares": 0,
        "buy_price": 3500,
    }
    invalid = client.post("/portfolio/add", json=payload, headers=headers)
    # Rejected by schemas.PortfolioAddRequest (shares gt=0) before the handler runs.
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["loc"] == ["body", "shares"]

    cross_user = client.post(
        "/portfolio/add",
        json={**payload, "shares": 2},
        headers=other_headers,
    )
    assert other_user_id != user_id
    assert cross_user.status_code == 403


def test_portfolio_holding_crud_and_duplicate_prevention(client):
    user_id, headers = _register_and_login(client, "holding")
    payload = {
        "user_id": user_id,
        "ticker": "INFY",
        "exchange": "NSE",
        "company_name": "Infosys Ltd",
        "shares": 3,
        "buy_price": 1500.25,
    }

    created = client.post("/portfolio/add", json=payload, headers=headers)
    duplicate = client.post("/portfolio/add", json=payload, headers=headers)
    updated = client.put(
        "/portfolio/update",
        json={"user_id": user_id, "ticker": "INFY", "shares": 4, "buy_price": 1600},
        headers=headers,
    )
    noted = client.put(
        "/portfolio/note",
        json={"user_id": user_id, "ticker": "INFY", "note": "Track margin recovery"},
        headers=headers,
    )
    removed = client.request(
        "DELETE",
        "/portfolio/remove",
        json={"user_id": user_id, "ticker": "INFY"},
        headers=headers,
    )

    assert created.status_code == 200, created.text
    assert created.json()["ticker"] == "INFY"
    assert duplicate.status_code == 409
    assert updated.status_code == 200
    assert noted.status_code == 200
    assert removed.status_code == 200


def test_portfolio_listing_handles_decimal_money_columns(client):
    user_id, headers = _register_and_login(client, "portfolio_list")
    payload = {
        "user_id": user_id,
        "ticker": "INFYLIST",
        "exchange": "NSE",
        "company_name": "Infosys Ltd",
        "shares": 3,
        "buy_price": 1500.25,
    }
    created = client.post("/portfolio/add", json=payload, headers=headers)
    assert created.status_code == 200, created.text

    listed = client.get(f"/portfolio/{user_id}", headers=headers)

    assert listed.status_code == 200, listed.text
    assert any(row["ticker"] == "INFYLIST" for row in listed.json().get("holdings", []))


def test_watchlist_add_uses_documented_sentinel_values(client):
    user_id, headers = _register_and_login(client, "watchlist")
    response = client.post(
        "/watchlist/add",
        json={
            "user_id": user_id,
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "company_name": "Reliance Industries Ltd",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    listed = client.get(f"/watchlist/{user_id}", headers=headers)
    assert listed.status_code == 200
    assert any(row["ticker"] == "RELIANCE" for row in listed.json()["watchlist"])


def test_alert_and_trade_journal_auth_failure_paths(client):
    user_id, headers = _register_and_login(client, "journal")
    other_user_id, other_headers = _register_and_login(client, "journal_other")

    bad_alert = client.post(
        "/alerts/add",
        json={"user_id": user_id, "ticker": "TCS", "target_price": -1, "direction": "above"},
        headers=headers,
    )
    assert bad_alert.status_code == 400

    cross_user_journal = client.post(
        "/trade-journal",
        json={
            "user_id": user_id,
            "ticker": "TCS",
            "action": "BUY",
            "price_at_time": 3500,
            "reason_text": "Entry test",
        },
        headers=other_headers,
    )
    assert other_user_id != user_id
    assert cross_user_journal.status_code == 403


def test_trade_journal_crud_contract(client):
    user_id, headers = _register_and_login(client, "trade")
    created = client.post(
        "/trade-journal",
        json={
            "user_id": user_id,
            "ticker": "HDFCBANK",
            "action": "BUY",
            "price_at_time": 1680.75,
            "reason_text": "Breakout from base",
            "outcome_text": "Pending",
            "company_name": "HDFC Bank Ltd",
            "mood": "disciplined",
        },
        headers=headers,
    )

    assert created.status_code == 200, created.text
    entry_id = created.json()["entry_id"]

    listed = client.get(f"/trade-journal/{user_id}", headers=headers)
    updated = client.put(
        f"/trade-journal/{entry_id}",
        params={"user_id": user_id},
        json={"outcome_text": "Followed plan", "mood": "calm"},
        headers=headers,
    )
    deleted = client.request(
        "DELETE",
        f"/trade-journal/{entry_id}",
        params={"user_id": user_id},
        headers=headers,
    )

    assert listed.status_code == 200
    assert any(row["id"] == entry_id for row in listed.json()["entries"])
    assert updated.status_code == 200
    assert updated.json()["outcome_text"] == "Followed plan"
    assert deleted.status_code == 200
