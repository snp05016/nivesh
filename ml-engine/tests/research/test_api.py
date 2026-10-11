"""ml-engine research API ``/research/v1`` (spec 9.2, 11.1; package ml-api-deploy).

The router is mounted on a fresh ``FastAPI()`` (``main.py`` loads polars and torch
models at startup, so it is never imported here). Data lives in a temp dir; the
nightly run is replaced by a fake where a real one is not the point; nothing
touches the network.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from research import api, config, pipeline
from research.contract import ResearchReport, RunCounts, RunStatus
from research.marketdata import bhavcopy, store

KEY = "test-key-not-a-secret"
AUTH = {"X-ML-Engine-Key": KEY}
D = date(2026, 6, 23)  # last session of the local CSV
needs_csv = pytest.mark.skipif(not config.LOCAL_CSV.exists(), reason="RESEARCH_LOCAL_CSV not available")


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    def refuse(*_a: Any, **_k: Any) -> None:
        raise AssertionError("network access in a unit test")

    monkeypatch.setattr(bhavcopy.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(store.YFinance, "__init__", refuse)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("ML_ENGINE_API_KEY", KEY)
    monkeypatch.setenv("RESEARCH_FUNDAMENTALS", "skip")
    monkeypatch.delenv("RESEARCH_PANEL_SOURCE", raising=False)
    monkeypatch.setattr(api, "_ACTIVE", None)
    yield tmp_path
    active = api._ACTIVE
    if active is not None:
        active["thread"].join(timeout=10)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as c:  # runs the router lifespan (startup sweep)
        yield c


def _seed_run(root: Path, run_id: str, status: str, market_date: date = D, age_days: float = 0.0,
              extra: list[str] | None = None) -> Path:
    rdir = root / "runs" / run_id
    rdir.mkdir(parents=True)
    started = datetime.now(timezone.utc) - timedelta(days=age_days)
    rs = RunStatus(run_id=run_id, market_date=market_date, status=status, stage="assemble",  # type: ignore[arg-type]
                   counts=RunCounts(), error=None, started_at=started,
                   finished_at=None if status == "running" else started)
    (rdir / "run.json").write_text(rs.model_dump_json(), encoding="utf-8")
    if extra is not None:
        (rdir / "request.json").write_text(json.dumps({"market_date": market_date.isoformat(),
                                                       "extra_symbols": extra}), encoding="utf-8")
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(rdir, (t, t))
    return rdir


# ── auth ────────────────────────────────────────────────────────────────────


def test_key_unset_gives_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ML_ENGINE_API_KEY")
    assert client.get("/research/v1/ready", headers=AUTH).status_code == 503
    assert client.get("/research/v1/model-card").status_code == 503


def test_wrong_or_missing_key_gives_401(client: TestClient) -> None:
    assert client.get("/research/v1/ready", headers={"X-ML-Engine-Key": "wrong"}).status_code == 401
    assert client.get("/research/v1/ready").status_code == 401
    assert client.post("/research/v1/compute", json={"symbol": "TCS"}).status_code == 401


# ── ready, model card, live metrics, outcomes ───────────────────────────────


def test_ready_503_with_reasons(client: TestClient) -> None:
    resp = client.get("/research/v1/ready", headers=AUTH)
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert {"artefact_invalid:21", "artefact_invalid:63", "no_market_data"} <= set(body["reasons"])


def test_model_card_without_artefacts(client: TestClient) -> None:
    resp = client.get("/research/v1/model-card", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"procedure_id": config.PROCEDURE_ID, "horizons": {"21": None, "63": None}}


def test_live_metrics_without_artefact_is_collecting(client: TestClient) -> None:
    resp = client.post("/research/v1/live-metrics", headers=AUTH,
                       json={"procedure_id": config.PROCEDURE_ID, "horizon_days": 21, "rows": []})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["live_status"] == "collecting" and body["live_gate_passed"] is False
    assert body["metrics"]["oos_rank_ic_mean"] is None


def test_outcomes_empty_and_validation(client: TestClient) -> None:
    resp = client.post("/research/v1/outcomes", headers=AUTH, json={"items": []})
    assert resp.status_code == 200 and resp.json() == {"results": [], "last_session": None}
    too_many = [{"prediction_id": i, "isin": None, "symbol": "TCS", "as_of": "2026-01-01", "horizon_days": 21,
                 "entry_close": 1.0} for i in range(api.MAX_OUTCOME_ITEMS + 1)]
    assert client.post("/research/v1/outcomes", headers=AUTH, json={"items": too_many}).status_code == 422


# ── compute ─────────────────────────────────────────────────────────────────


@needs_csv
def test_compute_local_csv(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_PANEL_SOURCE", "local_csv")
    resp = client.post("/research/v1/compute", headers=AUTH, json={"symbol": "tcs.ns"})
    assert resp.status_code == 200, resp.text
    report = ResearchReport.model_validate(resp.json()["report"])
    assert report.origin == "on_demand" and report.symbol == "TCS" and report.as_of.market_date == D
    unknown = client.post("/research/v1/compute", headers=AUTH, json={"symbol": "NOSUCH"})
    assert unknown.status_code == 404 and unknown.json() == {"code": "UNKNOWN_SYMBOL"}
    assert client.post("/research/v1/compute", headers=AUTH, json={}).status_code == 422


def test_compute_errors_map_to_codes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def short(*_a: Any, **_k: Any) -> None:
        raise pipeline.InsufficientHistory("x")

    def broken(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(pipeline, "compute_symbol", short)
    resp = client.post("/research/v1/compute", headers=AUTH, json={"symbol": "NEWCO"})
    assert resp.status_code == 422 and resp.json() == {"code": "INSUFFICIENT_HISTORY"}
    monkeypatch.setattr(pipeline, "compute_symbol", broken)
    resp = client.post("/research/v1/compute", headers=AUTH, json={"symbol": "TCS"})
    assert resp.status_code == 503 and resp.json() == {"code": "COMPUTE_UNAVAILABLE"}


# ── runs ────────────────────────────────────────────────────────────────────


class FakeRun:
    """Stands in for ``pipeline.run_nightly``: blocks until released, then writes an ok run.json."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls: list[tuple[date, list[str]]] = []

    def __call__(self, market_date: date, extra: list[str], source: str, data_dir: Path, mode: str, *,
                 run_id: str) -> RunStatus:
        self.calls.append((market_date, list(extra)))
        assert self.release.wait(timeout=10)
        rdir = Path(data_dir) / "runs" / run_id
        status = RunStatus.model_validate_json((rdir / "run.json").read_text(encoding="utf-8"))
        status.status, status.finished_at = "ok", datetime.now(timezone.utc)
        (rdir / "run.json").write_text(status.model_dump_json(), encoding="utf-8")
        return status


