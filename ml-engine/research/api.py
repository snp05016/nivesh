"""ml-engine internal research API, ``/research/v1`` (spec 9.2, 2.6, 2.7).

Every route needs ``X-ML-Engine-Key`` equal to ``ML_ENGINE_API_KEY``
(``hmac.compare_digest``): an unset key answers 503, a wrong or missing header 401.
The service is bound to 127.0.0.1 and called only by the backend.

At startup (the router lifespan, merged into the app's) every ``runs/*/run.json``
still ``running`` is rewritten to ``failed`` with error ``engine_restarted``: its
thread died with the previous process (spec 2.6).

Runs execute one at a time in a background thread under a module lock. Before a
new run starts, ``runs/*`` folders older than 7 days are deleted (spec 2.2).

Deployment knobs (read per request; the defaults are production):

- ``RESEARCH_DATA_DIR``: data root (``research.config.DATA_DIR``).
- ``RESEARCH_PANEL_SOURCE``: ``store`` (default) or ``local_csv`` (dev, the
  survivorship-biased ``RESEARCH_LOCAL_CSV`` panel).
- ``RESEARCH_FUNDAMENTALS``: ``fetch`` (default) or ``skip`` (no Yahoo calls).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import shutil
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import config, live, outcomes, pipeline, registry
from .contract import SCHEMA_VERSION, LiveMetricsRequest, OutcomeRequestItem, RunCounts, RunStatus
from .marketdata import store, universe
from .report import as_timestamp

__all__ = ["router"]

log = logging.getLogger("research.api")

RUN_RETENTION = timedelta(days=7)
MAX_EXTRA_SYMBOLS = 500
MAX_OUTCOME_ITEMS = 5000
MAX_ITEMS_PAGE = 200
MAX_READY_SESSIONS_OLD = 5
# Outcome scoring needs the same lookback as the nightly window: PIT membership is
# path-dependent and only truncation-safe at this depth (pipeline.WINDOW_YEARS).
_OUTCOME_LOOKBACK = timedelta(days=round(365.25 * pipeline.WINDOW_YEARS))
_RUN_ID_RE = re.compile(r"^\d{8}-[0-9a-f]{8}$")
_REQUEST_FILE = "request.json"

PanelSource = Literal["store", "local_csv"]

# The single active run of this process: {"run_id", "market_date", "thread"}.
_LOCK = threading.Lock()
_ACTIVE: dict[str, Any] | None = None


# ── settings and auth ───────────────────────────────────────────────────────


def _data_dir() -> Path:
    return config.DATA_DIR


def _source() -> PanelSource:
    value = os.environ.get("RESEARCH_PANEL_SOURCE", "store").strip() or "store"
    if value not in ("store", "local_csv"):
        log.error("RESEARCH_PANEL_SOURCE=%r is invalid", value)
        raise HTTPException(status_code=503, detail="invalid RESEARCH_PANEL_SOURCE")
    return cast(PanelSource, value)


def _fundamentals_mode() -> Literal["fetch", "skip"]:
    return "skip" if os.environ.get("RESEARCH_FUNDAMENTALS", "").strip() == "skip" else "fetch"


def require_key(x_ml_engine_key: Annotated[str | None, Header(alias="X-ML-Engine-Key")] = None) -> None:
    """503 when ``ML_ENGINE_API_KEY`` is unset, 401 when the header is missing or wrong."""
    expected = os.environ.get("ML_ENGINE_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="ML_ENGINE_API_KEY is not configured")
    if x_ml_engine_key is None or not hmac.compare_digest(x_ml_engine_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid X-ML-Engine-Key")


# ── run folders ─────────────────────────────────────────────────────────────


def _runs_dir(root: Path) -> Path:
    return root / "runs"


def _read_status(rdir: Path) -> RunStatus | None:
    try:
        return RunStatus.model_validate_json((rdir / "run.json").read_bytes())
    except (OSError, ValidationError):
        return None


def _write_status(rdir: Path, status: RunStatus) -> None:
    registry.write_atomic(rdir / "run.json", (status.model_dump_json(indent=2) + "\n").encode("utf-8"))


def mark_orphaned_runs(root: Path, now: datetime | None = None) -> list[str]:
    """Rewrite every ``running`` run.json (not owned by this process) to failed ``engine_restarted``."""
    base = _runs_dir(root)
    if not base.is_dir():
        return []
    active = _ACTIVE["run_id"] if _ACTIVE is not None else None
    fixed: list[str] = []
    for rdir in sorted(p for p in base.iterdir() if p.is_dir()):
        status = _read_status(rdir)
        if status is None or status.status != "running" or status.run_id == active:
            continue
        status.status = "failed"
        status.error = "engine_restarted"
        status.finished_at = now or datetime.now(timezone.utc)
        try:
            _write_status(rdir, status)
            fixed.append(status.run_id)
        except OSError as exc:
            log.warning("could not mark orphaned run %s failed: %s", rdir.name, exc)
    if fixed:
        log.warning("marked %d orphaned research run(s) failed: %s", len(fixed), ", ".join(fixed))
    return fixed


def prune_runs(root: Path, now: float | None = None, keep: frozenset[str] = frozenset()) -> list[str]:
    """Delete ``runs/*`` folders last modified more than 7 days ago (never one in ``keep``)."""
    base = _runs_dir(root)
    if not base.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - RUN_RETENTION.total_seconds()
    removed: list[str] = []
    for rdir in base.iterdir():
        if not rdir.is_dir() or rdir.name in keep:
            continue
        try:
            if rdir.stat().st_mtime < cutoff:
                shutil.rmtree(rdir)
                removed.append(rdir.name)
        except OSError as exc:
            log.warning("could not prune run folder %s: %s", rdir.name, exc)
    return removed


def _finished_run(root: Path, market_date: date, extra: list[str]) -> RunStatus | None:
    """The newest finished run for ``market_date`` and this extra set (a holiday matches any extra set)."""
    base = _runs_dir(root)
    if not base.is_dir():
        return None
    best: RunStatus | None = None
    for rdir in base.iterdir():
        status = _read_status(rdir) if rdir.is_dir() else None
        if status is None or status.market_date != market_date:
            continue
        if status.status == "skipped_holiday":
            match = True
        elif status.status in ("ok", "degraded"):
            try:
                req = json.loads((rdir / _REQUEST_FILE).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            match = req.get("extra_symbols") == extra
        else:
            continue
        if match and (best is None or status.started_at > best.started_at):
            best = status
    return best


def _run_thread(run_id: str, market_date: date, extra: list[str], root: Path, source: PanelSource,
                fundamentals: Literal["fetch", "skip"]) -> None:
    global _ACTIVE
    try:
        pipeline.run_nightly(market_date, extra, source, root, fundamentals, run_id=run_id)
    except Exception as exc:  # run_nightly records its own failures; this is a last resort
        log.exception("research run %s crashed", run_id)
        rdir = _runs_dir(root) / run_id
        status = _read_status(rdir)
        if status is not None and status.status == "running":
            status.status, status.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
            status.finished_at = datetime.now(timezone.utc)
            _write_status(rdir, status)
    finally:
        with _LOCK:
            if _ACTIVE is not None and _ACTIVE["run_id"] == run_id:
                _ACTIVE = None


# ── /ready helpers ──────────────────────────────────────────────────────────


def _active_artefact(h: int, root: Path) -> tuple[str, dict[str, Any], Path]:
    """(model_id, manifest, dir) of the verified active artefact; raises ArtefactError."""
    entry = registry.read_registry(root)["active"].get(str(h))
    if not entry:
        raise registry.ArtefactError([f"no active artefact for horizon {h}"])
    mdir = registry.model_dir(str(entry["model_id"]), root)
    manifest, sha = registry.verify(mdir, allow_fast=bool(entry.get("allow_fast")))
    if sha != entry.get("manifest_sha256"):
        raise registry.ArtefactError([f"manifest sha256 differs from the registry for {mdir.name}"])
    if int(manifest.get("horizon", -1)) != h:
        raise registry.ArtefactError([f"artefact {mdir.name} is not for horizon {h}"])
    return str(entry["model_id"]), manifest, mdir


def _active_json(h: int, root: Path, name: str, procedure_id: str | None = None) -> dict[str, Any] | None:
    """A JSON file of the verified active artefact, or None (missing, invalid or another procedure)."""
    try:
        _, manifest, mdir = _active_artefact(h, root)
        if procedure_id is not None and manifest.get("procedure_id") != procedure_id:
            return None
        data = json.loads((mdir / name).read_text(encoding="utf-8"))
    except (registry.ArtefactError, OSError, ValueError) as exc:
        log.info("active artefact h=%d unusable for %s: %s", h, name, exc)
        return None
    return data if isinstance(data, dict) else None


def _last_session_and_schema(root: Path, source: PanelSource) -> tuple[date | None, bool]:
    """(latest panel date, store schema ok). Reads only the newest partition's ``date`` column."""
    if source == "local_csv":
        if not config.LOCAL_CSV.exists():
            return None, True
        dates = pd.read_csv(config.LOCAL_CSV, usecols=["date"])["date"]
        return (as_timestamp(pd.to_datetime(dates).max()).date() if len(dates) else None), True
    paths = sorted((root / "curated" / "prices").glob("year=*/part.parquet"))
    if not paths:
        return None, True
    newest = paths[-1]
    if not set(store.PANEL_COLUMNS) <= set(pq.read_schema(newest).names):
        return None, False
    dates = pd.read_parquet(newest, columns=["date"])["date"]
    return (as_timestamp(dates.max()).date() if len(dates) else None), True


