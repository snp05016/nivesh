"""Stock report API and serving policy tests (spec 2.5, 5.6, 8.6, 9.1, 11.2).

Hermetic: the research router is mounted on a fresh ``FastAPI()``; a fresh
in-memory SQLite database per test (shared across TestClient threads through
``StaticPool``) replaces ``routers.research.get_session``; tokens are resolved
by a patched ``core.security.verify_access_token``; ml-engine is a fake; the
LLM transport raises if called. Nothing touches the network.
"""

from __future__ import annotations

import ast
import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routers.research as research_router
from core import security
from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    Base,
    ResearchLiveMetric,
    ResearchPrediction,
    ResearchReportRow,
    ResearchRun,
)
from repositories import research_repo as repo
from services import llm_utils
from services.research import config, serve
from services.research.client import EngineResponse, MLEngineUnavailable
from services.research.templates import TIER_TEXT

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND.parent / "docs" / "research" / "contract" / "fixtures"
BASE = "/api/v1/research"

D = date(2026, 10, 9)                                                 # Friday, the fixtures' as_of
MON = date(2026, 10, 12)
FRI_NIGHT = datetime(2026, 10, 9, 16, 30, tzinfo=timezone.utc)        # Fri 22:00 IST: due = Fri
MON_NIGHT = datetime(2026, 10, 12, 16, 30, tzinfo=timezone.utc)       # Mon 22:00 IST: due = Mon
WED_MORNING = datetime(2026, 10, 14, 4, 30, tzinfo=timezone.utc)      # Wed 10:00 IST: due = Tue
WED_NIGHT = datetime(2026, 10, 14, 16, 30, tzinfo=timezone.utc)       # Wed 22:00 IST: due = Wed

USER_ID, OTHER_ID, ADMIN_ID = 4101, 4102, 4199
TOKENS = {"user-token": USER_ID, "other-token": OTHER_ID, "admin-token": ADMIN_ID}
USER = {"Authorization": "Bearer user-token"}
ADMIN = {"Authorization": "Bearer admin-token"}
PROCEDURE = "rg-lgbm-v1"
TABLES = (ResearchRun, ResearchReportRow, ResearchPrediction, ResearchLiveMetric)

_FORBIDDEN_EXACT = frozenset({"signal", "rating", "zone", "flag", "gates"})
_FORBIDDEN_PREFIX = ("target", "upside", "downside", "stop", "entry", "confidence")


# ---------------------------------------------------------------------------
# Fixtures and fakes
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def db(monkeypatch, session):
    @contextmanager
    def _get_session():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    monkeypatch.setattr(research_router, "get_session", _get_session)
    return session


def _set_config(monkeypatch, **kwargs: Any) -> None:
    kwargs.setdefault("ml_engine_api_key", "test-key")
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(**kwargs))


@pytest.fixture(autouse=True)
def research_on(monkeypatch):
    _set_config(monkeypatch, mode="on")


@pytest.fixture(autouse=True)
def auth(monkeypatch):
    monkeypatch.setattr(security, "verify_access_token", lambda token: TOKENS.get(token))
    monkeypatch.setattr(security, "is_admin", lambda uid: uid == ADMIN_ID)


@pytest.fixture(autouse=True)
def now(monkeypatch):
    clock = {"now": FRI_NIGHT}
    monkeypatch.setattr(research_router, "_now", lambda: clock["now"])
    return clock


@pytest.fixture(autouse=True)
def llm(monkeypatch):
    mock = MagicMock(side_effect=AssertionError("no LLM call on a request path"))
    monkeypatch.setattr(llm_utils, "deepseek_chat", mock)
    return mock


@pytest.fixture(autouse=True)
def clear_model_card_cache():
    serve._engine_card.clear()
    yield
    serve._engine_card.clear()


class FakeEngine:
    def __init__(self) -> None:
        self.compute_calls: list[str] = []
        self.compute_fn = lambda symbol: EngineResponse(200, {"report": _stored("out_of_universe_degraded.json", symbol=symbol)})
        self.card_calls = 0

    def compute(self, symbol: str) -> EngineResponse:
        self.compute_calls.append(symbol)
        return self.compute_fn(symbol)

    def model_card(self) -> dict[str, Any]:
        self.card_calls += 1
        return {"procedure_id": PROCEDURE, "horizons": {"21": {"gates": [{"id": "G1", "passed": False}]}, "63": None}}


