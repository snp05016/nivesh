"""ARCH-02: default-deny route inventory.

Every route must require auth (require_auth / require_admin / require_user_match
anywhere in its dependency tree, or the legacy in-body require_auth(...) /
require_admin(...) call) unless it is listed in PUBLIC_ROUTES. Known
unauthenticated user-scoped routes sit in KNOWN_GAPS, keyed to the audit item that
fixes them; once fixed, test_known_gaps_are_still_gaps forces the entry out.

A new route that fails here needs Depends(require_auth) (or require_user_match for
a {user_id} route); add it to PUBLIC_ROUTES only for genuinely public data.
"""
import inspect
import re

from fastapi.routing import APIRoute

from core.security import require_admin, require_auth, require_user_match
from main import app

_AUTH_DEPS = {require_auth, require_admin, require_user_match}
_INLINE_AUTH = re.compile(r"\brequire_(?:auth|admin)\(")

PUBLIC_ROUTES = {
    # Infrastructure, CORS preflight and the admin dashboard shell (its data routes need admin).
    ("GET", "/"), ("GET", "/ping"), ("GET", "/api/v1/ping"), ("GET", "/health"),
    ("GET", "/health/live"), ("GET", "/healthz"), ("GET", "/favicon.ico"),
    ("OPTIONS", "/{rest_of_path:path}"),
    # Authentication itself.
    ("POST", "/login"), ("POST", "/register"),
    # Public market data, fundamentals and content.
    ("GET", "/analyst-ratings"), ("GET", "/analyze/cache-status/{ticker}"),
    ("GET", "/api/ipo"), ("GET", "/api/ipo/calendar"), ("GET", "/api/ipo/symbol/{symbol}"),
    ("GET", "/api/ipo/{ipo_id}"), ("GET", "/api/ipo/{ipo_id}/subscription-status"),
    ("GET", "/api/mutual-funds/"), ("GET", "/api/mutual-funds/{scheme_code}"),
    ("GET", "/api/mutual-funds/{scheme_code}/nav-history"),
    ("GET", "/api/v1/earnings/calendar"), ("GET", "/api/v1/earnings/estimates"),
    ("GET", "/api/v1/earnings/feed"), ("GET", "/api/v1/earnings/post-result-movers"),
    ("GET", "/api/v1/earnings/progress"), ("GET", "/api/v1/earnings/surprise-history/{ticker}"),
    ("GET", "/api/v1/earnings/surprises"), ("GET", "/api/v1/earnings/sync-ratio"),
    ("GET", "/api/v1/earnings/yoy-aggregate"),
    ("GET", "/api/v1/expert-posts"), ("GET", "/api/v1/experts"),
    ("GET", "/api/v1/fundamentals/corporate-actions"), ("GET", "/api/v1/fundamentals/financials"),
    ("GET", "/api/v1/fundamentals/shareholding"),
    ("GET", "/api/v1/fundamentals/{ticker}/corporate-actions"),
    ("GET", "/api/v1/fundamentals/{ticker}/financials"),
    ("GET", "/api/v1/fundamentals/{ticker}/shareholding"),
    ("GET", "/fundamentals/{ticker}/corporate-actions"), ("GET", "/fundamentals/{ticker}/financials"),
    ("GET", "/fundamentals/{ticker}/shareholding"), ("GET", "/fundamentals/piotroski/{ticker}"),
    ("GET", "/api/v1/ideas/advisors"), ("GET", "/api/v1/ideas/feed"),
    ("GET", "/api/v1/market/anomalies"), ("GET", "/api/v1/market/dashboard"),
    ("GET", "/api/v1/market/dashboard-pulse"), ("GET", "/api/v1/market/institutional-flow"),
    ("GET", "/api/v1/market/institutional-leaderboard"), ("GET", "/api/v1/market/macro-alternatives"),
    ("GET", "/api/v1/market/momentum"), ("GET", "/api/v1/market/pulse"), ("GET", "/api/v1/market/status"),
    ("GET", "/api/v1/market/stock-history"), ("GET", "/api/v1/market/top-movers"),
    ("GET", "/api/v1/options/chain/{ticker}"), ("GET", "/api/v1/stock-profile"),
    ("GET", "/api/v1/technical-signals"), ("GET", "/block-deals/{ticker}"),
    ("GET", "/dividends/{ticker}"), ("GET", "/earnings-calendar"), ("GET", "/fii-dii-flow"),
    ("GET", "/ipo-calendar"), ("GET", "/macro-context/{ticker}"), ("GET", "/macro-strip"),
    ("GET", "/market-indices"), ("GET", "/market/screener"),
    ("GET", "/market/sentiment-trend/{ticker}"), ("GET", "/mf/{scheme_code}"),
    ("GET", "/nifty-history"), ("GET", "/quarterly-financials"), ("GET", "/quick-info"),
    ("GET", "/screener"), ("GET", "/search"), ("GET", "/sector-performance"),
    ("GET", "/sector-weekly"), ("GET", "/signal-accuracy"),
    # Regulatory documents.
    ("GET", "/api/v1/compliance/disclosures/{key}"), ("GET", "/api/v1/compliance/key-fact-statement"),
    # Stateless calculators and DEMO_MODE-only illustrative catalogs (404 outside demo).
    ("POST", "/portfolio/sip-calculator"), ("POST", "/api/fixed-deposits/calculator"),
    ("GET", "/api/finance/loan-offers"), ("GET", "/api/fixed-deposits/schemes"),
    ("GET", "/api/fixed-deposits/schemes/{scheme_id}"),
    # Optional auth: anonymous callers get the public variant (get_current_user_id).
    ("GET", "/api/v1/home-feed"), ("GET", "/api/forum/boards"),
    ("GET", "/api/forum/boards/{board_id}/threads"), ("GET", "/api/forum/threads/{thread_id}"),
}

