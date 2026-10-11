"""ARCH-17: one URL convention for new routes.

New routes go under /api/v1. Unversioned routes that predate the rule are frozen in
fixtures/legacy_unversioned_routes.json ("METHOD /path"); do not add to it. The
money-control routers moved to /api/v1/<name> and keep /api/<name> as deprecated
aliases (hidden from OpenAPI) until the iOS app switches over.
"""
import json
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from main import app

_LEGACY = set(json.loads((Path(__file__).parent / "fixtures" / "legacy_unversioned_routes.json").read_text()))
# Legacy alias prefixes mounted in main.py; delete together with the aliases.
_ALIASES = {"ipo", "mutual-funds", "forum", "finance", "kyc", "me", "fixed-deposits"}


def _alias_name(path):
    """<name> when path is /api/<name> or /api/<name>/... for a money-control alias, else None."""
    parts = path.split("/")
    return parts[2] if len(parts) > 2 and parts[1] == "api" and parts[2] in _ALIASES else None


def _routes():
    """{(method, path): route} for every APIRoute."""
    return {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods - {"HEAD"}
    }


def test_new_routes_are_versioned():
    stray = sorted(
        f"{method} {path}"
        for method, path in _routes()
        if not path.startswith("/api/v1/")
        and f"{method} {path}" not in _LEGACY
        and _alias_name(path) is None
    )
    assert stray == [], f"New routes must live under /api/v1: {stray}"


def test_money_aliases_mirror_v1_routes():
    routes = _routes()
    aliases = {key: route for key, route in routes.items() if _alias_name(key[1])}
    assert {_alias_name(path) for _, path in aliases} == _ALIASES
    for (method, path), route in aliases.items():
        twin = routes.get((method, "/api/v1/" + path[len("/api/"):]))
        assert twin is not None and twin.endpoint is route.endpoint, f"{method} {path} has no /api/v1 twin"
        assert route.deprecated and not route.include_in_schema, f"{method} {path} must be a hidden deprecated alias"


@pytest.mark.parametrize(
    "v1, legacy",
    [("/api/v1/ipo", "/api/ipo"), ("/api/v1/mutual-funds/", "/api/mutual-funds/")],
)
def test_money_routes_dual_mounted(client, v1, legacy):
    new, old = client.get(v1), client.get(legacy)
    assert new.status_code == old.status_code == 200
    assert new.json() == old.json()


def test_openapi_lists_v1_paths_not_aliases():
    paths = app.openapi()["paths"]
    assert [p for p in paths if _alias_name(p)] == []
    assert "/api/v1/ipo" in paths
    assert "/api/v1/finance/loan-offers" in paths
    assert "/api/v1/me/subscription" in paths
