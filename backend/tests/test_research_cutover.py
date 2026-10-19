"""Legacy cutover tests (spec 6.6, 9.5, 11.2; REG-02, REL-22, LLM-03, ML-01).

Hermetic: the gate and the ml-signal router are mounted on fresh ``FastAPI()``
apps with dummy routes; copilot LLM transports, ``multiprocessing.Process`` and
``subprocess.Popen`` are replaced by mocks that fail if called; the research
ledger is a fresh in-memory SQLite database. Nothing touches the network.
"""

from __future__ import annotations

import ast
import json
import multiprocessing
import subprocess
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routers.ml_signal as ml_signal_router
from models.db_models import Base, ResearchReportRow  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
from schemas.ml_signal import MLSignalResponse
from services import copilot_service, llm_utils
from services.research import config
from services.research.legacy_gate import legacy_gate, retired_ml_signal
from services.research.templates import LEGACY_GONE_TEXT

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND.parent / "docs" / "research" / "contract" / "fixtures"
DEEP_LINK = "nivesh://analyze/RELIANCE"


def _set_config(monkeypatch, **kwargs: Any) -> None:
    kwargs.setdefault("ml_engine_api_key", "test-key")
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(**kwargs))


# ---------------------------------------------------------------------------
# legacy_gate
# ---------------------------------------------------------------------------

def _gate_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(legacy_gate)

    @app.post("/analyze")
    def analyze() -> dict[str, str]:
        return {"route": "analyze"}

    @app.get("/analyze/job/{job_id}")
    def job(job_id: str) -> dict[str, str]:
        return {"route": "job"}

    @app.get("/analyze/cache-status/{ticker}")
    def cache_status(ticker: str) -> dict[str, str]:
        return {"route": "cache-status"}

    @app.post("/analyze/batch")
    def analyze_batch() -> dict[str, str]:
        return {"route": "analyze-batch"}

    @app.get("/analyze/batch/{batch_id}")
    def analyze_batch_status(batch_id: str) -> dict[str, str]:
        return {"route": "analyze-batch-status"}

    @app.post("/batch")
    def batch() -> dict[str, str]:
        return {"route": "batch"}

    @app.get("/batch")
    def batch_get() -> dict[str, str]:
        return {"route": "batch-get"}

    @app.get("/daily-action/{user_id}")
    def daily_action(user_id: int) -> dict[str, str]:
        return {"route": "daily-action"}

    @app.get("/api/v1/other")
    def other() -> dict[str, str]:
        return {"route": "other"}

    return app


RETIRED_CALLS = [
    ("POST", "/analyze"),
    ("GET", "/analyze/job/x"),
    ("GET", "/analyze/cache-status/X"),
    ("POST", "/batch"),
    ("GET", "/daily-action/1"),
]
ALWAYS_GONE_CALLS = [("POST", "/analyze/batch"), ("GET", "/analyze/batch/abc")]


def _assert_gone(resp: Any) -> None:
    assert resp.status_code == 410
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text == LEGACY_GONE_TEXT


@pytest.mark.parametrize("method,path", RETIRED_CALLS + ALWAYS_GONE_CALLS)
def test_gate_retired_returns_410(monkeypatch, method, path):
    _set_config(monkeypatch, legacy_retired=True)
    with TestClient(_gate_app()) as client:
        _assert_gone(client.request(method, path))


@pytest.mark.parametrize("method,path", RETIRED_CALLS)
def test_gate_not_retired_passes_through(monkeypatch, method, path):
    _set_config(monkeypatch, legacy_retired=False)
    with TestClient(_gate_app()) as client:
        resp = client.request(method, path)
    assert resp.status_code == 200
    assert resp.text != LEGACY_GONE_TEXT


@pytest.mark.parametrize("retired", [False, True])
@pytest.mark.parametrize("method,path", ALWAYS_GONE_CALLS)
def test_gate_analyze_batch_always_410(monkeypatch, retired, method, path):
    _set_config(monkeypatch, legacy_retired=retired)
    with TestClient(_gate_app()) as client:
        _assert_gone(client.request(method, path))


@pytest.mark.parametrize("retired", [False, True])
@pytest.mark.parametrize("method,path", [("GET", "/batch"), ("GET", "/api/v1/other")])
def test_gate_leaves_other_routes(monkeypatch, retired, method, path):
    _set_config(monkeypatch, legacy_retired=retired)
    with TestClient(_gate_app()) as client:
        assert client.request(method, path).status_code == 200


# ---------------------------------------------------------------------------
# Copilot DEEP_ANALYSIS (REL-22)
# ---------------------------------------------------------------------------

