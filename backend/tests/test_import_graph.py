"""REL-15: main.py stays a thin app entry point.

Admin dashboard, health probes, middleware and startup/shutdown live in their own
modules, and nothing under them imports main back. Static scan; nothing is imported.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MAIN = BACKEND_DIR / "main.py"
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "api_route", "route"}


def _imports_main(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "main")
        or (isinstance(node, ast.Import) and any(a.name == "main" for a in node.names))
    ]


def test_main_is_thin():
    assert len(MAIN.read_text(encoding="utf-8").splitlines()) < 400


def test_main_defines_no_routes():
    # Only the global OPTIONS catch-all may stay on `app`; every other route lives in routers/.
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    offenders = [
        f"{fn.name}:{fn.lineno}"
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        for dec in fn.decorator_list
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
        and isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app"
        and dec.func.attr in _HTTP_METHODS
    ]
    assert offenders == [], f"move these routes into a router: {offenders}"


def test_extracted_modules_do_not_import_main():
    files = sorted((BACKEND_DIR / "middleware").rglob("*.py")) + [
        BACKEND_DIR / "core" / "lifecycle.py",
        BACKEND_DIR / "routers" / "admin_dashboard.py",
        BACKEND_DIR / "routers" / "health.py",
        BACKEND_DIR / "services" / "admin_dashboard_service.py",
    ]
    assert len(files) >= 6
    offenders = [f"{p.relative_to(BACKEND_DIR)}:{ln}" for p in files for ln in _imports_main(p)]
    assert offenders == [], offenders
