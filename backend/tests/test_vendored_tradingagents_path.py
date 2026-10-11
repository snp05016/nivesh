"""ARCH-23 regression: the vendored tradingagents-core fork has ONE load mechanism.

It used to be loaded both by `pip install -e` (impossible in a clean clone: its
pyproject.toml is git-ignored) and by ad-hoc sys.path inserts in several modules,
so sys.path ordering decided which copy ran. services/orchestrator.py now owns the
only sys.path insert, and the fork's runtime floors live in requirements.txt.
Static checks only: nothing here imports the orchestrator or the fork.
"""
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ORCHESTRATOR = BACKEND / "services" / "orchestrator.py"
SKIP_DIRS = {"tradingagents-core", "tests", "venv", ".venv", "__pycache__"}


def _inserts_vendor_path(tree: ast.AST) -> bool:
    """True when the AST both names "tradingagents-core" and calls sys.path.insert."""
    names_dir = any(
        isinstance(n, ast.Constant) and n.value == "tradingagents-core" for n in ast.walk(tree)
    )
    inserts = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "insert"
        and ast.unparse(n.func.value).endswith("path")
        for n in ast.walk(tree)
    )
    return names_dir and inserts


def _live_tree(path: Path) -> ast.Module:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if path == BACKEND / "routers" / "analysis.py":
        # Dead `_run_analysis_worker` (no callers) is deleted by ARCH-12; ignore it
        # until then so this test does not depend on merge order.
        tree.body = [
            n for n in tree.body
            if not (isinstance(n, ast.FunctionDef) and n.name == "_run_analysis_worker")
        ]
    return tree


def test_only_orchestrator_puts_vendored_fork_on_sys_path():
    offenders = []
    for path in BACKEND.rglob("*.py"):
        if SKIP_DIRS.intersection(path.relative_to(BACKEND).parts):
            continue
        if path != ORCHESTRATOR and _inserts_vendor_path(_live_tree(path)):
            offenders.append(str(path.relative_to(BACKEND)))
    assert offenders == []
    assert _inserts_vendor_path(ast.parse(ORCHESTRATOR.read_text(encoding="utf-8")))


def test_orchestrator_inserts_path_before_importing_tradingagents():
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    insert_line = min(n.lineno for n in tree.body if "sys.path.insert" in ast.unparse(n))
    first_import = min(
        n.lineno for n in tree.body
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("tradingagents")
    )
    assert insert_line < first_import


def _floor(requirement: str) -> tuple[int, ...]:
    text = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    m = re.search(rf"^{re.escape(requirement)}>=([\d.]+)\s*$", text, re.MULTILINE)
    assert m, f"{requirement} floor missing from requirements.txt"
    return tuple(int(p) for p in m.group(1).split("."))


def test_requirements_floors_cover_the_vendored_fork():
    # Floors the fork's own pyproject declares (tradingagents 0.2.5).
    assert _floor("langchain-core") >= (0, 3, 81)
    assert _floor("langgraph") >= (0, 4, 8)
    assert _floor("langchain-anthropic") >= (0, 3, 15)
    text = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    assert "pip install -e ./tradingagents-core" not in text
