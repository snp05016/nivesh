"""REL-08: one supported topology (single uvicorn worker, no --reload) and a scheduler
lock that tells "cannot open the lock file" apart from "another worker holds it"."""
import fcntl
import io
import logging
import re
from pathlib import Path
from unittest.mock import MagicMock

import services.harvest_worker as hw

REPO = Path(__file__).resolve().parents[2]
LAUNCHERS = ["backend/nivesh.service", "backend/Dockerfile", ".github/workflows/deploy.yml"]


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
