"""Suite hygiene: pytest must only collect real tests (#612, #624).

Root-level backend/test_*.py debug scripts ran a paid analyze() and live
Claude/DeepSeek calls at import time, and a bare `pytest` collected them.
File-based checks only: no app import, no network.
"""
import ast
import configparser
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent


def _testpaths(ini: Path) -> list[str]:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(ini)
    return cfg.get("pytest", "testpaths", fallback="").split()


def test_no_test_scripts_outside_tests_dir():
    assert sorted(p.name for p in BACKEND.glob("test_*.py")) == []
    assert sorted(p.name for p in (BACKEND / "scripts").glob("test_*.py")) == []


def test_pytest_ini_restricts_testpaths():
    assert _testpaths(BACKEND / "pytest.ini") == ["tests"]
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("backend/ deployed without the repo root (e.g. the Docker image)")
    assert _testpaths(REPO_ROOT / "pytest.ini") == ["backend/tests"]


def test_no_absolute_user_paths_in_tests():
    # A hard-coded '/Users/...' sys.path insert shadows modules with another checkout's copy.
    tests = BACKEND / "tests"
    hits = [
        str(p.relative_to(tests))
        for p in tests.rglob("*.py")
        if p.resolve() != Path(__file__).resolve()
        and "/Users/" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == []


_BROAD_EXCEPTIONS = {"Exception", "BaseException", "AssertionError"}


def _swallowed_asserts(tree: ast.AST) -> list[int]:
    """Lines of `try:` blocks holding an assert whose broad handler only passes."""
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(isinstance(n, ast.Assert) for stmt in node.body for n in ast.walk(stmt)):
            continue
        for handler in node.handlers:
            caught = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
            broad = any(
                t is None or (isinstance(t, ast.Name) and t.id in _BROAD_EXCEPTIONS)
                for t in caught
            )
            if broad and all(
                isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                for s in handler.body
            ):
                hits.append(node.lineno)
    return hits


def test_no_swallowed_asserts():
    # TEST-06: `try: assert ... except Exception: pass` can never fail, since
    # AssertionError is an Exception; the generated iOS endpoint tests had 32 of them.
    tests = BACKEND / "tests"
    hits = [
        f"{p.relative_to(tests)}:{line}"
        for p in sorted(tests.rglob("*.py"))
        for line in _swallowed_asserts(ast.parse(p.read_text(encoding="utf-8")))
    ]
    assert hits == []


def test_swallowed_assert_detector():
    assert _swallowed_asserts(ast.parse("try:\n    assert x\nexcept Exception:\n    pass\n")) == [1]
    assert _swallowed_asserts(ast.parse("try:\n    assert x\nexcept:\n    pass\n")) == [1]
    assert _swallowed_asserts(ast.parse("try:\n    assert x\nexcept KeyError:\n    pass\n")) == []
    assert _swallowed_asserts(ast.parse("try:\n    f()\nexcept Exception:\n    pass\n")) == []


def test_backend_ci_runs_whole_suite():
    # TEST-06: CI must run all of backend/tests, not a hand-picked list of files.
    ci = REPO_ROOT / ".github" / "workflows" / "backend_ci.yml"
    if not ci.exists():
        pytest.skip("backend/ deployed without the repo root (e.g. the Docker image)")
    text = ci.read_text(encoding="utf-8")
    assert "python -m pytest backend/tests --collect-only" in text
    assert "python -m pytest backend/tests -q" in text
    assert "pytest backend/tests/" not in text, "CI pytest targets single files"
