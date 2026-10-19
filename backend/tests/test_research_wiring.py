"""Research Engine wiring (spec 2.6, 2.7, 6.6, 11.2; REL-12).

- The job registration in ``harvest_worker.start_scheduler`` is guarded and
  runs before ``_scheduler.start()`` (AST, nothing is executed).
- ``main.app`` mounts the research router once and the legacy gate.
- With an invalid research config the app still serves: research answers 404
  ``RESEARCH_DISABLED`` and ``/healthz`` reports ``research.degraded`` with 200.
- The ``/healthz`` research block (no_run_for_last_weekday, ml-engine /ready
  reasons) never changes the overall status.

Hermetic: conftest's temp SQLite app DB, a per-test in-memory DB for the
block's own ledger reads, a fake ml-engine client; no network.
"""

from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routers.health as health_router
from main import app
from models.db_models import Base, ResearchRun  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
from services.research import config
from services.research import health as research_health_mod
from services.research.client import MLEngineClient
from services.research.templates import LEGACY_GONE_TEXT

BACKEND = Path(__file__).resolve().parents[1]
HARVEST_WORKER = BACKEND / "services" / "harvest_worker.py"

FRI, MON = date(2026, 10, 9), date(2026, 10, 12)
TUE_0800_IST = datetime(2026, 10, 13, 2, 30, tzinfo=timezone.utc)
TUE_0700_IST = datetime(2026, 10, 13, 1, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Scheduler guard (AST)
# ---------------------------------------------------------------------------

def _start_scheduler() -> ast.FunctionDef:
    tree = ast.parse(HARVEST_WORKER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "start_scheduler":
            return node
    raise AssertionError("start_scheduler() not found in harvest_worker.py")


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == name) or (isinstance(f, ast.Attribute) and f.attr == name):
                out.append(n)
    return out


def test_register_research_jobs_is_guarded_and_precedes_start():
    fn = _start_scheduler()
    guarded = [
        stmt for stmt in fn.body
        if isinstance(stmt, ast.Try) and any(_calls(s, "register_research_jobs") for s in stmt.body)
    ]
    assert len(guarded) == 1, "register_research_jobs must be called inside one top-level try in start_scheduler"
    try_node = guarded[0]
    assert any(
        isinstance(h.type, ast.Name) and h.type.id == "Exception" for h in try_node.handlers
    ), "the try around register_research_jobs needs an `except Exception` handler"
    # Every call is inside that try: an unguarded one elsewhere would defeat it.
    assert len(_calls(fn, "register_research_jobs")) == len(
        [c for s in try_node.body for c in _calls(s, "register_research_jobs")]
    )

    starts = [
        c for c in _calls(fn, "start")
        if isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id == "_scheduler"
    ]
    assert starts, "_scheduler.start() not found"
    assert try_node.lineno < min(c.lineno for c in starts)


# ---------------------------------------------------------------------------
# main.app wiring
# ---------------------------------------------------------------------------

def test_research_router_mounted_once():
    paths = [r.path for r in app.routes if isinstance(r, APIRoute) and "GET" in r.methods]
    assert paths.count("/api/v1/research/stocks/{symbol}") == 1
    assert paths.count("/api/v1/research/admin/status") == 1


def test_legacy_gate_mounted(client):
    resp = client.post("/analyze/batch", json={"tickers": ["RELIANCE"]})
    assert resp.status_code == 410
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text == LEGACY_GONE_TEXT


# ---------------------------------------------------------------------------
# Invalid config: research fails closed, the app keeps serving
# ---------------------------------------------------------------------------

@pytest.fixture()
def no_dependencies(monkeypatch):
    """/healthz probes: no ml-engine /health, no Redis ping."""
    monkeypatch.setattr(health_router, "_ml_engine_ok", lambda: True)
    monkeypatch.setattr(health_router, "_redis_ok", lambda: True)


@pytest.fixture()
def bad_config(monkeypatch):
    """RESEARCH_ENGINE_MODE=on without ML_ENGINE_API_KEY, reloaded from the env."""
    monkeypatch.setattr(config, "CONFIG", config.CONFIG)  # restored at teardown
    monkeypatch.setenv("RESEARCH_ENGINE_MODE", "on")
    monkeypatch.delenv("ML_ENGINE_API_KEY", raising=False)
    cfg = config.load()
    assert cfg.mode == "off"
    assert "config_invalid:ML_ENGINE_API_KEY" in cfg.degraded_reasons
    return cfg


def test_bad_config_research_disabled(client, auth_headers, bad_config):
    resp = client.get("/api/v1/research/stocks/RELIANCE", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "RESEARCH_DISABLED"


def test_bad_config_healthz_reports_research_degraded(client, admin_headers, bad_config, no_dependencies, monkeypatch):
    def _no_ready(self):
        raise AssertionError("ml-engine /ready must not be called without a key")

    monkeypatch.setattr(MLEngineClient, "ready", _no_ready)

    resp = client.get("/healthz", headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    research = body["research"]
    assert research["mode"] == "off"
    assert research["degraded"] is True
    assert "config_invalid:ML_ENGINE_API_KEY" in research["degraded_reasons"]
    assert "research" not in body["degraded"]
    for key in ("last_nightly_market_date", "last_nightly_status", "hours_since_last_success", "last_outcome_run_at"):
        assert key in research


def test_healthz_survives_research_block_error(client, admin_headers, no_dependencies, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("secret-detail")

    monkeypatch.setattr(research_health_mod, "research_health", _boom)

    resp = client.get("/healthz", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["research"] == {"degraded": True, "degraded_reasons": ["health_check_failed"]}
    assert "secret-detail" not in resp.text


# ---------------------------------------------------------------------------
# research_health() block
# ---------------------------------------------------------------------------

@pytest.fixture()
def ledger(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        yield session

    monkeypatch.setattr(research_health_mod, "get_session", _get_session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def research_on(monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(mode="on", ml_engine_api_key="test-key"))


class _FakeEngine:
    def __init__(self, ready: dict[str, Any]) -> None:
        self._ready = ready
        self.calls = 0

    def ready(self) -> dict[str, Any]:
        self.calls += 1
        return self._ready


def _add_run(session, market_date: date, status: str) -> None:
    session.add(ResearchRun(kind="nightly", market_date=market_date, status=status,
                            started_at=datetime(2026, 10, 12, 14, 15), finished_at=datetime(2026, 10, 12, 15, 0)))
    session.commit()


@pytest.mark.parametrize("now, expected", [
    (TUE_0800_IST, MON),                                              # Tue 08:00 IST: Monday is due
    (TUE_0700_IST, FRI),                                              # Tue 07:00 IST: Monday's 07:15 kick not yet run
    (datetime(2026, 10, 12, 2, 30, tzinfo=timezone.utc), FRI),        # Mon 08:00 IST
    (datetime(2026, 10, 11, 4, 30, tzinfo=timezone.utc), FRI),        # Sun 10:00 IST
    (datetime(2026, 10, 10, 1, 30, tzinfo=timezone.utc), date(2026, 10, 8)),  # Sat 07:00 IST: Thursday
])
def test_expected_market_date(now, expected):
    assert research_health_mod.expected_market_date(now) == expected


def test_no_run_and_engine_not_ready(ledger, research_on):
    engine = _FakeEngine({"ready": False, "reasons": ["manifest_invalid"]})
    block = research_health_mod.research_health(TUE_0800_IST, engine)  # type: ignore[arg-type]
    assert block["mode"] == "on"
    assert block["degraded"] is True
    assert block["degraded_reasons"] == ["no_run_for_last_weekday", "manifest_invalid"]
    assert engine.calls == 1


@pytest.mark.parametrize("status", ["ok", "degraded", "running", "skipped_holiday"])
def test_run_for_due_weekday_is_healthy(ledger, research_on, status):
    _add_run(ledger, MON, status)
    block = research_health_mod.research_health(TUE_0800_IST, _FakeEngine({"ready": True, "reasons": []}))  # type: ignore[arg-type]
    assert block["degraded"] is False
    assert block["degraded_reasons"] == []
    assert block["last_nightly_market_date"] == MON.isoformat()
    assert block["last_nightly_status"] == status


def test_failed_run_counts_as_no_run(ledger, research_on):
    _add_run(ledger, MON, "failed")
    block = research_health_mod.research_health(TUE_0800_IST, _FakeEngine({"ready": True, "reasons": []}))  # type: ignore[arg-type]
    assert block["degraded_reasons"] == ["no_run_for_last_weekday"]


def test_before_deadline_previous_weekday_suffices(ledger, research_on):
    _add_run(ledger, FRI, "ok")
    block = research_health_mod.research_health(TUE_0700_IST, _FakeEngine({"ready": True, "reasons": []}))  # type: ignore[arg-type]
    assert block["degraded"] is False


def test_mode_off_skips_run_check(ledger, monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(mode="off"))
    engine = _FakeEngine({"ready": False, "reasons": ["x"]})
    block = research_health_mod.research_health(TUE_0800_IST, engine)  # type: ignore[arg-type]
    assert block["mode"] == "off"
    assert block["degraded"] is False
    assert block["degraded_reasons"] == []
    assert engine.calls == 0  # no key configured: /ready is not called
