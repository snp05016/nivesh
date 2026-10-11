"""Task 7 — job_manager spawns into a registry and cancels (terminates + marks CANCELLED)."""
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_table():
    import database
    database.Base.metadata.create_all(database.ENGINE)


class _FakeProc:
    def __init__(self, *a, **k):
        self.pid = 999
        self._alive = True

    def start(self):
        pass

    def is_alive(self):
        return self._alive

    def terminate(self):
        self._alive = False

    def kill(self):
        self._alive = False

    def join(self, *a, **k):
        pass


def test_spawn_registers_and_cancel(monkeypatch, real_spawn_job):
    import database
    import services.job_manager as jm
    job = database.create_job(22_222_221, "TCS", "NSE", "standard")

    monkeypatch.setattr(jm, "MP_CTX", SimpleNamespace(Process=lambda *a, **k: _FakeProc()))
    jm.spawn_job(job["job_id"], "TCS", "NSE", 22_222_221, False, "standard")
    assert job["job_id"] in jm._job_registry

    jm.cancel_job(job["job_id"])
    assert database.get_job(job["job_id"])["status"] == "CANCELLED"
    assert job["job_id"] not in jm._job_registry  # popped on cancel


def test_reap_finished_drops_dead(monkeypatch):
    import services.job_manager as jm
    dead = _FakeProc()
    dead._alive = False
    with jm._registry_lock:
        jm._job_registry["zzz"] = dead  # type: ignore[assignment]
    jm.reap_finished()
    assert "zzz" not in jm._job_registry