# Unauthenticated today; each entry names the audit item that adds auth.
KNOWN_GAPS = {
    ("POST", "/analyze"): "IOSCORE-04/AUTH-08: user_id comes from the request body",
    ("GET", "/analyze/job/{job_id}"): "AUTH-08: opt-in ownership check",
    ("GET", "/analyze/active"): "AUTH-08: client-supplied user_id",
    ("POST", "/analyze/{job_id}/cancel"): "AUTH-08: opt-in ownership check",
    ("POST", "/batch"): "AUTH-08/LLM-02",
    ("POST", "/brainstorm"): "LLM-02: paid LLM, anonymous",
    ("POST", "/api/v1/copilot/chat"): "LLM-02: paid LLM, optional auth",
    ("POST", "/api/v1/screener/natural-language"): "LLM-02/IOSCORE-04",
    ("GET", "/api/v1/earnings/alerts"): "AUTH-10",
    # Bearer is checked inside notifications_service.register_user_device; move it to
    # Depends(require_auth) so the inventory can see it.
    ("POST", "/api/v1/notifications/register"): "ARCH-02 follow-up: service-level bearer check",
}


def _dependency_calls(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependency_calls(dep)


def _is_protected(route: APIRoute) -> bool:
    if any(call in _AUTH_DEPS for call in _dependency_calls(route.dependant)):
        return True
    try:
        source = inspect.getsource(route.endpoint)
    except (OSError, TypeError):
        return False
    return bool(_INLINE_AUTH.search(source))


def _route_keys():
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD"}):
                yield (method, route.path), route


def test_every_route_protected_or_allowlisted():
    unprotected = sorted(
        f"{method} {path}"
        for (method, path), route in _route_keys()
        if (method, path) not in PUBLIC_ROUTES
        and (method, path) not in KNOWN_GAPS
        and not _is_protected(route)
    )
    assert unprotected == [], (
        "Routes without require_auth/require_admin/require_user_match "
        f"(add the dependency, or allowlist genuinely public data): {unprotected}"
    )


def test_known_gaps_are_still_gaps():
    routes = dict(_route_keys())
    stale = sorted(
        f"{method} {path}"
        for (method, path) in KNOWN_GAPS
        if (method, path) not in routes or _is_protected(routes[(method, path)])
    )
    assert stale == [], f"Fixed or removed; delete from KNOWN_GAPS: {stale}"


def test_user_match_routes_return_403_for_another_user(client, auth_headers, test_user_id):
    other = test_user_id + 1_000_000
    assert client.get(f"/portfolio/{other}", headers=auth_headers).status_code == 403
    assert client.get(f"/portfolio/{other}").status_code == 401
    assert client.get(f"/portfolio/{test_user_id}", headers=auth_headers).status_code == 200


def test_body_user_id_mismatch_returns_403(client, auth_headers, test_user_id):
    resp = client.put(
        "/portfolio/update",
        json={"user_id": test_user_id + 1_000_000, "ticker": "RELIANCE", "shares": 1, "buy_price": 100.0},
        headers=auth_headers,
    )
    assert resp.status_code == 403
