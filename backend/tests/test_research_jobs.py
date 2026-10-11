"""Research Engine config, ml-engine client and scheduler job tests (spec 2.2, 9.3, 11.2).

Hermetic: a fresh in-memory SQLite database per test (FKs on), ``jobs.get_session``
patched to yield it, a fake ml-engine client, telemetry mocked and no LLM call
(``formatter.generate_narrative`` is patched). The client tests use
``httpx.MockTransport``; nothing touches the network.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core import dashboard_state
from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    Base,
    Portfolio,
    ResearchLiveMetric,
    ResearchPrediction,
    ResearchReportRow,
    ResearchRun,
    User,
    Watchlist,
)
from repositories import research_repo as repo
from services import error_telemetry
from services.research import config, jobs
from services.research.client import EngineResponse, MLEngineClient, MLEngineError, MLEngineUnavailable

D = date(2026, 10, 9)                                            # a Friday
EVENING = datetime(2026, 10, 9, 14, 20, tzinfo=timezone.utc)     # Fri 19:50 IST
MORNING = datetime(2026, 10, 10, 1, 50, tzinfo=timezone.utc)     # Sat 07:20 IST -> previous weekday
PROSE_TIME = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)   # Fri 20:30 IST (in the window)
OFF_WINDOW = datetime(2026, 10, 9, 2, 30, tzinfo=timezone.utc)   # Fri 08:00 IST


# ---------------------------------------------------------------------------
# Fixtures and fakes
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")

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
def research_on(monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(mode="on", ml_engine_api_key="test-key"))


@pytest.fixture(autouse=True)
def db(monkeypatch, session):
    @contextmanager
    def _get_session():
        yield session

    monkeypatch.setattr(jobs, "get_session", _get_session)
    return session


@pytest.fixture(autouse=True)
def telemetry(monkeypatch):
    mock = MagicMock(return_value="err-uuid")
    monkeypatch.setattr(error_telemetry, "log_diagnostic_error", mock)
    return mock


@pytest.fixture(autouse=True)
def reset_dashboard(monkeypatch):
    monkeypatch.setitem(
        dashboard_state._harvest_status, "research_nightly", {"status": "idle", "last_run": None, "last_result": None},
    )


class FakeEngine:
    """Records calls; responses are set per test."""

    def __init__(self) -> None:
        self.start_response = EngineResponse(202, {"run_id": "run-1", "status": "running"})
        self.start_error: Exception | None = None
        self.statuses: dict[str, dict[str, Any] | None] = {}
        self.items: dict[str, list[dict[str, Any]]] = {}
        self.outcome_fn = lambda items: {"results": [], "last_session": None}
        self.live_response: dict[str, Any] = {}
        self.start_calls: list[tuple[date, list[str]]] = []
        self.outcome_calls: list[list[dict[str, Any]]] = []
        self.live_calls: list[dict[str, Any]] = []

    def start_run(self, market_date: date, extra_symbols: list[str]) -> EngineResponse:
        self.start_calls.append((market_date, list(extra_symbols)))
        if self.start_error is not None:
            raise self.start_error
        return self.start_response

    def run_status(self, run_id: str) -> dict[str, Any] | None:
        return self.statuses.get(run_id, {"status": "running", "stage": "features"})

    def run_items(self, run_id: str) -> list[dict[str, Any]]:
        return self.items.get(run_id, [])

    def outcomes(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        self.outcome_calls.append(items)
        return self.outcome_fn(items)

    def live_metrics(self, request: dict[str, Any]) -> dict[str, Any]:
        self.live_calls.append(request)
        return self.live_response


def _engine(fake: FakeEngine) -> MLEngineClient:
    return cast(MLEngineClient, fake)


def _report(symbol: str, as_of: str = D.isoformat(), *, in_universe: bool = True, origin: str = "nightly") -> dict:
    return {
        "schema_version": "research.v1",
        "report_id": str(uuid.uuid4()),
        "engine_version": "re-1.0.0+fv1",
        "origin": origin,
        "status": "ok",
        "degraded_reasons": [],
        "symbol": symbol,
        "exchange": "NSE",
        "isin": None,
        "company_name": f"{symbol} Ltd",
        "as_of": {"market_date": as_of, "computed_at": f"{as_of}T14:00:00Z"},
        "coverage": {"universe_id": "NSE_LIQ200", "in_universe": in_universe},
        "model_card": {"procedure_id": "lgbm-rank-v1"},
    }


def _pred(horizon: int, *, reason_codes: list[str] | None = None) -> dict:
    return {
        "horizon_days": horizon,
        "procedure_id": "lgbm-rank-v1",
        "model_id": f"lgbm-rank-v1-h{horizon}",
        "manifest_sha256": "a" * 64,
        "universe_id": "NSE_LIQ200",
        "evidence_tier": "no_reliable_edge",
        "reason_codes": reason_codes if reason_codes is not None else ["gate_failed:G1"],
        "score": 0.12,
        "rank_pct": 0.61,
        "bucket": 4,
        "p_top_half": 0.53,
        "entry_close": 3512.25,
        "feature_hash": "f" * 64,
        "expected_maturity_date": "2026-11-09" if horizon == 21 else "2027-01-08",
    }


def _item(symbol: str, **kwargs) -> dict:
    return {"report": _report(symbol), "predictions": [_pred(21, **kwargs), _pred(63, **kwargs)]}


def _running_row(session, run_uid: str | None, started: datetime, market_date: date = D) -> int:
    run_id = repo.create_run(session, kind="nightly", market_date=market_date, run_uid=run_uid).id
    session.query(ResearchRun).filter(ResearchRun.id == run_id).update({"started_at": started.replace(tzinfo=None)})
    session.commit()
    return run_id


def _ingested(session, symbols: list[str], *, market_date: date = D, status: str = "ok", **kwargs) -> int:
    run_id = repo.create_run(session, kind="nightly", market_date=market_date, status=status).id
    repo.ingest_run_items(session, run_id, [_item(s, **kwargs) for s in symbols])
    return run_id


def _run(session, run_id: int) -> ResearchRun:
    session.expire_all()
    row = session.get(ResearchRun, run_id)
    assert row is not None
    return row


def _classifications(telemetry: MagicMock) -> list[str]:
    for call in telemetry.call_args_list:
        assert call.kwargs["subsystem"] == "RESEARCH_ENGINE"
    return [call.kwargs["classification"] for call in telemetry.call_args_list]


# ---------------------------------------------------------------------------
# Kick
# ---------------------------------------------------------------------------

def test_target_market_date():
    assert jobs.target_market_date(EVENING) == D
    assert jobs.target_market_date(MORNING) == D                        # Sat 07:15 -> Fri
    assert jobs.target_market_date(datetime(2026, 10, 13, 1, 50, tzinfo=timezone.utc)) == date(2026, 10, 12)  # Tue -> Mon


def test_kick_starts_a_run_and_is_idempotent(db):
    fake = FakeEngine()
    result = jobs.research_nightly_kick(now=EVENING, client=_engine(fake))
    assert result["outcome"] == "started"
    row = db.query(ResearchRun).one()
    assert (row.kind, row.market_date, row.status, row.run_uid) == ("nightly", D, "running", "run-1")

    again = jobs.research_nightly_kick(now=EVENING + timedelta(minutes=75), client=_engine(fake))
    assert again["outcome"] == "already_running"
    assert len(fake.start_calls) == 1 and db.query(ResearchRun).count() == 1

    status = dashboard_state._harvest_status["research_nightly"]
    assert status["last_result"]["outcome"] == "already_running"


def test_kick_records_holiday_and_does_not_rekick(db):
    fake = FakeEngine()
    fake.start_response = EngineResponse(200, {"run_id": "hol-1", "status": "skipped_holiday"})
    assert jobs.research_nightly_kick(now=MORNING, client=_engine(fake))["outcome"] == "skipped_holiday"
    row = db.query(ResearchRun).one()
    assert (row.market_date, row.status) == (D, "skipped_holiday")
    assert repo.holiday_dates_after(db, D - timedelta(days=1)) == {D}

    assert jobs.research_nightly_kick(now=MORNING, client=_engine(fake))["outcome"] == "already_skipped_holiday"
    assert len(fake.start_calls) == 1


def test_kick_sweeps_a_four_hour_old_running_row_and_starts_a_new_run(db, telemetry):
    old = _running_row(db, None, EVENING - timedelta(hours=4))
    fake = FakeEngine()
    result = jobs.research_nightly_kick(now=EVENING, client=_engine(fake))
    assert result["swept"] == 1 and result["outcome"] == "started"
    assert (_run(db, old).status, _run(db, old).error) == ("failed", "stale_run")
    new = db.query(ResearchRun).filter(ResearchRun.id != old).one()
    assert (new.status, new.run_uid) == ("running", "run-1")
    assert _classifications(telemetry) == ["stale_sweep"]
    assert telemetry.call_args.kwargs["context"]["swept"] == [
        {"run_id": old, "market_date": D.isoformat(), "cause": "older_than_3h"},
    ]


def test_kick_marks_an_engine_404_run_failed(db, telemetry):
    gone = _running_row(db, "gone-1", EVENING - timedelta(minutes=10))
    fake = FakeEngine()
    fake.statuses["gone-1"] = None  # ml-engine 404
    result = jobs.research_nightly_kick(now=EVENING, client=_engine(fake))
    assert result["swept"] == 1 and result["outcome"] == "started"
    assert (_run(db, gone).status, _run(db, gone).error) == ("failed", "stale_run")
    assert len(fake.start_calls) == 1
    assert _classifications(telemetry) == ["stale_sweep"]
    assert telemetry.call_args.kwargs["context"]["swept"][0]["cause"] == "engine_404"


def test_kick_409_stores_the_returned_run_id_when_the_date_matches(db):
    fake = FakeEngine()
    fake.start_response = EngineResponse(409, {"run_id": "active-1", "market_date": D.isoformat()})
    assert jobs.research_nightly_kick(now=EVENING, client=_engine(fake))["outcome"] == "attached_active_run"
    row = db.query(ResearchRun).one()
    assert (row.status, row.run_uid) == ("running", "active-1")


def test_kick_409_for_another_date_is_engine_busy(db, telemetry):
    fake = FakeEngine()
    fake.start_response = EngineResponse(409, {"run_id": "active-1", "market_date": "2026-10-08"})
    assert jobs.research_nightly_kick(now=EVENING, client=_engine(fake))["outcome"] == "engine_busy"
    row = db.query(ResearchRun).one()
    assert (row.status, row.error, row.run_uid) == ("failed", "engine_busy", None)
    assert "kick" in _classifications(telemetry)


def test_kick_moves_a_reused_run_id_from_an_older_failed_row(db):
    old = _running_row(db, "run-1", EVENING - timedelta(hours=1))
    repo.mark_run_failed(db, old, "ingest_failed")
    fake = FakeEngine()
    fake.start_response = EngineResponse(200, {"run_id": "run-1", "status": "ok"})  # finished run for D
    assert jobs.research_nightly_kick(now=EVENING, client=_engine(fake))["outcome"] == "started"
    new = db.query(ResearchRun).filter(ResearchRun.id != old).one()
    assert (new.status, new.run_uid) == ("running", "run-1")
    assert _run(db, old).run_uid is None


def test_kick_sends_symbols_only(db):
    users = []
    for name in ("u1", "u2"):
        u = User(username=name, password_hash="x", display_name=name)
        db.add(u)
        db.flush()
        users.append(cast(int, u.id))
    db.add_all([
        Portfolio(user_id=users[0], ticker="TCS.NS", company_name="TCS", shares=1, buy_price=100, group_name="holdings"),
        Portfolio(user_id=users[1], ticker="INFY.BO", company_name="Infosys", shares=1, buy_price=10, group_name="holdings"),
        Watchlist(user_id=users[1], ticker="tcs"),
    ])
    db.commit()
    fake = FakeEngine()
    jobs.research_nightly_kick(now=EVENING, client=_engine(fake))
    market_date, extra = fake.start_calls[0]
    assert market_date == D
    assert extra == ["TCS", "INFY"]
    assert all(isinstance(s, str) for s in extra)
    assert not set(extra) & {str(u) for u in users}


def test_kick_failure_marks_the_run_failed_and_reports_it(db, telemetry):
    fake = FakeEngine()
    fake.start_error = MLEngineUnavailable("POST /research/v1/runs", 503)
    result = jobs.research_nightly_kick(now=EVENING, client=_engine(fake))
    assert result["error"] == "MLEngineUnavailable"
    row = db.query(ResearchRun).one()
    assert (row.status, row.error) == ("failed", "engine_unavailable")
    assert _classifications(telemetry) == ["kick"]
    assert dashboard_state._harvest_status["research_nightly"]["status"] == "error"


# ---------------------------------------------------------------------------
# Poll and ingest
# ---------------------------------------------------------------------------

def test_poll_ingests_two_items_in_one_go(db):
    run_id = _running_row(db, "run-1", EVENING)
    fake = FakeEngine()
    fake.statuses["run-1"] = {"status": "ok", "counts": {"reports": 2, "predictions": 4}}
    fake.items["run-1"] = [_item("TCS"), _item("INFY")]
    result = jobs.research_poll_ingest(now=OFF_WINDOW, client=_engine(fake))
    assert result["runs"] == {str(run_id): "ok"}
    assert db.query(ResearchReportRow).count() == 2
    assert db.query(ResearchPrediction).count() == 4
    row = _run(db, run_id)
    counts = row.counts_json or {}
    assert row.status == "ok" and counts["reports_new"] == 2 and counts["predictions_new"] == 4
    status = dashboard_state._harvest_status["research_nightly"]
    assert status["status"] == "idle" and status["last_result"]["runs"] == {str(run_id): "ok"}


def test_poll_ingest_failure_rolls_back_and_fails_the_run(db, telemetry):
    run_id = _running_row(db, "run-1", EVENING)
    broken = _item("INFY")
    del broken["report"]["engine_version"]
    fake = FakeEngine()
    fake.statuses["run-1"] = {"status": "ok", "counts": {}}
    fake.items["run-1"] = [_item("TCS"), broken]
    jobs.research_poll_ingest(now=OFF_WINDOW, client=_engine(fake))
    assert db.query(ResearchReportRow).count() == 0
    assert db.query(ResearchPrediction).count() == 0
    row = _run(db, run_id)
    assert (row.status, row.error) == ("failed", "ingest_failed")
    assert "ingest" in _classifications(telemetry)
    assert dashboard_state._harvest_status["research_nightly"]["status"] == "error"


def test_poll_marks_404_and_failed_runs_failed(db):
    gone = _running_row(db, "gone-1", EVENING)
    dead = _running_row(db, "dead-1", EVENING, market_date=D - timedelta(days=1))
    fake = FakeEngine()
    fake.statuses["gone-1"] = None
    fake.statuses["dead-1"] = {"status": "failed", "error": "engine_restarted"}
    jobs.research_poll_ingest(now=OFF_WINDOW, client=_engine(fake))
    assert (_run(db, gone).status, _run(db, gone).error) == ("failed", "run_not_found")
    assert (_run(db, dead).status, _run(db, dead).error) == ("failed", "engine_restarted")


def test_poll_leaves_running_runs_running(db):
    run_id = _running_row(db, "run-1", EVENING)
    jobs.research_poll_ingest(now=OFF_WINDOW, client=_engine(FakeEngine()))
    row = _run(db, run_id)
    assert (row.status, row.stage) == ("running", "features")


# ---------------------------------------------------------------------------
# Prose
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_formatter(monkeypatch):
    from services.research import formatter

    calls: list[int] = []

    def _generate(report, *, known_symbols, company_names, allow_llm, calls_remaining):
        calls.append(calls_remaining)
        assert allow_llm is True
        return {"status": "llm_validated", "summary": "s", "sections": [], "facts_hash": "h" * 64}, 1, []

    monkeypatch.setattr(formatter, "generate_narrative", _generate)
    return calls


def test_prose_stops_at_the_daily_budget(db, monkeypatch, fake_formatter):
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(mode="on", ml_engine_api_key="k", llm_max_calls_per_day=3))
    _ingested(db, ["A", "B", "C", "D", "E"])
    result = jobs.research_poll_ingest(now=PROSE_TIME, client=_engine(FakeEngine()))
    assert fake_formatter == [3, 2, 1]
    assert result["prose_written"] == 3 and result["prose"] == "budget_exhausted"
    assert db.query(ResearchReportRow).filter(ResearchReportRow.narrative_json.isnot(None)).count() == 3


def test_prose_is_not_attempted_at_8am_ist(db, fake_formatter):
    _ingested(db, ["A", "B"])
    result = jobs.research_poll_ingest(now=OFF_WINDOW, client=_engine(FakeEngine()))
    assert fake_formatter == [] and result["prose"] == "skipped"
    assert db.query(ResearchReportRow).filter(ResearchReportRow.narrative_json.isnot(None)).count() == 0


def test_prose_in_shadow_covers_universe_reports_only(db, monkeypatch, fake_formatter):
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(mode="shadow", ml_engine_api_key="k"))
    run_id = repo.create_run(db, kind="nightly", market_date=D, status="ok").id
    repo.ingest_run_items(db, run_id, [
        _item("UNI"), {"report": _report("OFFU", in_universe=False), "predictions": []},
    ])
    jobs.research_poll_ingest(now=PROSE_TIME, client=_engine(FakeEngine()))
    with_prose = {r.symbol for r in db.query(ResearchReportRow).filter(ResearchReportRow.narrative_json.isnot(None))}
    assert with_prose == {"UNI"}


# ---------------------------------------------------------------------------
# Outcomes and live metrics
# ---------------------------------------------------------------------------

def test_scoring_writes_once_and_counts_voids(db):
    _ingested(db, ["TCS", "INFY"])
    repo.create_run(db, kind="nightly", market_date=date(2027, 1, 8), status="ok")  # every prediction matured

    def _score(items):
        results = []
        for i, it in enumerate(items):
            void = i == 0
            results.append({
                "prediction_id": it["prediction_id"],
                "outcome_status": "void" if void else "matured",
                "void_reason": "entry_price_mismatch" if void else None,
                "realized_return_pct": None if void else 2.5,
                "realized_excess_pp": None if void else 0.4,
                "realized_top_half": None if void else True,
                "nifty50_return_pct": None if void else 1.0,
                "stale_exit": None if void else False,
                "scorer_version": "os-2",
            })
        results.append({**results[-1], "prediction_id": 999_999})  # not sent: ignored
        return {"results": results, "last_session": "2027-01-08"}

    fake = FakeEngine()
    fake.outcome_fn = _score
    first = jobs.research_score_outcomes(client=_engine(fake))
    assert first["counts"] == {"sent": 4, "matured": 3, "void": 1, "pending": 0, "written": 4}
    sent = fake.outcome_calls[0][0]
    assert set(sent) == {"prediction_id", "isin", "symbol", "as_of", "horizon_days", "entry_close"}
    assert db.query(ResearchPrediction).filter(ResearchPrediction.outcome_status == "void").count() == 1

    second = jobs.research_score_outcomes(client=_engine(fake))
    assert second["counts"]["written"] == 0 and len(fake.outcome_calls) == 1

    heartbeats = db.query(ResearchRun).filter(ResearchRun.kind == "outcomes").all()
    assert [h.status for h in heartbeats] == ["ok", "ok"]


def test_live_metrics_stores_a_row_and_excludes_fallback_predictions(db):
    _ingested(db, ["TCS"])
    _ingested(db, ["INFY"], reason_codes=["gate_failed:G1", "prices_fallback_yfinance"])
    matured = {"outcome_status": "matured", "realized_excess_pp": 0.5, "realized_top_half": True,
               "stale_exit": False, "scorer_version": "os-2"}
    for pid, in db.query(ResearchPrediction.id).filter(ResearchPrediction.horizon_days == 21).all():
        assert repo.write_outcome_once(db, pid, matured)

    fake = FakeEngine()
    fake.live_response = {"live_status": "collecting", "live_gate_passed": False, "matured_n": 1, "void_n": 0,
                          "stale_exit_n": 0, "matured_dates": 1, "independent_periods": 0, "metrics": {}, "alarms": []}
    result = jobs.research_live_metrics(now=EVENING, client=_engine(fake))
    assert result["stored"] == 1
    assert len(fake.live_calls) == 1  # 63d has no matured rows
    request = fake.live_calls[0]
    assert (request["procedure_id"], request["horizon_days"]) == ("lgbm-rank-v1", 21)
    assert [r["symbol"] for r in request["rows"]] == ["TCS"]
    row = db.query(ResearchLiveMetric).one()
    assert (row.horizon_days, row.live_status, row.computed_on) == (21, "collecting", D)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def test_cleanup_prunes_per_retention(db):
    today = EVENING.date()
    run_id = repo.create_run(db, kind="nightly", market_date=D, status="ok").id
    repo.ingest_run_items(db, run_id, [
        {"report": _report("OLDUNI", (today - timedelta(days=401)).isoformat()), "predictions": [_pred(21)]},
        {"report": _report("NEWUNI", (today - timedelta(days=10)).isoformat()), "predictions": []},
    ])
    repo.insert_on_demand_report(db, _report("ODOLD", (today - timedelta(days=31)).isoformat(), origin="on_demand"), None)
    result = jobs.research_cleanup(now=EVENING)
    assert result["pruned"] == 2
    db.expire_all()
    assert {r.symbol for r in db.query(ResearchReportRow).all()} == {"NEWUNI"}
    assert db.query(ResearchPrediction).one().report_id is None  # the prediction survives


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_adds_seven_jobs_with_the_spec_cron_fields():
    scheduler = MagicMock()
    assert jobs.register_research_jobs(scheduler) == 7
    assert scheduler.add_job.call_count == 7
    calls = {c.kwargs["id"]: c for c in scheduler.add_job.call_args_list}
    poll = calls["research_poll_ingest"]
    assert poll.args == (jobs.research_poll_ingest, "cron")
    assert (poll.kwargs["day_of_week"], poll.kwargs["hour"], poll.kwargs["minute"]) == ("mon-sat", "1-3,14-18", "*/5")
    kicks = [c for c in calls.values() if c.args[0] is jobs.research_nightly_kick]
    assert sorted((c.kwargs["day_of_week"], c.kwargs["hour"], c.kwargs["minute"]) for c in kicks) == [
        ("mon-fri", 14, 15), ("mon-fri", 15, 30), ("tue-sat", 1, 45),
    ]
    assert (calls["research_cleanup"].kwargs["hour"], calls["research_cleanup"].kwargs["minute"]) == (21, 0)
    for c in calls.values():
        assert (c.kwargs["max_instances"], c.kwargs["coalesce"], c.kwargs["misfire_grace_time"]) == (1, True, 3600)


def test_register_adds_no_jobs_when_off(monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.ResearchConfig(mode="off"))
    scheduler = MagicMock()
    assert jobs.register_research_jobs(scheduler) == 0
    scheduler.add_job.assert_not_called()
    assert jobs.research_nightly_kick(now=EVENING, client=_engine(FakeEngine())) == {"skipped": "research_off"}


# ---------------------------------------------------------------------------
# Config (spec 9.3, D36)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("env, reason", [
    ({"RESEARCH_ENGINE_MODE": "on"}, "config_invalid:ML_ENGINE_API_KEY"),
    ({"RESEARCH_ENGINE_MODE": "sideways", "ML_ENGINE_API_KEY": "k"}, "config_invalid:RESEARCH_ENGINE_MODE"),
    ({"RESEARCH_ENGINE_MODE": "on", "ML_ENGINE_API_KEY": "k", "RESEARCH_SEBI_RA_REG_NO": "INH12"},
     "config_invalid:RESEARCH_SEBI_RA_REG_NO"),
    ({"RESEARCH_ENGINE_MODE": "on", "ML_ENGINE_API_KEY": "k", "RESEARCH_SEBI_RA_REG_NO": "INH000001234"},
     "config_invalid:RESEARCH_SEBI_RA_REG_NO_without_disclaimer"),
    ({"RESEARCH_ENGINE_MODE": "on", "ML_ENGINE_API_KEY": "k", "RESEARCH_OUTLOOK_DISPLAY": "cohort_frequency"},
     "config_invalid:RESEARCH_OUTLOOK_DISPLAY_needs_registration"),
    ({"RESEARCH_ENGINE_MODE": "shadow", "ML_ENGINE_API_KEY": "k", "RESEARCH_TRACK_RECORD_PUBLIC": "true"},
     "config_invalid:RESEARCH_TRACK_RECORD_PUBLIC_needs_registration"),
    ({"RESEARCH_ENGINE_MODE": "on", "ML_ENGINE_API_KEY": "k", "RESEARCH_LLM_MAX_CALLS_PER_DAY": "lots"},
     "config_invalid:RESEARCH_LLM_MAX_CALLS_PER_DAY"),
])
def test_invalid_config_fails_closed_without_raising(monkeypatch, env, reason):
    monkeypatch.setattr(config, "CONFIG", config.CONFIG)  # restored after the test
    cfg = config.load({**env, "RESEARCH_LEGACY_RETIRED": "true"})
    assert cfg is config.CONFIG
    assert reason in cfg.degraded_reasons and cfg.degraded
    assert (cfg.mode, cfg.outlook_display, cfg.track_record_public, cfg.sebi_ra_reg_no) == ("off", "tier_only", False, None)
    assert cfg.legacy_retired is True and config.LEGACY_RETIRED is True  # D24: independent of the mode
    assert config.MODE == "off" and reason in config.DEGRADED_REASONS


def test_valid_config_and_defaults(monkeypatch):
    monkeypatch.setattr(config, "CONFIG", config.CONFIG)
    cfg = config.load({"RESEARCH_ENGINE_MODE": "Shadow", "ML_ENGINE_API_KEY": "secret-value", "ML_ENGINE_URL": "http://127.0.0.1:8001/"})
    assert (cfg.mode, cfg.degraded_reasons, cfg.ml_engine_url) == ("shadow", (), "http://127.0.0.1:8001")
    assert "secret-value" not in repr(cfg)
    defaults = config.load({})
    assert (defaults.mode, defaults.enabled, defaults.degraded) == ("off", False, False)
    assert (defaults.llm_prose, defaults.llm_max_calls_per_day, defaults.compute_daily_quota) == (True, 800, 10)


# ---------------------------------------------------------------------------
# Client (httpx.MockTransport; no network)
# ---------------------------------------------------------------------------

def _client(handler) -> MLEngineClient:
    return MLEngineClient("http://engine.test", "test-key", transport=httpx.MockTransport(handler))


def test_client_sends_the_key_and_maps_statuses():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/research/v1/runs":
            return httpx.Response(409, json={"run_id": "r9", "market_date": "2026-10-09"})
        if path == "/research/v1/runs/missing":
            return httpx.Response(404, json={"detail": "not found"})
        if path == "/research/v1/runs/r9/items":
            offset = int(request.url.params["offset"])
            return httpx.Response(200, json={"items": [{"n": offset}], "next_offset": 200 if offset == 0 else None})
        return httpx.Response(503, json={"ready": False, "reasons": ["manifest_invalid"]})

    client = _client(handler)
    assert client.start_run(D, ["TCS"]) == EngineResponse(409, {"run_id": "r9", "market_date": "2026-10-09"})
    assert client.run_status("missing") is None
    assert client.run_items("r9") == [{"n": 0}, {"n": 200}]
    assert client.ready() == {"ready": False, "reasons": ["manifest_invalid"]}
    with pytest.raises(MLEngineUnavailable):
        client.outcomes([])
    assert all(r.headers["X-ML-Engine-Key"] == "test-key" for r in seen)
    assert "test-key" not in repr(client)


def test_client_timeout_is_unavailable_and_4xx_is_an_error():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(MLEngineUnavailable):
        _client(timeout).run_status("r1")
    assert _client(timeout).ready() == {"ready": False, "reasons": ["ml_engine_unreachable"]}

    unauthorised = _client(lambda request: httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(MLEngineError) as exc:
        unauthorised.model_card()
    assert exc.value.status_code == 401 and not isinstance(exc.value, MLEngineUnavailable)
