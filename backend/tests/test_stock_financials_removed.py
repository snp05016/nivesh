"""FAKE-04 / GH-188: the seeded-random stock_financials router (invented statements,
shareholding and SEBI-investigation 'risk signals') is unmounted and deleted; only
its ml-signal endpoint survives, in routers/ml_signal.py."""
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from main import app

_ROUTERS = Path(__file__).resolve().parent.parent / "routers"
_GENERATOR_SUFFIXES = ("financials", "shareholding", "corporate-actions", "valuation", "risk-signals")


@pytest.mark.parametrize("suffix", _GENERATOR_SUFFIXES)
def test_generator_routes_gone(client, auth_headers, suffix):
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert f"/api/v1/stocks/{{symbol}}/{suffix}" not in paths
    # 405 rather than 404 because main.py's global OPTIONS route matches every path.
    resp = client.get(f"/api/v1/stocks/HDFCBANK/{suffix}", headers=auth_headers)
    assert resp.status_code in (404, 405), resp.text


def test_ml_signal_still_routed():
    routes = [
        r for r in app.routes
        if isinstance(r, APIRoute) and r.path == "/api/v1/stocks/{symbol}/ml-signal"
    ]
    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == "routers.ml_signal"
    assert routes[0].methods == {"GET"}


def test_no_fabricated_allegations():
    assert not (_ROUTERS / "stock_financials.py").exists()
    for path in _ROUTERS.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "SEBI Investigation" not in src, path.name
        assert "_seeded_random" not in src, path.name
