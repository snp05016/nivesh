"""Concurrency and failure-mode tests for guarded backend state."""

from __future__ import annotations

import threading
import time

import pytest

from core import concurrency
from services import job_manager


@pytest.fixture(autouse=True)
def clear_analysis_slots():
    with concurrency._running_lock:
        concurrency._running_analyses.clear()
    yield
    with concurrency._running_lock:
        concurrency._running_analyses.clear()


def test_analysis_slot_acquire_is_atomic_for_same_user():
    user_id = 44_001
    barrier = threading.Barrier(8)
    results: list[bool] = []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        acquired = concurrency._acquire_analysis_slot(user_id)
        with lock:
            results.append(acquired)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_stale_analysis_slot_is_evicted(monkeypatch):
    user_id = 44_002
    monkeypatch.setattr(concurrency, "_RUNNING_ANALYSES_STALENESS_SEC", 10)
    with concurrency._running_lock:
        concurrency._running_analyses[user_id] = time.time() - 11

    assert concurrency._acquire_analysis_slot(user_id) is True


def test_release_analysis_slot_is_idempotent():
    user_id = 44_003
    assert concurrency._acquire_analysis_slot(user_id) is True

    concurrency._release_analysis_slot(user_id)
    concurrency._release_analysis_slot(user_id)

    assert concurrency._acquire_analysis_slot(user_id) is True


def test_job_registry_reap_removes_finished_process_handles():
    class DeadProcess:
        def is_alive(self):
            return False

    with job_manager._registry_lock:
        job_manager._job_registry["dead_job"] = DeadProcess()

    job_manager.reap_finished()

    with job_manager._registry_lock:
        assert "dead_job" not in job_manager._job_registry