def _wait_idle() -> None:
    active = api._ACTIVE
    if active is not None:
        active["thread"].join(timeout=10)
    assert api._ACTIVE is None


def test_runs_409_then_idempotent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun()
    monkeypatch.setattr(pipeline, "run_nightly", fake)
    resp = client.post("/research/v1/runs", headers=AUTH,
                       json={"market_date": D.isoformat(), "extra_symbols": ["infy.ns", "TCS", "TCS"]})
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["run_id"]
    assert resp.json()["status"] == "running"
    running = client.get(f"/research/v1/runs/{run_id}", headers=AUTH)
    assert running.status_code == 200 and running.json()["status"] == "running"

    busy = client.post("/research/v1/runs", headers=AUTH, json={"market_date": "2026-06-24", "extra_symbols": []})
    assert busy.status_code == 409
    assert busy.json() == {"run_id": run_id, "market_date": D.isoformat()}

    fake.release.set()
    _wait_idle()
    assert fake.calls == [(D, ["INFY", "TCS"])]
    assert client.get(f"/research/v1/runs/{run_id}", headers=AUTH).json()["status"] == "ok"

    again = client.post("/research/v1/runs", headers=AUTH,
                        json={"market_date": D.isoformat(), "extra_symbols": ["TCS", "INFY"]})
    assert again.status_code == 200 and again.json()["run_id"] == run_id and again.json()["status"] == "ok"
    other = client.post("/research/v1/runs", headers=AUTH, json={"market_date": D.isoformat(), "extra_symbols": []})
    assert other.status_code == 202 and other.json()["run_id"] != run_id
    _wait_idle()


def test_holiday_run_is_returned_for_any_extra_set(client: TestClient, env: Path) -> None:
    _seed_run(env, "20260623-0000aaaa", "skipped_holiday")
    resp = client.post("/research/v1/runs", headers=AUTH, json={"market_date": D.isoformat(), "extra_symbols": ["X"]})
    assert resp.status_code == 200 and resp.json()["status"] == "skipped_holiday"
    assert resp.json()["run_id"] == "20260623-0000aaaa"


def test_runs_request_validation(client: TestClient) -> None:
    many = [f"S{i}" for i in range(api.MAX_EXTRA_SYMBOLS + 1)]
    assert client.post("/research/v1/runs", headers=AUTH,
                       json={"market_date": D.isoformat(), "extra_symbols": many}).status_code == 422
    assert client.post("/research/v1/runs", headers=AUTH, json={"market_date": "not-a-date"}).status_code == 422


def test_startup_marks_running_runs_failed(env: Path) -> None:
    rdir = _seed_run(env, "20260622-deadbeef", "running")
    done = _seed_run(env, "20260619-cafe0001", "ok")
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as c:
        body = c.get("/research/v1/runs/20260622-deadbeef", headers=AUTH).json()
    assert body["status"] == "failed" and body["error"] == "engine_restarted" and body["finished_at"]
    on_disk = RunStatus.model_validate_json((rdir / "run.json").read_text(encoding="utf-8"))
    assert on_disk.status == "failed"
    assert RunStatus.model_validate_json((done / "run.json").read_text(encoding="utf-8")).status == "ok"


