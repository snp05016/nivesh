"""REL-19: guard the route table against duplicate, shadowed and double-prefixed routes."""
from fastapi.routing import APIRoute

from main import app

_IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _api_routes():
    """(method, path) for every APIRoute, in registration order."""
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in sorted(r.methods - _IGNORED_METHODS):
                out.append((m, r.path))
    return out


def test_no_duplicate_method_path():
    seen = set()
    dups = []
    for key in _api_routes():
        if key in seen:
            dups.append(key)
        seen.add(key)
    assert not dups, f"Duplicate routes (the first registered wins, the rest are dead): {dups}"


def _shadows(earlier: str, later: str) -> bool:
    """True when `earlier` has a {param} segment that would capture `later`'s literal segment."""
    a, b = earlier.split("/"), later.split("/")
    if len(a) != len(b):
        return False
    has_param_over_literal = False
    for x, y in zip(a, b):
        if x == y:
            continue
        if x.startswith("{"):
            if not y.startswith("{"):
                has_param_over_literal = True
            continue
        return False
    return has_param_over_literal


def test_no_param_route_shadows_literal():
    routes = [r for r in _api_routes() if ":path" not in r[1]]
    shadowed = []
    for i, (method, earlier) in enumerate(routes):
        for method2, later in routes[i + 1:]:
            if method2 == method and _shadows(earlier, later):
                shadowed.append((method, earlier, later))
    assert not shadowed, f"Literal routes shadowed by an earlier param route: {shadowed}"


def test_shadow_helper_detects_param_before_literal():
    assert _shadows("/portfolio/{user_id}", "/portfolio/export")
    assert not _shadows("/portfolio/export", "/portfolio/{user_id}")
    assert not _shadows("/alerts/{user_id}", "/alerts/check/{user_id}")


def test_no_double_prefixed_admin_route():
    bad = [p for _, p in _api_routes() if "/api/v1/admin/api/v1/admin" in p]
    assert not bad, f"Double-prefixed admin routes: {bad}"


def test_removed_routes_stay_removed():
    paths = {p for _, p in _api_routes()}
    assert "/api/v1/markets/overview" not in paths
    assert ("POST", "/api/v1/admin/harvest-youtube") in set(_api_routes())
    assert ("GET", "/alerts/check/{user_id}") in set(_api_routes())
