"""GH-695: every response, not just /api/*, must carry no-store cache headers."""


def test_legacy_route_has_no_store(client):
    resp = client.get("/watchlist/999999")
    assert resp.status_code == 401
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["pragma"] == "no-cache"


def test_ping_has_no_store(client):
    assert client.get("/ping").headers["cache-control"] == "no-store, private"


def test_api_route_still_no_store(client):
    resp = client.get("/api/finance/accounts")
    assert resp.status_code == 401
    assert resp.headers["cache-control"] == "no-store, private"
