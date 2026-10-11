"""ARCH-12: backend/.env is loaded only through core.env.load_backend_env, with
override=False, at process entry points. The real environment (systemd, docker -e)
must win over a stale .env. Static checks; nothing is imported.
The precedence itself is tested in test_test_isolation.py.
"""
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
_OVERRIDE_TRUE = re.compile(r"load_dotenv\([^)]*override\s*=\s*True")


def _backend_py_files():
    yield from sorted(BACKEND.glob("*.py"))
    for d in ("services", "routers", "core", "repositories", "scripts", "migrations"):
        yield from sorted((BACKEND / d).rglob("*.py"))


def _calls(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == name or getattr(n.func, "attr", None) == name)
    )


def test_no_load_dotenv_override_true():
    offenders = [
        p.relative_to(BACKEND).as_posix()
        for p in _backend_py_files()
        if _OVERRIDE_TRUE.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_loader_does_not_override_environment():
    src = (BACKEND / "core" / "env.py").read_text(encoding="utf-8")
    assert "override=False" in src


def test_main_loads_env_exactly_once():
    main = BACKEND / "main.py"
    assert _calls(main, "load_backend_env") == 1
    assert _calls(main, "load_dotenv") == 0


def test_orchestrator_does_not_reload_env():
    assert _calls(BACKEND / "services" / "orchestrator.py", "load_backend_env") == 0


def test_dead_analysis_worker_removed():
    tree = ast.parse((BACKEND / "routers" / "analysis.py").read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_run_analysis_worker" not in names