def _sessions_old(last: date, today: date) -> int:
    """Weekdays d with last < d <= today (holidays are not known here, so this over-counts)."""
    return int(np.busday_count(last + timedelta(days=1), today + timedelta(days=1)))


def _ist_today() -> date:
    return datetime.now(pipeline.IST).date()


# ── request bodies ──────────────────────────────────────────────────────────


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunRequest(_Body):
    market_date: date
    extra_symbols: Annotated[list[Annotated[str, Field(max_length=32)]], Field(max_length=MAX_EXTRA_SYMBOLS)] = []


class ComputeRequest(_Body):
    symbol: Annotated[str, Field(min_length=1, max_length=32)]


class OutcomesRequest(_Body):
    items: Annotated[list[OutcomeRequestItem], Field(max_length=MAX_OUTCOME_ITEMS)]


# ── router ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        mark_orphaned_runs(_data_dir())
    except Exception:  # never block startup of the rest of ml-engine
        log.exception("research startup sweep failed")
    yield


router = APIRouter(prefix="/research/v1", tags=["research"], dependencies=[Depends(require_key)],
                   lifespan=_lifespan)


@router.get("/ready")
def ready() -> JSONResponse:
    """200 ``{ready, active_models, last_session, schema_version}`` or 503 ``{ready: false, reasons}``."""
    root = _data_dir()
    source = _source()
    reasons: list[str] = []
    if not root.is_dir() or not os.access(root, os.R_OK | os.W_OK | os.X_OK):
        reasons.append("data_dir_unavailable")
    active: dict[str, str] = {}
    for h in config.HORIZONS:
        try:
            active[str(h)] = _active_artefact(h, root)[0]
        except registry.ArtefactError as exc:
            log.info("ready: artefact h=%d: %s", h, exc)
            reasons.append(f"artefact_invalid:{h}")
    last: date | None = None
    try:
        last, schema_ok = _last_session_and_schema(root, source)
        if not schema_ok:
            reasons.append("store_schema_mismatch")
        elif last is None:
            reasons.append("no_market_data")
        elif _sessions_old(last, _ist_today()) > MAX_READY_SESSIONS_OLD:
            reasons.append("market_data_stale")
    except Exception as exc:
        log.warning("ready: market data unreadable: %s", exc)
        reasons.append("market_data_unreadable")
    if reasons:
        return JSONResponse(status_code=503, content={"ready": False, "reasons": reasons})
    return JSONResponse(content={
        "ready": True, "active_models": active,
        "last_session": last.isoformat() if last else None, "schema_version": SCHEMA_VERSION,
    })