def test_post_runs_prunes_old_folders(client: TestClient, env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun()
    fake.release.set()
    monkeypatch.setattr(pipeline, "run_nightly", fake)
    old = _seed_run(env, "20260601-00000001", "ok", market_date=date(2026, 6, 1), age_days=8)
    recent = _seed_run(env, "20260620-00000002", "ok", market_date=date(2026, 6, 20), age_days=1)
    resp = client.post("/research/v1/runs", headers=AUTH, json={"market_date": D.isoformat(), "extra_symbols": []})
    assert resp.status_code == 202
    _wait_idle()
    assert not old.exists() and recent.exists()


# ── items paging and run lookup ─────────────────────────────────────────────


def test_items_paging(client: TestClient, env: Path) -> None:
    rdir = _seed_run(env, "20260623-0abc0def", "ok")
    (rdir / "items.jsonl").write_text("".join(json.dumps({"n": i}) + "\n" for i in range(5)), encoding="utf-8")
    url = "/research/v1/runs/20260623-0abc0def/items"
    first = client.get(url, headers=AUTH, params={"offset": 0, "limit": 2}).json()
    assert first == {"items": [{"n": 0}, {"n": 1}], "next_offset": 2}
    middle = client.get(url, headers=AUTH, params={"offset": 2, "limit": 2}).json()
    assert middle == {"items": [{"n": 2}, {"n": 3}], "next_offset": 4}
    last = client.get(url, headers=AUTH, params={"offset": 4, "limit": 2}).json()
    assert last == {"items": [{"n": 4}], "next_offset": None}
    exact = client.get(url, headers=AUTH, params={"offset": 0, "limit": 5}).json()
    assert len(exact["items"]) == 5 and exact["next_offset"] is None
    assert client.get(url, headers=AUTH, params={"limit": 201}).status_code == 422
    assert client.get(url, headers=AUTH, params={"offset": -1}).status_code == 422


def test_unknown_or_malformed_run_is_404(client: TestClient, env: Path) -> None:
    _seed_run(env, "20260623-00000abc", "running")
    assert client.get("/research/v1/runs/20260623-00000abc/items", headers=AUTH).json() == {
        "items": [], "next_offset": None}
    assert client.get("/research/v1/runs/20260623-ffffffff", headers=AUTH).status_code == 404
    assert client.get("/research/v1/runs/..%2F..%2Fetc", headers=AUTH).status_code == 404
    assert client.get("/research/v1/runs/nope/items", headers=AUTH).status_code == 404


# ── with promoted (fast) artefacts ──────────────────────────────────────────


@pytest.fixture(scope="module")
def fast_models(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """``train --fast --train-production`` for 21 and 63 on the local CSV, promoted with --allow-fast."""
    if not config.LOCAL_CSV.exists():
        pytest.skip("RESEARCH_LOCAL_CSV not available")
    from research import registry, train

    data_dir = tmp_path_factory.mktemp("models")
    for h in config.HORIZONS:
        assert train.main(["--horizon", str(h), "--source", "local_csv", "--data-dir", str(data_dir),
                           "--fast", "--train-production"]) == 0
    for mdir in (data_dir / "models").iterdir():
        if (mdir / registry.MANIFEST).exists():
            registry.promote(mdir.name, data_dir=data_dir, allow_fast=True)
    return data_dir / "models"


@needs_csv
def test_ready_model_card_and_live_metrics_with_artefacts(env: Path, fast_models: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    shutil.copytree(fast_models, env / "models")
    monkeypatch.setenv("RESEARCH_PANEL_SOURCE", "local_csv")
    monkeypatch.setattr(api, "_ist_today", lambda: D + timedelta(days=6))  # Monday after: 4 sessions old
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as c:
        ready = c.get("/research/v1/ready", headers=AUTH)
        assert ready.status_code == 200, ready.text
        body = ready.json()
        assert body["ready"] is True and set(body["active_models"]) == {"21", "63"}
        assert body["last_session"] == D.isoformat() and body["schema_version"] == "research.v1"

        card = c.get("/research/v1/model-card", headers=AUTH).json()
        assert card["horizons"]["21"]["rank_ic"]["mean"] is not None and card["horizons"]["63"] is not None

        req = {"procedure_id": config.PROCEDURE_ID, "horizon_days": 21, "rows": []}
        live = c.post("/research/v1/live-metrics", headers=AUTH, json=req).json()
        assert live["metrics"]["oos_rank_ic_mean"] == card["horizons"]["21"]["rank_ic"]["mean"]
        other = c.post("/research/v1/live-metrics", headers=AUTH, json={**req, "procedure_id": "other-v9"}).json()
        assert other["metrics"]["oos_rank_ic_mean"] is None  # another procedure's artefact is never used

        monkeypatch.setattr(api, "_ist_today", lambda: D + timedelta(days=10))  # 8 sessions old
        stale = c.get("/research/v1/ready", headers=AUTH)
        assert stale.status_code == 503 and stale.json()["reasons"] == ["market_data_stale"]
