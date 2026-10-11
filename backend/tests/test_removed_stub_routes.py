"""GH-642: placeholder compare/markets routers stay unmounted until real ones exist."""
from main import app


def test_stub_routes_not_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert not any(p and p.startswith(("/api/v1/compare", "/api/v1/markets")) for p in paths)


def test_markets_overview_stub_removed(client, auth_headers):
    # 405 rather than 404 because main.py's global OPTIONS route matches every path.
    assert client.get("/api/v1/markets/overview", headers=auth_headers).status_code in (404, 405)


def test_compare_stub_removed(client, auth_headers):
    assert client.get("/api/v1/compare/?tickers=TCS", headers=auth_headers).status_code in (404, 405)
