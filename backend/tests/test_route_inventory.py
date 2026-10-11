"""TEST-20: every literal request path in backend/tests must hit a route of main.app.

#684 left feature tests probing /api/v1/market/screener, /macro-impact and
/earnings-dashboard, none of which ever existed, and one accepted 404 so it passed
vacuously. Paths are hand-typed, so this test checks them against app.routes.
"""
import ast
from pathlib import Path

from starlette.routing import Match

_TESTS = Path(__file__).resolve().parent
_VERBS = {"get", "post", "put", "patch", "delete", "options"}

# Probes that are meant to miss main.app, one reason each. Keep this list short:
# a test that expects a route to exist must never land here.
INTENTIONAL_404 = {
    ("POST", "/analyze/batch"),  # LLM-03: removed batch route must stay unreachable
    ("GET", "/analyze/batch/abc"),  # LLM-03: same, status endpoint
    ("GET", "/charts/1"),  # public chart mount removed; f-string filename becomes "1"
    ("GET", "/premium"),  # stub FastAPI app built inside test_subscription_compliance_api
    ("GET", "/me"),  # stale: no /me route, the ledger tests skip on it; replace with the login user_id
    ("GET", "/api/v1/portfolio"),  # stale probe in api/test_endpoint_contracts (TEST-09)
}


def _literal_path(node):
    """The path of a str or f-string argument (each {expr} becomes "1"), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value
    elif isinstance(node, ast.JoinedStr):
        text = "".join(str(v.value) if isinstance(v, ast.Constant) else "1" for v in node.values)
    else:
        return None
    return text.split("?", 1)[0] if text.startswith("/") else None


def _request_calls(tree):
    """(line, METHOD, path) for x.get("/...")-style calls; route decorators are skipped."""
    decorators = {
        id(d)
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for d in n.decorator_list
    }
    out = []
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and id(n) not in decorators
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in _VERBS
            and n.args
        ):
            path = _literal_path(n.args[0])
            if path:
                out.append((n.lineno, n.func.attr.upper(), path))
    return sorted(out)


def _all_test_requests():
    """(file:line, METHOD, path) across backend/tests, minus the *_integrity_tests stub apps."""
    out = []
    for f in sorted(_TESTS.rglob("*.py")):
        rel = f.relative_to(_TESTS)
        if any(part.endswith("_integrity_tests") for part in rel.parts):
            continue
        for line, method, path in _request_calls(ast.parse(f.read_text(encoding="utf-8"))):
            out.append((f"{rel}:{line}", method, path))
    return out


def _resolves(app, method, path):
    scope = {"type": "http", "path": path, "method": method, "root_path": ""}
    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return True
        # PARTIAL: the path exists under another method (a 405 probe). main.py's global
        # OPTIONS catch-all is PARTIAL for every path, so it never counts.
        if match == Match.PARTIAL and getattr(route, "methods", None) != {"OPTIONS"}:
            return True
    return False


def test_request_call_extraction():
    src = (
        'c.get("/a/b?x=1")\n'
        'c.post(f"/p/{uid}/q")\n'
        "c.get(url)\n"
        'd.get("key")\n'
        '@stub.get("/stub")\n'
        "def f():\n"
        "    pass\n"
    )
    assert _request_calls(ast.parse(src)) == [(1, "GET", "/a/b"), (2, "POST", "/p/1/q")]


def test_all_test_request_paths_exist():
    from main import app

    requests = _all_test_requests()
    assert len(requests) > 200, "extractor found too few request calls; it is probably broken"
    missing = [
        f"{where} {method} {path}"
        for where, method, path in requests
        if (method, path) not in INTENTIONAL_404 and not _resolves(app, method, path)
    ]
    assert not missing, "Tests call routes that main.app does not register:\n" + "\n".join(missing)


def test_intentional_404_entries_really_miss():
    from main import app

    hit = sorted(f"{m} {p}" for m, p in INTENTIONAL_404 if _resolves(app, m, p))
    assert not hit, f"INTENTIONAL_404 entries now match a route; drop them: {hit}"