@router.post("/runs")
def start_run(body: RunRequest) -> JSONResponse:
    """202 new run; 200 an already finished run for that date and extra set; 409 while a run is active."""
    global _ACTIVE
    root = _data_dir()
    source, fundamentals = _source(), _fundamentals_mode()
    extra = sorted({pipeline.normalise_symbol(s) for s in body.extra_symbols if s.strip()})
    with _LOCK:
        if _ACTIVE is not None and _ACTIVE["thread"].is_alive():
            return JSONResponse(status_code=409, content={
                "run_id": _ACTIVE["run_id"], "market_date": _ACTIVE["market_date"].isoformat(),
            })
        prune_runs(root)
        done = _finished_run(root, body.market_date, extra)
        if done is not None:
            return JSONResponse(content=json.loads(done.model_dump_json()))
        run_id = pipeline.new_run_id(body.market_date)
        rdir = _runs_dir(root) / run_id
        rdir.mkdir(parents=True, exist_ok=False)
        registry.write_atomic(rdir / _REQUEST_FILE, registry.canonical_json(
            {"market_date": body.market_date.isoformat(), "extra_symbols": extra}))
        # Written before returning so an immediate GET /runs/{id} never 404s.
        _write_status(rdir, RunStatus(run_id=run_id, market_date=body.market_date, status="running", stage="prices",
                                      counts=RunCounts(), error=None, started_at=datetime.now(timezone.utc),
                                      finished_at=None))
        thread = threading.Thread(
            target=_run_thread, args=(run_id, body.market_date, extra, root, source, fundamentals),
            name=f"research-run-{run_id}", daemon=True,
        )
        _ACTIVE = {"run_id": run_id, "market_date": body.market_date, "thread": thread}
        thread.start()
    return JSONResponse(status_code=202, content={"run_id": run_id, "status": "running"})


