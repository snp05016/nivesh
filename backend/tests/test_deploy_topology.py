"""REL-08: one supported topology (single uvicorn worker, no --reload) and a scheduler
lock that tells "cannot open the lock file" apart from "another worker holds it"."""
import fcntl
import io
import logging
import os
import re
from pathlib import Path
from unittest.mock import MagicMock

import services.harvest_worker as hw

REPO = Path(__file__).resolve().parents[2]
LAUNCHERS = [
    "backend/nivesh.service", "backend/Dockerfile", ".github/workflows/deploy.yml",
    "scripts/deploy_ml_engine.sh", "scripts/deploy_ml_microservice.sh",
]
# Connections kept free for the scheduler, job subprocesses and admin sessions (PERF-21).
_PG_RESERVE = 10


def test_launch_configs_single_worker():
    for rel in LAUNCHERS:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text()
        assert "--reload" not in text, rel
        for n in re.findall(r'--workers"?,?\s*"?(\d+)', text):
            assert int(n) == 1, f"{rel} runs {n} workers"
    assert "--workers 1" in (REPO / "backend" / "nivesh.service").read_text()
    assert '"--workers", "1"' in (REPO / "backend" / "Dockerfile").read_text()


def test_reload_only_in_marked_local_dev_script():
    """PERF-21: run.sh may use --reload only while it is labelled local-dev-only."""
    text = (REPO / "backend" / "run.sh").read_text()
    if "--reload" in text:
        assert re.search(r"local dev(elopment)? only", text, re.IGNORECASE)


def test_pool_budget_within_pg_limit():
    """PERF-21: workers x (pool_size + max_overflow) + reserve must fit Postgres max_connections."""
    db_src = (REPO / "backend" / "database.py").read_text()
    pool = int(re.search(r"pool_size=(\d+)", db_src).group(1))
    overflow = int(re.search(r"max_overflow=(\d+)", db_src).group(1))
    unit = (REPO / "backend" / "nivesh.service").read_text()
    workers = int(re.search(r"--workers\s+(\d+)", unit).group(1))
    pg_max = int(os.getenv("PG_MAX_CONNECTIONS", "100"))
    assert workers * (pool + overflow) + _PG_RESERVE <= pg_max, (workers, pool, overflow, pg_max)


def _fresh(monkeypatch, opener, lockf):
    built = MagicMock()
    monkeypatch.setattr(hw, "AsyncIOScheduler", built)
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", opener, raising=False)
    monkeypatch.setattr(fcntl, "lockf", lockf)
    return built


def test_unopenable_lock_logs_error_not_other_worker(monkeypatch, caplog):
    def _denied(*_a, **_k):
        raise PermissionError("read-only /tmp")

    built = _fresh(monkeypatch, _denied, MagicMock())
    with caplog.at_level(logging.INFO, logger=hw.__name__):
        assert hw.start_scheduler() is False

    built.assert_not_called()
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors and "Cannot open scheduler lock" in errors[0].getMessage()
    assert "Another worker" not in caplog.text


def test_held_lock_is_reported_as_other_worker(monkeypatch, caplog):
    def _held(*_a, **_k):
        raise BlockingIOError("held")

    built = _fresh(monkeypatch, lambda *_a, **_k: io.StringIO(), _held)
    with caplog.at_level(logging.INFO, logger=hw.__name__):
        assert hw.start_scheduler() is False

    built.assert_not_called()
    assert "Another worker is running the scheduler" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
