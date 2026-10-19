"""TEST-09: behavioural auth matrix generated from app.routes.

test_route_auth_inventory.py proves statically that every route outside PUBLIC_ROUTES
carries an auth dependency or an in-body require_auth/require_admin call. This file
sends the requests: every such route must turn away an anonymous and a forged-token
caller, and every user-scoped GET must refuse another user's id. KNOWN_GAPS routes are
strict xfails, so fixing one fails here until its entry is removed.
"""
import re

import pytest
from fastapi.routing import APIRoute

from core.security import require_admin, require_auth
from main import app
from services import feature_flags
from tests.test_route_auth_inventory import KNOWN_GAPS, PUBLIC_ROUTES

_PATH_PARAM = re.compile(r"\{[^}]+\}")
_AUTH_DEPS = {require_auth, require_admin}
# Serves the caller's own stats whatever the path id says, so it never leaks another user's data.
_IGNORES_PATH_USER_ID = {"/trade-journal/{user_id}/stats"}


def _collect_routes():
    routes = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD"}):
                routes.setdefault((method, route.path), route)  # first match wins, as in Starlette
    return routes


_ROUTES = _collect_routes()


@pytest.fixture(autouse=True)
def _focus_flags_on(monkeypatch):
    """I04: the forum and IPO hub are off by default and their flag gate answers 404 before
    auth runs, so turn them on here to prove the auth checks behind the gate."""
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    monkeypatch.setenv("NIVESH_FLAG_IPO_HUB", "true")
    feature_flags._reset_cache()
    yield
    feature_flags._reset_cache()


def _has_auth_dependency(dependant) -> bool:
    return any(dep.call in _AUTH_DEPS or _has_auth_dependency(dep) for dep in dependant.dependencies)


def _accepted_statuses(key, route):
    if key in KNOWN_GAPS or _has_auth_dependency(route.dependant):
        return {401, 403}
    d = route.dependant
    if any(f.field_info.is_required() for f in d.query_params + d.header_params + d.body_params):
        # An in-body require_auth(...) runs only after FastAPI validates the query/body,
        # so a bare request stops at 422; the static inventory proves the call is there.
        return {401, 403, 422}
    return {401, 403}


def _case(key):
    marks = [pytest.mark.xfail(strict=True, reason=KNOWN_GAPS[key])] if key in KNOWN_GAPS else []
    return pytest.param(*key, marks=marks, id=f"{key[0]} {key[1]}")


@pytest.mark.parametrize(
    "method,path", [_case(key) for key in sorted(_ROUTES) if key not in PUBLIC_ROUTES]
)
def test_protected_route_rejects_anonymous_and_forged_token(client, monkeypatch, method, path):
    # Demo-only routers answer 404 before auth when DEMO_MODE is off.
    monkeypatch.setattr("config.settings.DEMO_MODE", True)
    accepted = _accepted_statuses((method, path), _ROUTES[(method, path)])
    url = _PATH_PARAM.sub("1", path)
    for headers in ({}, {"Authorization": "Bearer invalid.token.x"}):
        resp = client.request(method, url, headers=headers)
        assert resp.status_code in accepted, (
            f"{method} {url} with {headers or 'no token'} -> {resp.status_code}: {resp.text[:200]}"
        )


_USER_SCOPED_GETS = sorted(
    path
    for (method, path) in _ROUTES
    if method == "GET"
    and "{user_id}" in path
    and (method, path) not in PUBLIC_ROUTES
    and (method, path) not in KNOWN_GAPS
    and path not in _IGNORES_PATH_USER_ID
)


@pytest.mark.parametrize("path", _USER_SCOPED_GETS)
def test_user_scoped_get_rejects_other_users_id(client, auth_headers, test_user_id, path):
    url = _PATH_PARAM.sub("1", path.replace("{user_id}", str(test_user_id + 1_000_000)))
    resp = client.get(url, headers=auth_headers)
    assert resp.status_code in (403, 404), f"GET {url} -> {resp.status_code}: {resp.text[:200]}"
