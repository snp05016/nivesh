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


_STOCK_DETAIL = {"price": 2500.0, "vwap": 2490.0, "high_52_week": 3000.0, "low_52_week": 2000.0}


def test_stocks_crud_stub_removed(client, auth_headers):
    # GH-640: the /api/v1/stocks/{ticker} CRUD stub returned success without persisting anything.
    url = "/api/v1/stocks/RELIANCE"
    assert client.get(url, headers=auth_headers).status_code in (404, 405)
    assert client.delete(url, headers=auth_headers).status_code in (404, 405)
    assert client.post(url, json=_STOCK_DETAIL, headers=auth_headers).status_code in (404, 405)
    assert client.put(url, json=_STOCK_DETAIL, headers=auth_headers).status_code in (404, 405)


def test_ml_signal_route_still_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/stocks/{symbol}/ml-signal" in paths
    assert "/api/v1/stocks/{ticker}" not in paths
