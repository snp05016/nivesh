"""CMON-26: every backend path the iOS app calls must exist as a FastAPI route.

Static scan of the Swift sources (no simulator, no network): path literals
built on the API base URL, plus `endpoint`/`path` string literals, are
matched against app.routes ignoring the HTTP method. An iOS call to a path
with no route (e.g. the removed GET /api/mutual-funds/{code}/holdings) fails
here instead of 404ing in production.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

IOS_SRC = Path(__file__).resolve().parents[2] / "ios" / "StockApp" / "stockme" / "stockme"

_INTERP = re.compile(r"\\\((?:[^()]|\([^()]*\))*\)")  # Swift "\(expr)", one level of nested parens
_PATH_LITERALS = [
    # "\(baseURL)/watchlist/add", "\(NetworkManager.shared.baseURL)/...", "\(harvesterBaseURL)/..."
    re.compile(r'"\\\((?:NetworkManager\.shared\.)?(?:baseURL|harvesterBaseURL)\)(/[^"]*)"'),
    # let endpoint = "/api/..."; let path = "/..."; static let endpointPath = "/..."
    re.compile(r'\b(?:endpoint|endpointPath|path)\s*=\s*"(/[^"]*)"'),
    # fetch(endpoint: "/api/v1/...") — full paths only; "/\(ticker)/x" fragments get a prefix elsewhere
    re.compile(r'\bendpoint:\s*"(/api/[^"]*)"'),
]


def _ios_paths() -> dict[str, str]:
    """{normalised path: first Swift file using it}; interpolations become {x}."""
    found: dict[str, str] = {}
    for swift in sorted(IOS_SRC.rglob("*.swift")):
        text = swift.read_text(encoding="utf-8")
        for rx in _PATH_LITERALS:
            for m in rx.finditer(text):
                path = _INTERP.sub("{x}", m.group(1)).split("?", 1)[0]
                found.setdefault(path, str(swift.relative_to(IOS_SRC)))
    return found


def _routes() -> list:
    """HTTP routes, minus main.py's CORS catch-all OPTIONS "/{rest_of_path:path}"
    (it matches every path and would make this test vacuous)."""
    from main import app

    return [
        r for r in app.routes
        if hasattr(r, "path_regex") and set(getattr(r, "methods", None) or ()) - {"OPTIONS", "HEAD"}
    ]


def _matches(ios_path: str, routes: list) -> bool:
    probe = ios_path.replace("{x}", "X")
    # An interpolation may stand for one value or a whole sub-path ("\(endpoint)").
    ios_rx = re.compile("^" + ".+".join(re.escape(p) for p in ios_path.split("{x}")) + "/?$")
    for route in routes:
        if route.path_regex.match(probe):
            return True
        if ios_rx.match(route.path):
            return True
    return False


@pytest.mark.skipif(not IOS_SRC.is_dir(), reason="ios/ sources not present")
def test_every_ios_path_has_a_backend_route():
    routes = _routes()
    ios_paths = _ios_paths()
    assert len(ios_paths) > 50, "path extraction found too few iOS calls; regexes out of date?"

    unmatched = sorted(f"{p}  ({src})" for p, src in ios_paths.items() if not _matches(p, routes))
    assert not unmatched, "iOS calls paths with no FastAPI route:\n" + "\n".join(unmatched)


def test_matcher_rejects_unknown_and_accepts_params():
    routes = _routes()
    assert _matches("/watchlist/{x}", routes)
    assert _matches("/watchlist/add", routes)
    assert not _matches("/api/mutual-funds/{x}/holdings/definitely-not-a-route", routes)