@pytest.fixture()
def research_db(monkeypatch):
    """A fresh in-memory ledger behind ``copilot_service.get_session``."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    monkeypatch.setattr(copilot_service, "get_session", _get_session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def no_spawn_no_llm(monkeypatch):
    """Intent and ticker extraction answer from a script; every other LLM call,
    process or subprocess fails the test."""
    calls: list[str] = []
    replies = iter(["DEEP_ANALYSIS", "RELIANCE.NS"])

    def scripted(messages: Any, **_kwargs: Any) -> str:
        calls.append(messages[-1]["content"])
        return next(replies)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("DEEP_ANALYSIS must not spawn, analyse or call a report LLM")

    monkeypatch.setattr(copilot_service, "deepseek_chat", scripted)
    monkeypatch.setattr(copilot_service, "claude_haiku", forbidden)
    monkeypatch.setattr(copilot_service, "claude_messages", forbidden)
    monkeypatch.setattr(llm_utils, "deepseek_chat", forbidden)    # the research formatter's transport
    monkeypatch.setattr(llm_utils, "claude_messages", forbidden)
    monkeypatch.setattr(multiprocessing, "Process", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    return calls


def _add_report(session: Any, *, narrative: Optional[dict[str, Any]]) -> dict[str, Any]:
    report = json.loads((FIXTURES / "no_edge.json").read_text(encoding="utf-8"))
    report["report_id"] = str(uuid.uuid4())
    report["symbol"] = "RELIANCE"
    for key in ("staleness", "narrative", "live_track_record", "compliance"):
        report[key] = None
    session.add(ResearchReportRow(
        report_uid=report["report_id"],
        symbol="RELIANCE",
        isin=report.get("isin"),
        as_of_date=date.fromisoformat(report["as_of"]["market_date"]),
        engine_version=report["engine_version"],
        procedure_id=report["model_card"].get("procedure_id"),
        origin="nightly",
        status=report["status"],
        in_universe=True,
        report_json=report,
        narrative_json=narrative,
        narrative_status=narrative["status"] if narrative else None,
    ))
    session.commit()
    return report


def _ask() -> dict[str, Any]:
    return copilot_service.process_copilot_request("deep analysis of Reliance please", [], {}, 5)


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_copilot_deep_analysis_no_fork_any_mode(monkeypatch, research_db, no_spawn_no_llm, mode):
    _set_config(monkeypatch, mode=mode)
    _add_report(research_db, narrative=None)

    res = _ask()

    assert DEEP_LINK in res["reply"]
    assert len(no_spawn_no_llm) == 2                      # intent + ticker extraction only
    assert res["context_cards"] == [{"type": "open_analysis", "ticker": "RELIANCE"}]
    assert "signal" not in res["reply"].lower()


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_copilot_no_summary_unless_mode_on(monkeypatch, research_db, no_spawn_no_llm, mode):
    _set_config(monkeypatch, mode=mode)
    _add_report(research_db, narrative={"status": "llm_validated", "summary": "Stored summary sentence."})

    reply = _ask()["reply"]

    assert "Stored summary sentence." not in reply
    assert reply.endswith(DEEP_LINK)


def test_copilot_mode_on_prepends_stored_summary(monkeypatch, research_db, no_spawn_no_llm):
    _set_config(monkeypatch, mode="on")
    _add_report(research_db, narrative={"status": "llm_validated", "summary": "Stored summary sentence."})

    reply = _ask()["reply"]

    assert reply.startswith("Stored summary sentence.")
    assert reply.endswith(DEEP_LINK)


def test_copilot_mode_on_template_summary_without_narrative(monkeypatch, research_db, no_spawn_no_llm):
    _set_config(monkeypatch, mode="on")
    report = _add_report(research_db, narrative=None)

    reply = _ask()["reply"]

    assert reply.startswith(report["company_name"])       # tf-1 summary rendered locally, no LLM
    assert reply.endswith(DEEP_LINK)


def test_copilot_mode_on_without_report(monkeypatch, research_db, no_spawn_no_llm):
    _set_config(monkeypatch, mode="on")

    reply = _ask()["reply"]

    assert reply == f"See the stock report for RELIANCE in Nivesh: {DEEP_LINK}"


def test_copilot_has_no_analysis_fork():
    """Static guard (REL-22): no process, subprocess or analyze() call remains."""
    source = (BACKEND / "services" / "copilot_service.py").read_text(encoding="utf-8")
    assert "multiprocessing" not in source
    assert "subprocess" not in source
    called: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            called.add(func.id if isinstance(func, ast.Name) else getattr(func, "attr", ""))
    assert not called & {"analyze", "Process", "Popen", "_deep_analysis_worker"}


# ---------------------------------------------------------------------------
# ml-signal retirement (ML-01)
# ---------------------------------------------------------------------------

def test_retired_ml_signal_payload():
    payload = retired_ml_signal(" reliance ")
    parsed = MLSignalResponse.model_validate(payload.model_dump())

    assert parsed.symbol == "RELIANCE"
    assert parsed.direction == 0
    assert parsed.direction_label == "UNAVAILABLE"
    assert parsed.direction_label != "NEUTRAL"
    assert parsed.confidence is None and parsed.confidence_pct is None
    assert parsed.ml_engine_mode == "retired"
    assert parsed.lightgbm_loaded is False
    assert parsed.feature_drivers == []
    assert parsed.status == "unavailable"
    assert parsed.warning == "Retired"
    assert datetime.fromisoformat(parsed.generated_at).tzinfo is not None


def test_ml_signal_route_retired_skips_ml_engine(monkeypatch):
    import services.ml_signal_service as ml_signal_service

    async def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("retired ml-signal must not call ml-engine")

    monkeypatch.setattr(ml_signal_service, "get_ml_signal_cached", forbidden)
    _set_config(monkeypatch, legacy_retired=True)
    app = FastAPI()
    app.include_router(ml_signal_router.router)
    app.dependency_overrides[ml_signal_router.require_auth] = lambda: 1

    with TestClient(app) as client:
        resp = client.get("/api/v1/stocks/RELIANCE/ml-signal")

    assert resp.status_code == 200
    body = MLSignalResponse.model_validate(resp.json())
    assert body.direction_label == "UNAVAILABLE"
    assert body.status == "unavailable"
    assert "NEUTRAL" not in resp.text
