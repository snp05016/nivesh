"""ARCH-07 / OPS-04: one uvicorn worker everywhere, and leader-only startup tasks.

Rate limits, the price-alert poller and other singletons live in process memory,
so every deploy artefact must run a single worker without --reload. Even if
someone runs --workers N again, only the scheduler-lock holder starts the alert
poller, the stale-job sweep and the preference backfill.
"""
import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import database
import core.lifecycle as lifecycle
import services.alerts_service
import services.harvest_worker
import services.harvester_db
import core.logging_config

_BACKEND = Path(__file__).resolve().parent.parent


def test_worker_count_consistent():
    service = (_BACKEND / "nivesh.service").read_text()
    dockerfile = (_BACKEND / "Dockerfile").read_text()
    assert re.findall(r"--workers\s+(\d+)", service) == ["1"]
    assert re.findall(r'"--workers",\s*"(\d+)"', dockerfile) == ["1"]
    assert "--reload" not in service
    assert "--reload" not in dockerfile


@pytest.fixture
def startup(monkeypatch):
    """Run core.lifecycle.on_startup with every side effect stubbed; returns the spies."""
    spies = {
        "poller": AsyncMock(),
        "sweep": MagicMock(return_value=0),
        "backfill": MagicMock(),
    }
    monkeypatch.setattr(core.logging_config, "configure_logging", lambda: None)
    monkeypatch.setattr(lifecycle, "init_db", lambda: None)
    monkeypatch.setattr(lifecycle, "_seed_catalogs", lambda: None)
    monkeypatch.setattr(lifecycle, "_backfill_preferences", spies["backfill"])
    monkeypatch.setattr(lifecycle, "_price_alert_task", None)
    monkeypatch.setattr(services.harvester_db, "init_harvester_db", lambda: None)
    monkeypatch.setattr(services.harvest_worker, "_seed_harvester_sources", lambda: None)
    monkeypatch.setattr(services.alerts_service, "price_alert_poller", spies["poller"])
    monkeypatch.setattr(database, "sweep_stale_jobs", spies["sweep"])

    def run(is_leader: bool):
        monkeypatch.delenv("NIVESH_TESTING", raising=False)  # tests are otherwise always leader (DB-13)
        monkeypatch.setattr(lifecycle, "start_scheduler", lambda: is_leader)
        asyncio.run(lifecycle.on_startup())
        return spies

    return run


def test_follower_skips_leader_tasks(startup):
    spies = startup(False)
    spies["poller"].assert_not_called()
    spies["sweep"].assert_not_called()
    spies["backfill"].assert_not_called()
    assert lifecycle._price_alert_task is None


def test_leader_runs_leader_tasks(startup):
    spies = startup(True)
    spies["poller"].assert_called_once_with()
    spies["sweep"].assert_called_once_with(90)
    assert lifecycle._price_alert_task is not None
