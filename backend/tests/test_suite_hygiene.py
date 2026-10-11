"""Suite hygiene: pytest must only collect real tests (#612, #624).

Root-level backend/test_*.py debug scripts ran a paid analyze() and live
Claude/DeepSeek calls at import time, and a bare `pytest` collected them.
File-based checks only: no app import, no network.
"""
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
