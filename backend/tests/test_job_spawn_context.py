"""REL-06: job subprocesses use the spawn start method, never fork.

A forked child of the threaded API process shares its pooled DB/pgvector sockets and
can inherit a lock held by another thread. No test here starts a real process.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import services.job_manager as jm

BACKEND_DIR = Path(__file__).resolve().parent.parent


class _FakeProcess:
    def __init__(self, target, args, daemon):
        self.target, self.args, self.daemon = target, args, daemon
        self.pid = 4242
        self.started = False

    def start(self):
        self.started = True

    def is_alive(self):
        return self.started


def test_mp_ctx_is_spawn():
    assert jm.MP_CTX.get_start_method() == "spawn"


def test_spawn_job_uses_ctx(monkeypatch, real_spawn_job):
    from services.job_worker import run_job

    made = []

    def _process(target, args, daemon):
        made.append(_FakeProcess(target, args, daemon))
        return made[-1]

    monkeypatch.setattr(jm, "MP_CTX", SimpleNamespace(Process=_process))
    monkeypatch.setattr(jm, "_active_jobs", lambda _job_id: [])
    monkeypatch.setattr(jm, "_job_registry", {})

    jm.spawn_job("job-spawn-ctx", "TCS", "NSE", 1, False, "standard")

    assert len(made) == 1
    proc = made[0]
    assert proc.target is run_job and proc.daemon is True and proc.started
    assert proc.args[:3] == ("job-spawn-ctx", "TCS", "NSE")
    assert jm._job_registry["job-spawn-ctx"] is proc


def _raw_mp_uses(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "multiprocessing"
                and node.func.attr in {"Process", "Queue", "Pool"}):
            hits.append(f"{path.name}:{node.lineno} multiprocessing.{node.func.attr}(")
        if (isinstance(node, ast.ImportFrom) and node.module == "multiprocessing"
                and any(a.name in {"Process", "Queue", "Pool"} for a in node.names)):
            hits.append(f"{path.name}:{node.lineno} from multiprocessing import ...")
    return hits


def test_no_raw_multiprocessing_process():
    files = [BACKEND_DIR / "main.py"]
    for sub in ("services", "routers", "repositories", "core"):
        files += sorted((BACKEND_DIR / sub).rglob("*.py"))
    hits = [h for f in files for h in _raw_mp_uses(f)]
    assert not hits, f"start job processes via services.job_manager.spawn_process: {hits}"


def test_spawned_children_configure_logging(monkeypatch):
    """A spawned child does not inherit the parent's root handler (REL-06 follow-up)."""
    import multiprocessing

    import core.logging_config as lc
    import database
    from services.job_worker import run_job

    calls = []
    monkeypatch.setattr(lc, "configure_logging", lambda: calls.append(1))
    monkeypatch.setattr(database, "update_job", lambda *_a, **_k: False)  # stop before paid work

    monkeypatch.setattr(multiprocessing, "parent_process", lambda: None)
    run_job("job-log-parent", "TCS", "NSE", 1, False, "standard")
    assert calls == []  # in-process call keeps the parent's single handler

    monkeypatch.setattr(multiprocessing, "parent_process", lambda: object())
    run_job("job-log-child", "TCS", "NSE", 1, False, "standard")
    assert calls == [1]