@pytest.fixture(autouse=True)
def engine(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(research_router, "MLEngineClient", lambda *a, **k: fake)
    return fake


@pytest.fixture()
def api():
    app = FastAPI()
    app.include_router(research_router.router)
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stored(name: str, *, symbol: Optional[str] = None, as_of: date = D) -> dict[str, Any]:
    """A contract fixture as ml-engine stores it: backend blocks null."""
    report = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    report["report_id"] = str(uuid.uuid4())
    if symbol is not None:
        report["symbol"] = symbol
    report["as_of"]["market_date"] = as_of.isoformat()
    for key in ("staleness", "narrative", "live_track_record", "compliance"):
        report[key] = None
    for outlook in report["outlooks"]:
        outlook["tier_text"] = None
        outlook["prediction_id"] = None
    for entry in report["model_card"]["horizons"]:
        entry["tier_text"] = None
    return report


def _pred(outlook: dict[str, Any]) -> dict[str, Any]:
    h = outlook["horizon_days"]
    return {
        "horizon_days": h,
        "procedure_id": outlook["procedure_id"],
        "model_id": outlook["model_id"],
        "manifest_sha256": "a" * 64,
        "universe_id": "NSE_LIQ200",
        "evidence_tier": outlook["evidence_tier"],
        "reason_codes": list(outlook["reason_codes"]),
        "score": 0.1,
        "rank_pct": 0.6,
        "bucket": 4,
        "p_top_half": 0.54,
        "entry_close": 1234.5,
        "feature_hash": "f" * 64,
        "expected_maturity_date": "2026-11-09" if h == 21 else "2027-01-08",
    }


def _seed(session, name: str, *, symbol: Optional[str] = None, as_of: date = D) -> ResearchReportRow:
    """Ingest a fixture as a nightly report with its ledger rows."""
    report = _stored(name, symbol=symbol, as_of=as_of)
    run_id = repo.create_run(session, kind="nightly", market_date=as_of, status="ok").id
    preds = [_pred(o) for o in report["outlooks"] if o["procedure_id"]]
    repo.ingest_run_items(session, run_id, [{"report": report, "predictions": preds}])
    row = repo.latest_report(session, report["symbol"])
    assert row is not None
    return row


def _live(session, horizon: int, *, status: str = "collecting", gate: bool = False) -> None:
    repo.insert_live_metrics(session, procedure_id=PROCEDURE, horizon_days=horizon, computed_on=D, response={
        "live_status": status, "live_gate_passed": gate, "matured_n": 4000, "void_n": 3, "stale_exit_n": 1,
        "matured_dates": 300, "independent_periods": 14, "alarms": [],
        "metrics": {"rank_ic_mean": 0.04, "rank_ic_hac_t": 2.1, "window": "2025-06-02 to 2026-10-02"},
    })


def _code(resp) -> Optional[str]:
    body = resp.json()
    detail = body.get("detail") if isinstance(body, dict) else None
    return (detail if isinstance(detail, dict) else body).get("code")


def _outlook(served: dict[str, Any], h: int) -> dict[str, Any]:
    return next(o for o in served["outlooks"] if o["horizon_days"] == h)


def _snapshot(session) -> dict[str, list[tuple]]:
    session.expire_all()
    out = {}
    for model in TABLES:
        cols = [c.name for c in model.__table__.columns]
        out[model.__tablename__] = sorted(
            (tuple(repr(getattr(r, c)) for c in cols) for r in session.query(model).all()),
        )
    return out


def _forbidden_keys(obj: Any, top: bool = True, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            k = str(key).lower()
            if k in _FORBIDDEN_EXACT or k.startswith(_FORBIDDEN_PREFIX) or ("coverage" in k and not (top and k == "coverage")):
                found.append(path + str(key))
            found += _forbidden_keys(value, False, f"{path}{key}.")
    elif isinstance(obj, list):
        for item in obj:
            found += _forbidden_keys(item, False, path)
    return found


# ---------------------------------------------------------------------------
# Access and modes
# ---------------------------------------------------------------------------

def test_mode_on_requires_a_token(api, db):
    _seed(db, "no_edge.json")
    assert api.get(f"{BASE}/stocks/DEMOIND").status_code == 401
    assert api.get(f"{BASE}/stocks/DEMOIND", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert api.post(f"{BASE}/stocks/DEMOIND/compute").status_code == 401
    assert api.get(f"{BASE}/model-card").status_code == 401
    assert api.get(f"{BASE}/stocks/DEMOIND", headers=USER).status_code == 200


def test_shadow_mode_is_admin_only(api, db, monkeypatch):
    _set_config(monkeypatch, mode="shadow")
    _seed(db, "no_edge.json")
    assert api.get(f"{BASE}/stocks/DEMOIND").status_code == 401
    assert api.get(f"{BASE}/stocks/DEMOIND", headers=USER).status_code == 403
    assert api.post(f"{BASE}/stocks/DEMOIND/compute", headers=USER).status_code == 403
    assert api.get(f"{BASE}/stocks/DEMOIND", headers=ADMIN).status_code == 200


def test_off_mode_returns_research_disabled_everywhere(api, db, monkeypatch):
    _set_config(monkeypatch, mode="off")
    _seed(db, "no_edge.json")
    for method, path in (
        ("GET", "/stocks/DEMOIND"), ("POST", "/stocks/DEMOIND/compute"), ("GET", "/model-card"),
        ("GET", "/model-card?detail=full"),
    ):
        resp = api.request(method, f"{BASE}{path}", headers=ADMIN)
        assert (resp.status_code, _code(resp)) == (404, "RESEARCH_DISABLED"), path
    # Admin routes are not mode-gated (spec 9.1).
    for path in ("/track-record", "/admin/status"):
        assert api.get(f"{BASE}{path}", headers=ADMIN).status_code == 200, path
        assert api.get(f"{BASE}{path}", headers=USER).status_code == 403, path


def test_admin_status_shows_degraded_reasons_when_config_invalid(api, db, monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.CONFIG)  # restored after the test
    cfg = config.load({"RESEARCH_ENGINE_MODE": "on"})      # no ML_ENGINE_API_KEY -> invalid
    assert cfg.mode == "off"
    status = api.get(f"{BASE}/admin/status", headers=ADMIN)
    assert status.status_code == 200
    assert "config_invalid:ML_ENGINE_API_KEY" in status.json()["config"]["degraded_reasons"]
    assert api.get(f"{BASE}/admin/status", headers=USER).status_code == 403


def test_invalid_config_fails_closed_to_research_disabled(api, db, monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.CONFIG)  # restored after the test
    cfg = config.load({"RESEARCH_ENGINE_MODE": "on"})      # no ML_ENGINE_API_KEY -> invalid
    assert cfg.mode == "off" and cfg.degraded
    _seed(db, "no_edge.json")
    resp = api.get(f"{BASE}/stocks/DEMOIND", headers=USER)
    assert (resp.status_code, _code(resp)) == (404, "RESEARCH_DISABLED")


def test_etag_and_304(api, db):
    _seed(db, "no_edge.json")
    first = api.get(f"{BASE}/stocks/DEMOIND", headers=USER)
    assert first.status_code == 200
    tag = first.headers["etag"]
    assert first.headers["cache-control"] == "private, max-age=300"
    assert tag == f'"{serve.etag(first.json())}"' and len(tag) == 34

    again = api.get(f"{BASE}/stocks/DEMOIND", headers={**USER, "If-None-Match": tag})
    assert again.status_code == 304 and again.content == b""
    assert again.headers["etag"] == tag
    assert api.get(f"{BASE}/stocks/DEMOIND", headers={**USER, "If-None-Match": f"W/{tag}"}).status_code == 304
    assert api.get(f"{BASE}/stocks/DEMOIND", headers={**USER, "If-None-Match": '"stale"'}).status_code == 200


def test_symbol_normalisation_and_validation(api, db):
    _seed(db, "no_edge.json")
    assert api.get(f"{BASE}/stocks/demoind.ns", headers=USER).json()["symbol"] == "DEMOIND"
    assert api.get(f"{BASE}/stocks/DEMOIND.BO", headers=USER).status_code == 200
    bad = api.get(f"{BASE}/stocks/NOT_A_SYMBOL", headers=USER)
    assert (bad.status_code, _code(bad)) == (422, "INVALID_SYMBOL")
    missing = api.get(f"{BASE}/stocks/NEWCO", headers=USER)
    assert missing.status_code == 404
    assert missing.json()["detail"] == {"code": "NOT_COVERED", "compute_available": True}


def test_lang_hi_is_rejected(api, db):
    _seed(db, "no_edge.json")
    resp = api.get(f"{BASE}/stocks/DEMOIND?lang=hi", headers=USER)
    assert (resp.status_code, _code(resp)) == (422, "UNSUPPORTED_LANG")
    resp = api.post(f"{BASE}/stocks/DEMOIND/compute?lang=hi", headers=USER)
    assert (resp.status_code, _code(resp)) == (422, "UNSUPPORTED_LANG")
    assert api.get(f"{BASE}/stocks/DEMOIND?lang=en", headers=USER).status_code == 200


# ---------------------------------------------------------------------------
# GET is read-only
# ---------------------------------------------------------------------------

def test_get_leaves_all_four_tables_unchanged_and_calls_no_llm(api, db, llm, now):
    row = _seed(db, "validated_cohort.json")
    _live(db, 21)
    repo.create_run(db, kind="nightly", market_date=MON, status="skipped_holiday")
    before = _snapshot(db)

    now["now"] = MON_NIGHT
    served = api.get(f"{BASE}/stocks/SAMPLEFIN", headers=USER)
    assert served.status_code == 200
    assert served.json()["narrative"]["status"] == "template"   # rendered now, not stored
    assert api.get(f"{BASE}/stocks/NEWCO", headers=USER).status_code == 404
    assert api.get(f"{BASE}/model-card", headers=USER).status_code == 200
    assert api.get(f"{BASE}/track-record", headers=ADMIN).status_code == 200
    assert api.get(f"{BASE}/admin/status", headers=ADMIN).status_code == 200

    assert _snapshot(db) == before
    db.expire_all()
    stored = db.get(ResearchReportRow, row.id)
    assert stored is not None and stored.narrative_json is None
    llm.assert_not_called()


def test_stored_narrative_is_served_as_is(api, db):
    row = _seed(db, "no_edge.json")
    stored = json.loads((FIXTURES / "no_edge.json").read_text(encoding="utf-8"))["narrative"]
    assert repo.set_narrative_once(db, row.id, narrative=stored, status="llm_validated", attempts=1)
    assert api.get(f"{BASE}/stocks/DEMOIND", headers=USER).json()["narrative"] == stored


# ---------------------------------------------------------------------------
# Routing of the static paths
# ---------------------------------------------------------------------------

def test_model_card_and_track_record_reach_their_handlers(api, db):
    _seed(db, "no_edge.json")
    _live(db, 21)
    card = api.get(f"{BASE}/model-card", headers=USER)
    assert card.status_code == 200
    body = card.json()
    assert body.get("code") is None and body["procedure_id"] == PROCEDURE
    assert [h["tier_text"] for h in body["horizons"]] == [TIER_TEXT["no_reliable_edge"]] * 2
    assert body["data_period"] and body["universe_id"] == "NSE_LIQ200" and body["limitations"]

    record = api.get(f"{BASE}/track-record", headers=ADMIN)
    assert record.status_code == 200
    rows = record.json()["rows"]
    assert [(r["procedure_id"], r["horizon_days"], r["live_status"]) for r in rows] == [(PROCEDURE, 21, "collecting")]
    assert rows[0]["metrics"]["void_n"] == 3 and rows[0]["matured_dates"] == 300

    assert api.get(f"{BASE}/track-record", headers=USER).status_code == 403
    assert api.get(f"{BASE}/admin/status", headers=USER).status_code == 403


def test_model_card_summary_has_no_gates_and_full_is_admin_only_and_cached(api, db, engine):
    _seed(db, "validated_cohort.json")
    summary = api.get(f"{BASE}/model-card?detail=summary", headers=USER).json()
    assert "gates" not in json.dumps(summary) and not _forbidden_keys(summary, top=False)
    assert summary["horizons"][0]["tier_text"] == TIER_TEXT["weak_evidence"]

    assert api.get(f"{BASE}/model-card?detail=full", headers=USER).status_code == 403
    full = api.get(f"{BASE}/model-card?detail=full", headers=ADMIN)
    assert full.status_code == 200
    assert full.json()["engine"]["horizons"]["21"]["gates"][0]["id"] == "G1"
    assert api.get(f"{BASE}/model-card?detail=full", headers=ADMIN).status_code == 200
    assert engine.card_calls == 1                                  # cached for an hour
    bad = api.get(f"{BASE}/model-card?detail=everything", headers=USER)
    assert (bad.status_code, _code(bad)) == (422, "UNSUPPORTED_DETAIL")


def test_model_card_without_reports_is_404(api):
    resp = api.get(f"{BASE}/model-card", headers=USER)
    assert (resp.status_code, _code(resp)) == (404, "MODEL_CARD_UNAVAILABLE")


def test_admin_status_reports_config_runs_and_prose_without_secrets(api, db):
    _seed(db, "no_edge.json")
    status = api.get(f"{BASE}/admin/status", headers=ADMIN)
    assert status.status_code == 200
    body = status.json()
    assert body["config"]["mode"] == "on" and body["config"]["degraded_reasons"] == []
    assert body["runs"][0]["kind"] == "nightly" and body["prose"]["llm_calls_today"] == 0
    assert "test-key" not in status.text and "api_key" not in status.text


# ---------------------------------------------------------------------------
# Staleness (spec 2.5)
# ---------------------------------------------------------------------------

def test_holiday_with_failed_rows_adds_no_session(api, db, now):
    _seed(db, "no_edge.json")
    repo.create_run(db, kind="nightly", market_date=MON, status="failed", error="engine_busy")
    repo.create_run(db, kind="nightly", market_date=MON, status="failed", error="stale_run")
    repo.create_run(db, kind="nightly", market_date=MON, status="skipped_holiday")
    now["now"] = MON_NIGHT
    served = api.get(f"{BASE}/stocks/DEMOIND", headers=USER).json()
    assert served["staleness"] == {"sessions_old": 0, "state": "fresh"}
    assert serve.sessions_old(D, MON_NIGHT, set()) == 1             # without the holiday row


def test_three_weekday_outage_expires_the_report(api, db, now):
    _seed(db, "no_edge.json")
    now["now"] = WED_NIGHT
    served = api.get(f"{BASE}/stocks/DEMOIND", headers=USER).json()
    assert served["staleness"] == {"sessions_old": 3, "state": "expired"}
    for outlook in served["outlooks"]:
        assert outlook["evidence_tier"] == "unavailable"
        assert "snapshot_expired" in outlook["reason_codes"]
        assert outlook["tier_text"] == TIER_TEXT["unavailable"]
    assert [h["tier_text"] for h in served["model_card"]["horizons"]] == [TIER_TEXT["unavailable"]] * 2


def test_staleness_calendar_arithmetic():
    assert serve.last_due_weekday(FRI_NIGHT) == D
    assert serve.last_due_weekday(datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)) == date(2026, 10, 8)  # Fri 20:30
    assert serve.last_due_weekday(datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc)) == D                 # Sat 22:30
    assert serve.staleness(D, FRI_NIGHT, set()) == {"sessions_old": 0, "state": "fresh"}
    assert serve.staleness(D, WED_MORNING, set()) == {"sessions_old": 2, "state": "stale"}
    assert serve.staleness(D, WED_NIGHT, {MON, MON}) == {"sessions_old": 2, "state": "stale"}


# ---------------------------------------------------------------------------
# Tiers and cohort (spec 5.6, D9, D37)
# ---------------------------------------------------------------------------

def test_tier_only_strips_the_cohort_and_validated_without_live_gate_is_weak(api, db):
    row = _seed(db, "validated_cohort.json")
    served = api.get(f"{BASE}/stocks/SAMPLEFIN", headers=USER).json()
    o21, o63 = _outlook(served, 21), _outlook(served, 63)
    assert o21["cohort"] is None
    assert o21["evidence_tier"] == "weak_evidence"
    assert "live_shadow_collecting" in o21["reason_codes"] and "policy_hidden" in o21["reason_codes"]
    assert o21["tier_text"] == TIER_TEXT["weak_evidence"]
    assert (o63["evidence_tier"], o63["reason_codes"]) == ("weak_evidence", ["gate_failed:G1"])
    preds = {p.horizon_days: p.id for p in repo.predictions_for_report(db, row.id)}
    assert (o21["prediction_id"], o63["prediction_id"]) == (preds[21], preds[63])
    assert served["compliance"]["outlook_display"] == "tier_only"
    assert served["compliance"]["track_record_visible"] is False


def test_under_review_serves_no_reliable_edge(api, db):
    _seed(db, "validated_cohort.json")
    _live(db, 21, status="under_review")
    served = api.get(f"{BASE}/stocks/SAMPLEFIN", headers=USER).json()
    o21 = _outlook(served, 21)
    assert o21["evidence_tier"] == "no_reliable_edge" and "live_under_review" in o21["reason_codes"]
    assert o21["tier_text"] == TIER_TEXT["no_reliable_edge"]
    record = served["live_track_record"]
    assert record["visible"] is False
    assert record["horizons"][0] == {
        "horizon_days": 21, "state": "under_review", "since": "2025-06-02", "matured_dates": 300,
        "independent_periods": 14, "min_periods_required": 12,
    }
    assert record["horizons"][1]["state"] == "collecting"
    assert "rank_ic" not in json.dumps(record)                      # states only


def test_validated_with_live_gate_but_no_registration_is_weak_policy_hidden(api, db):
    _seed(db, "validated_cohort.json")
    _live(db, 21, status="ok", gate=True)
    o21 = _outlook(api.get(f"{BASE}/stocks/SAMPLEFIN", headers=USER).json(), 21)
    assert o21["evidence_tier"] == "weak_evidence"
    assert "policy_hidden" in o21["reason_codes"] and "live_shadow_collecting" not in o21["reason_codes"]


def _row(name: str) -> SimpleNamespace:
    return SimpleNamespace(report_json=_stored(name), as_of_date=D, narrative_json=None)


def _live_row(horizon: int, status: str = "ok", gate: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        procedure_id=PROCEDURE, horizon_days=horizon, live_status=status, live_gate_passed=gate,
        matured_dates=300, metrics_json={"independent_periods": 14, "metrics": {"window": None}},
    )


def test_policy_keeps_validated_and_cohort_only_with_gate_registration_and_cohort_display():
    registered = config.ResearchConfig(mode="on", outlook_display="cohort_frequency", sebi_ra_reg_no="INH000000001")
    served = serve.serve_report(_row("validated_cohort.json"), [], [_live_row(21)], set(), registered, FRI_NIGHT)
    o21 = _outlook(served, 21)
    assert o21["evidence_tier"] == "validated_edge" and o21["reason_codes"] == []
    assert o21["cohort"]["bucket"] == 4 and o21["tier_text"] == TIER_TEXT["validated_edge"]

    tier_only = config.ResearchConfig(mode="on", sebi_ra_reg_no="INH000000001")
    o21 = _outlook(serve.serve_report(_row("validated_cohort.json"), [], [_live_row(21)], set(), tier_only, FRI_NIGHT), 21)
    assert o21["evidence_tier"] == "validated_edge" and o21["cohort"] is None and o21["reason_codes"] == ["policy_hidden"]

    other = SimpleNamespace(**{**vars(_live_row(21)), "procedure_id": "another-procedure"})
    o21 = _outlook(serve.serve_report(_row("validated_cohort.json"), [], [other], set(), registered, FRI_NIGHT), 21)
    assert o21["evidence_tier"] == "weak_evidence" and "live_shadow_collecting" in o21["reason_codes"]


def test_out_of_universe_tier_is_kept_and_served_json_has_no_forbidden_keys():
    flags = config.ResearchConfig(mode="on")
    for name in ("no_edge.json", "validated_cohort.json", "out_of_universe_degraded.json"):
        served = serve.serve_report(_row(name), [], [], set(), flags, FRI_NIGHT)
        assert _forbidden_keys(served) == [], name
        assert served["compliance"]["disclaimer_id"] == "research_v1"
        assert served["narrative"]["status"] == "template"
    ooo = serve.serve_report(_row("out_of_universe_degraded.json"), [], [], set(), flags, FRI_NIGHT)
    assert {o["evidence_tier"] for o in ooo["outlooks"]} == {"out_of_universe"}
    assert ooo["outlooks"][0]["tier_text"] == TIER_TEXT["out_of_universe"]


# ---------------------------------------------------------------------------
# On-demand compute (spec 9.1, D23)
# ---------------------------------------------------------------------------

def test_compute_unknown_symbol_passes_through_404(api, db, engine):
    engine.compute_fn = lambda symbol: EngineResponse(404, {"code": "UNKNOWN_SYMBOL"})
    resp = api.post(f"{BASE}/stocks/NOPE/compute", headers=USER)
    assert (resp.status_code, _code(resp)) == (404, "UNKNOWN_SYMBOL")
    assert db.query(ResearchReportRow).count() == 0


def test_compute_engine_errors_map_to_422_and_503(api, db, engine):
    engine.compute_fn = lambda symbol: EngineResponse(422, {"detail": "under 60 sessions"})
    resp = api.post(f"{BASE}/stocks/NEWCO/compute", headers=USER)
    assert (resp.status_code, _code(resp)) == (422, "INSUFFICIENT_HISTORY")

    def _down(symbol: str) -> EngineResponse:
        raise MLEngineUnavailable("POST /research/v1/compute", None, "ConnectTimeout")

    engine.compute_fn = _down
    resp = api.post(f"{BASE}/stocks/NEWCO/compute", headers=USER)
    assert (resp.status_code, _code(resp)) == (503, "COMPUTE_UNAVAILABLE")
    assert resp.headers["retry-after"] == "300"
    assert db.query(ResearchReportRow).count() == 0


def test_compute_attempt_rate_limit_returns_429(api, engine):
    engine.compute_fn = lambda symbol: EngineResponse(404, {"code": "UNKNOWN_SYMBOL"})
    for _ in range(20):
        assert api.post(f"{BASE}/stocks/NOPE/compute", headers=USER).status_code == 404
    limited = api.post(f"{BASE}/stocks/NOPE/compute", headers=USER)
    assert limited.status_code == 429 and "retry-after" in limited.headers
    assert len(engine.compute_calls) == 20
    assert api.post(f"{BASE}/stocks/NOPE/compute", headers={"Authorization": "Bearer other-token"}).status_code == 404


def test_compute_persists_on_demand_without_predictions_and_quota_counts_only_new_rows(api, db, engine):
    repo.create_run(db, kind="nightly", market_date=D, status="ok")   # latest market date = D

    first = api.post(f"{BASE}/stocks/NEWCO0/compute", headers=USER)
    assert first.status_code == 200
    served = first.json()
    assert served["symbol"] == "NEWCO0" and served["origin"] == "on_demand"
    assert served["narrative"]["status"] == "template"
    assert all(o["prediction_id"] is None for o in served["outlooks"])
    for _ in range(3):                                                   # reuse: no engine call, not counted
        assert api.post(f"{BASE}/stocks/NEWCO0/compute", headers=USER).status_code == 200
    assert engine.compute_calls == ["NEWCO0"]

    for i in range(1, 10):
        assert api.post(f"{BASE}/stocks/NEWCO{i}/compute", headers=USER).status_code == 200
    eleventh = api.post(f"{BASE}/stocks/NEWCO10/compute", headers=USER)
    assert (eleventh.status_code, _code(eleventh)) == (429, "QUOTA_EXCEEDED")
    assert int(eleventh.headers["retry-after"]) > 0
    assert len(engine.compute_calls) == 10
    assert api.post(f"{BASE}/stocks/NEWCO3/compute", headers=USER).status_code == 200   # reuse still served

    rows = db.query(ResearchReportRow).all()
    assert len(rows) == 10
    assert {(r.origin, r.requested_by_user_id, r.in_universe) for r in rows} == {("on_demand", USER_ID, False)}
    assert db.query(ResearchPrediction).count() == 0
    assert api.post(f"{BASE}/stocks/NEWCO10/compute", headers={"Authorization": "Bearer other-token"}).status_code == 200


def test_compute_reuses_a_nightly_report_for_the_latest_market_date(api, db, engine):
    _seed(db, "no_edge.json")
    resp = api.post(f"{BASE}/stocks/DEMOIND/compute", headers=USER)
    assert resp.status_code == 200 and resp.json()["origin"] == "nightly"
    assert engine.compute_calls == []


# ---------------------------------------------------------------------------
# ARCH-23 static guard
# ---------------------------------------------------------------------------

def test_research_code_never_imports_the_legacy_pipeline():
    banned = ("tradingagents", "services.orchestrator", "quant_engine", "confidence_fusion")
    files = sorted((BACKEND / "services" / "research").glob("*.py")) + [BACKEND / "routers" / "research.py"]
    assert len(files) > 5
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module or ''}.{alias.name}" for alias in node.names]
            for name in names:
                assert not any(b in name for b in banned), f"{path.name} imports {name}"
