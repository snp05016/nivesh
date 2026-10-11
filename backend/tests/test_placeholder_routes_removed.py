"""FAKE-20: /ipo-calendar served a hardcoded 'upcoming' list of IPOs that listed in 2024.

The IPO Hub uses /api/v1/ipo; the markets/compare/stocks stubs are covered by
test_removed_stub_routes.py.
"""
from main import app


def test_ipo_calendar_stub_not_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/ipo-calendar" not in paths


def test_ipo_calendar_stub_removed(client):
    # 405 rather than 404 because main.py's global OPTIONS route matches every path.
    assert client.get("/ipo-calendar").status_code in (404, 405)
