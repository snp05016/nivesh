"""GH-614: lower layers must never import the FastAPI app module (main.py).

`from main import ...` inside services/routers re-runs the whole app module in
spawn/forkserver workers and creates an import cycle. Canonical helpers live in
helpers.py; this is a static check so it never imports main itself.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
_SCANNED = [
    *(BACKEND_DIR / d for d in ("services", "routers", "core", "repositories")),
    BACKEND_DIR / "helpers.py",
    BACKEND_DIR / "database.py",
]


def _py_files():
    for target in _SCANNED:
        if target.is_file():
            yield target
        elif target.is_dir():
            yield from sorted(target.rglob("*.py"))


def _main_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "main":
            yield node.lineno
        elif isinstance(node, ast.Import) and any(a.name == "main" for a in node.names):
            yield node.lineno


def test_lower_layers_do_not_import_main():
    offenders = [
        f"{path.relative_to(BACKEND_DIR)}:{line}"
        for path in _py_files()
        for line in _main_imports(path)
    ]
    assert offenders == [], f"import from helpers.py instead of main: {offenders}"


def test_scan_actually_covers_files():
    files = list(_py_files())
    names = {p.name for p in files}
    assert {"orchestrator.py", "copilot_service.py", "brainstorming.py", "market.py"} <= names