def _run_dir_or_404(run_id: str) -> Path:
    rdir = _runs_dir(_data_dir()) / run_id
    if not _RUN_ID_RE.fullmatch(run_id) or not (rdir / "run.json").is_file():
        raise HTTPException(status_code=404, detail="run not found")
    return rdir


@router.get("/runs/{run_id}")
def run_status(run_id: str) -> JSONResponse:
    status = _read_status(_run_dir_or_404(run_id))
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")
    return JSONResponse(content=json.loads(status.model_dump_json()))


@router.get("/runs/{run_id}/items")
def run_items(
    run_id: str,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_ITEMS_PAGE)] = MAX_ITEMS_PAGE,
) -> dict[str, Any]:
    """``{items, next_offset}``; next_offset is null on the last page (and for a run without items)."""
    path = _run_dir_or_404(run_id) / "items.jsonl"
    if not path.is_file():
        return {"items": [], "next_offset": None}
    with path.open(encoding="utf-8") as fh:
        lines = [line for line in islice((ln for ln in fh if ln.strip()), offset, offset + limit + 1)]
    items = [json.loads(line) for line in lines[:limit]]
    return {"items": items, "next_offset": offset + limit if len(lines) > limit else None}


@router.post("/compute")
def compute(body: ComputeRequest) -> JSONResponse:
    """200 ``{report}`` (origin on_demand, no ledger rows); 404 UNKNOWN_SYMBOL; 422 under 60 sessions; 503."""
    try:
        report = pipeline.compute_symbol(body.symbol, source=_source(), data_dir=_data_dir(),
                                         fundamentals_mode=_fundamentals_mode())
    except pipeline.UnknownSymbol:
        return JSONResponse(status_code=404, content={"code": "UNKNOWN_SYMBOL"})
    except pipeline.InsufficientHistory:
        return JSONResponse(status_code=422, content={"code": "INSUFFICIENT_HISTORY"})
    except HTTPException:
        raise
    except Exception:
        log.exception("compute failed for %r", body.symbol)
        return JSONResponse(status_code=503, content={"code": "COMPUTE_UNAVAILABLE"})
    return JSONResponse(content={"report": json.loads(report.model_dump_json())})


@router.post("/outcomes")
def score(body: OutcomesRequest) -> dict[str, Any]:
    """``{results, last_session}``: one OutcomeResult (scorer os-2) per item, in input order."""
    root, source = _data_dir(), _source()
    end = _ist_today()
    start = min((i.as_of for i in body.items), default=end) - _OUTCOME_LOOKBACK
    panel = store.load_panel(start=start, end=end, source=source, data_dir=root)
    cal = store.sessions(panel)
    last = as_timestamp(cal[-1]).date().isoformat() if len(cal) else None
    if not body.items:
        return {"results": [], "last_session": last}
    index = store.load_index("NIFTY50", data_dir=root)
    results = outcomes.score_outcomes(body.items, panel, universe.membership(panel), index, data_dir=root)
    return {"results": [json.loads(r.model_dump_json()) for r in results], "last_session": last}


@router.post("/live-metrics")
def live_metrics(body: LiveMetricsRequest) -> JSONResponse:
    """LiveMetricsResponse from the active artefact's validation.json and calibrator.json.

    Both are None when the active artefact is missing, invalid or of another
    procedure: G7 then fails and probability metrics are null (fail closed).
    """
    root = _data_dir()
    validation = _active_json(body.horizon_days, root, "validation.json", body.procedure_id)
    calibrator = _active_json(body.horizon_days, root, "calibrator.json", body.procedure_id) if validation else None
    resp = live.live_metrics(body, validation, calibrator)
    return JSONResponse(content=json.loads(resp.model_dump_json()))


@router.get("/model-card")
def model_card() -> dict[str, Any]:
    """``{procedure_id, horizons: {"21": validation.json | null, "63": ...}}`` (admin detail; gates included)."""
    root = _data_dir()
    return {
        "procedure_id": config.PROCEDURE_ID,
        "horizons": {str(h): _active_json(h, root, "validation.json") for h in config.HORIZONS},
    }
