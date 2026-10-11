"""ARCH-13: lower layers (services, core, repositories, helpers, database) never
import routers. Upward imports drag the FastAPI router modules (scraper, options,
yfinance) into workers and unit tests. `from main import` is covered by
test_no_main_imports.py. Static scan; nothing is imported.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
_SCANNED = [
    *(BACKEND_DIR / d for d in ("services", "core", "repositories")),
    BACKEND_DIR / "helpers.py",
    BACKEND_DIR / "database.py",
]

# Edges owned by another fix; remove the entry when it lands.
_KNOWN = {
    "services/user_service.py",  # GH-651: morning_summary_endpoint -> a service
}


def _py_files():
    for target in _SCANNED:
        if target.is_file():
            yield target
        elif target.is_dir():
            yield from sorted(target.rglob("*.py"))


def _is_routers(name: str | None) -> bool:
    return bool(name) and (name == "routers" or name.startswith("routers."))


def _router_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):  # includes function-level imports
        if isinstance(node, ast.ImportFrom) and node.level == 0 and _is_routers(node.module):
            yield node.lineno
        elif isinstance(node, ast.Import) and any(_is_routers(a.name) for a in node.names):
            yield node.lineno


def test_lower_layers_do_not_import_routers():
    offenders = [
        f"{rel}:{line}"
        for path in _py_files()
        if (rel := path.relative_to(BACKEND_DIR).as_posix()) not in _KNOWN
        for line in _router_imports(path)
    ]
    assert offenders == [], f"move the shared code into services/ instead: {offenders}"


def test_scan_covers_moved_edges():
    names = {p.name for p in _py_files()}
    assert {"sector_rotation.py", "earnings_surprise.py", "market_service.py"} <= names
