"""Research Engine ledger repository tests (spec §8, §11.2).

Hermetic: a fresh in-memory SQLite database per test (Base.metadata.create_all)
with foreign keys enforced, so ON DELETE SET NULL behaves as on Postgres.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models.db_models import (
    Base,
    Portfolio,
    ResearchPrediction,
    ResearchReportRow,
    StockUniverse,
    User,
    Watchlist,
)
from repositories import research_repo as repo

AS_OF = "2026-10-09"
MATURITY_21 = "2026-11-09"
MATURITY_63 = "2027-01-08"


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


_uid_counter = iter(range(1, 10_000))


def _report(symbol: str = "TCS", as_of: str = AS_OF, *, in_universe: bool = True, origin: str = "nightly") -> dict:
    return {
        "schema_version": "research.v1",
        "report_id": f"00000000-0000-4000-8000-{next(_uid_counter):012d}",
        "engine_version": "re-1.0.0+fv1",
        "origin": origin,
        "status": "ok",
        "degraded_reasons": [],
        "symbol": symbol,
        "exchange": "NSE",
        "isin": "INE467B01029",
        "company_name": f"{symbol} Ltd",
        "as_of": {"market_date": as_of, "computed_at": f"{as_of}T14:00:00Z"},
        "coverage": {"universe_id": "NSE_LIQ200", "in_universe": in_universe},
        "model_card": {"procedure_id": "lgbm-rank-v1"},
    }


def _pred(horizon: int, *, model_id: str = "lgbm-rank-v1-h", reason_codes: list[str] | None = None) -> dict:
    return {
        "horizon_days": horizon,
        "procedure_id": "lgbm-rank-v1",
        "model_id": f"{model_id}{horizon}",
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
        "expected_maturity_date": MATURITY_21 if horizon == 21 else MATURITY_63,
    }


def _nightly_run(session, market_date: date = date(2026, 10, 9)) -> int:
    return repo.create_run(session, kind="nightly", market_date=market_date).id


def _ingest_one(session, symbol: str = "TCS", **kwargs) -> int:
    """Ingest one report with both horizons; return the 21d prediction id."""
    run_id = _nightly_run(session)
    repo.ingest_run_items(session, run_id, [{"report": _report(symbol), "predictions": [_pred(21, **kwargs), _pred(63, **kwargs)]}])
    return (
        session.query(ResearchPrediction.id)
        .filter(ResearchPrediction.symbol == symbol, ResearchPrediction.horizon_days == 21)
        .scalar()
    )


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def test_ingest_one_prediction_per_report_horizon_and_idempotent(session):
    run_id = _nightly_run(session)
    items = [
        {"report": _report("TCS"), "predictions": [_pred(21), _pred(63), _pred(21)]},  # duplicate 21d skipped
        {"report": _report("INFY"), "predictions": [_pred(21), _pred(63)]},
    ]

    assert repo.ingest_run_items(session, run_id, items) == {
        "reports_new": 2, "reports_existing": 0, "predictions_new": 4,
    }
    # Re-ingest of the same items is a no-op.
    assert repo.ingest_run_items(session, run_id, items) == {
        "reports_new": 0, "reports_existing": 2, "predictions_new": 0,
    }
    assert session.query(ResearchReportRow).count() == 2
    assert session.query(ResearchPrediction).count() == 4

    tcs = repo.latest_report(session, "tcs.ns")
    assert tcs is not None and tcs.origin == "nightly" and tcs.run_id == run_id
    preds = repo.predictions_for_report(session, tcs.id)
    assert [p.horizon_days for p in preds] == [21, 63]
    assert all(p.outcome_status == "pending" for p in preds)
    assert preds[0].symbol == "TCS" and preds[0].as_of_date == date(2026, 10, 9)

    # The DB itself enforces one prediction per (report, horizon).
    session.add(ResearchPrediction(
        report_id=tcs.id, symbol="TCS", as_of_date=date(2026, 10, 9), horizon_days=21,
        procedure_id="lgbm-rank-v1", model_id="other-model", manifest_sha256="b" * 64,
        universe_id="NSE_LIQ200", evidence_tier="no_reliable_edge", score=0.0, rank_pct=0.5,
        entry_close=1.0, expected_maturity_date=date(2026, 11, 9),
    ))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_ingest_is_one_transaction(session):
    run_id = _nightly_run(session)
    bad = _pred(63)
    del bad["score"]
    items = [
        {"report": _report("TCS"), "predictions": [_pred(21), _pred(63)]},
        {"report": _report("INFY"), "predictions": [_pred(21), bad]},
    ]
    with pytest.raises(KeyError):
        repo.ingest_run_items(session, run_id, items)
    assert session.query(ResearchReportRow).count() == 0
    assert session.query(ResearchPrediction).count() == 0


# ---------------------------------------------------------------------------
# Write-once rules
# ---------------------------------------------------------------------------

def test_write_outcome_once(session):
    pid = _ingest_one(session)
    result = {
        "prediction_id": pid, "outcome_status": "matured", "void_reason": None,
        "realized_return_pct": 4.2, "realized_excess_pp": 1.1, "realized_top_half": True,
        "nifty50_return_pct": 3.1, "stale_exit": False, "scorer_version": "os-2",
    }
    assert repo.write_outcome_once(session, pid, result) is True
    assert repo.write_outcome_once(session, pid, {**result, "realized_return_pct": -9.9}) is False

    session.expire_all()
    row = session.get(ResearchPrediction, pid)
    assert row is not None
    assert row.outcome_status == "matured"
    assert row.realized_return_pct == pytest.approx(4.2)
    assert row.scorer_version == "os-2" and row.scored_at is not None
    assert float(row.entry_close) == pytest.approx(3512.25)  # prediction columns untouched

    other = session.query(ResearchPrediction).filter(ResearchPrediction.id != pid).one()
    assert repo.write_outcome_once(session, other.id, {"outcome_status": "pending"}) is False
    session.expire_all()
    assert session.get(ResearchPrediction, other.id).outcome_status == "pending"


def test_set_narrative_once_and_llm_call_count(session):
    _ingest_one(session)
    report = repo.latest_report(session, "TCS")
    assert report is not None
    assert [r.id for r in repo.reports_needing_prose(session)] == [report.id]

    first = {"status": "llm_validated", "summary": "first"}
    assert repo.set_narrative_once(
        session, report.id, narrative=first, status="llm_validated", attempts=2, facts_hash="h" * 64,
    ) is True
    assert repo.set_narrative_once(
        session, report.id, narrative={"summary": "second"}, status="template", attempts=1,
    ) is False

    session.expire_all()
    row = session.get(ResearchReportRow, report.id)
    assert row is not None
    assert row.narrative_json == first
    assert row.narrative_status == "llm_validated" and row.narrative_attempts == 2
    assert repo.reports_needing_prose(session) == []
    assert repo.llm_calls_since(session, datetime.now(timezone.utc) - timedelta(hours=1)) == 2
    assert repo.llm_calls_since(session, datetime.now(timezone.utc) + timedelta(hours=1)) == 0


def test_predictions_have_no_other_update_path():
    """Only write_outcome_once may issue an UPDATE touching research_predictions."""
    tree = ast.parse(inspect.getsource(repo))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            src = ast.get_source_segment(inspect.getsource(repo), node) or ""
            touches = "ResearchPrediction" in src and (".update(" in src or "setattr(" in src)
            if touches and node.name != "write_outcome_once":
                offenders.append(node.name)
    assert offenders == []


# ---------------------------------------------------------------------------
# Runs and holidays
# ---------------------------------------------------------------------------

def test_holiday_dates_after_only_returns_skipped_holidays(session):
    base = date(2026, 10, 1)
    repo.create_run(session, kind="nightly", market_date=date(2026, 9, 30), status="skipped_holiday")  # before
    repo.create_run(session, kind="nightly", market_date=date(2026, 10, 2), status="failed", error="engine_busy")
    repo.create_run(session, kind="nightly", market_date=date(2026, 10, 2), status="failed", error="stale_run")
    repo.create_run(session, kind="nightly", market_date=date(2026, 10, 2), status="skipped_holiday")
    repo.create_run(session, kind="nightly", market_date=date(2026, 10, 5), status="ok")
    running = repo.create_run(session, kind="nightly", market_date=date(2026, 10, 6))

    assert repo.holiday_dates_after(session, base) == {date(2026, 10, 2)}
    assert repo.get_run_by_market_date(session, date(2026, 10, 6)).id == running.id
    assert repo.mark_run_failed(session, running.id, "stale_run") is True
    session.expire_all()
    row = repo.get_run_by_market_date(session, date(2026, 10, 6))
    assert row.status == "failed" and row.error == "stale_run" and row.finished_at is not None
    assert repo.stale_running_runs(session, datetime.now(timezone.utc) + timedelta(hours=1)) == []


# ---------------------------------------------------------------------------
# On-demand quota
# ---------------------------------------------------------------------------

def test_count_on_demand_since(session):
    now = datetime.now(timezone.utc)
    a = repo.insert_on_demand_report(session, _report("ABB", origin="on_demand"), requested_by_user_id=7)
    repo.insert_on_demand_report(session, _report("ACC", origin="on_demand"), requested_by_user_id=7)
    old = repo.insert_on_demand_report(session, _report("AWL", origin="on_demand"), requested_by_user_id=7)
    repo.insert_on_demand_report(session, _report("BEL", origin="on_demand"), requested_by_user_id=8)
    session.query(ResearchReportRow).filter(ResearchReportRow.id == old.id).update(
        {"created_at": now - timedelta(days=2)}, synchronize_session=False,
    )
    session.commit()

    # Same unique key returns the existing row and adds nothing.
    again = repo.insert_on_demand_report(session, {**_report("ABB", origin="on_demand")}, requested_by_user_id=7)
    assert again.id == a.id

    since = now - timedelta(days=1)
    assert repo.count_on_demand_since(session, since, user_id=7) == 2
    assert repo.count_on_demand_since(session, since) == 3
    assert session.query(ResearchPrediction).count() == 0  # on-demand never writes predictions


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def test_prune_reports_retention_keeps_predictions(session):
    today = date(2026, 10, 11)
    run_id = _nightly_run(session)

    def day(n: int) -> str:
        return (today - timedelta(days=n)).isoformat()

    items = [
        {"report": _report("OLDUNI", day(401)), "predictions": [_pred(21), _pred(63)]},  # deleted
        {"report": _report("KEEPUNI", day(399)), "predictions": [_pred(21)]},           # kept
        {"report": _report("OFFOLD", day(31), in_universe=False), "predictions": []},   # deleted
        {"report": _report("OFFNEW", day(29), in_universe=False), "predictions": []},   # kept
    ]
    repo.ingest_run_items(session, run_id, items)
    repo.insert_on_demand_report(session, _report("ODOLD", day(31), origin="on_demand"), requested_by_user_id=1)
    repo.insert_on_demand_report(session, _report("ODNEW", day(29), origin="on_demand"), requested_by_user_id=1)

    assert repo.prune_reports(session, today) == 3
    session.expire_all()
    remaining = {r.symbol for r in session.query(ResearchReportRow).all()}
    assert remaining == {"KEEPUNI", "OFFNEW", "ODNEW"}

    preds = session.query(ResearchPrediction).order_by(ResearchPrediction.symbol, ResearchPrediction.horizon_days).all()
    assert [(p.symbol, p.horizon_days) for p in preds] == [("KEEPUNI", 21), ("OLDUNI", 21), ("OLDUNI", 63)]
    assert all(p.report_id is None for p in preds if p.symbol == "OLDUNI")
    assert all(p.report_id is not None for p in preds if p.symbol == "KEEPUNI")


# ---------------------------------------------------------------------------
# Live metrics inputs
# ---------------------------------------------------------------------------

def test_matured_rows_excludes_fallback_rows(session):
    ok_pid = _ingest_one(session, "TCS")
    fb_pid = _ingest_one(session, "INFY", reason_codes=["gate_failed:G1", "prices_fallback_yfinance"])
    _ingest_one(session, "SBIN")  # stays pending
    outcome = {"outcome_status": "matured", "realized_excess_pp": 0.5, "realized_top_half": True,
               "stale_exit": False, "scorer_version": "os-2"}
    assert repo.write_outcome_once(session, ok_pid, outcome)
    assert repo.write_outcome_once(session, fb_pid, outcome)

    rows = repo.matured_rows(session, "lgbm-rank-v1", 21)
    assert [r["symbol"] for r in rows] == ["TCS"]
    assert rows[0]["as_of"] == AS_OF and rows[0]["outcome_status"] == "matured"
    assert repo.matured_rows(session, "lgbm-rank-v1", 63) == []

    pending = repo.pending_matured_predictions(session, date(2027, 1, 8))
    assert {p.symbol for p in pending} == {"TCS", "INFY", "SBIN"}  # 63d rows of all, 21d of SBIN
    assert len(pending) == 4
    assert repo.pending_matured_predictions(session, date(2026, 11, 8)) == []
    assert repo.pending_matured_predictions(session, date(2027, 1, 8), after_id=max(p.id for p in pending)) == []


def test_insert_and_latest_live_metrics(session):
    resp = {"live_status": "collecting", "live_gate_passed": False, "matured_n": 10, "void_n": 0,
            "stale_exit_n": 0, "matured_dates": 3, "independent_periods": 0, "metrics": {}, "alarms": []}
    assert repo.insert_live_metrics(session, procedure_id="p1", horizon_days=21,
                                    computed_on=date(2026, 10, 4), response=resp)
    assert repo.insert_live_metrics(session, procedure_id="p1", horizon_days=21,
                                    computed_on=date(2026, 10, 11), response={**resp, "matured_n": 20})
    assert not repo.insert_live_metrics(session, procedure_id="p1", horizon_days=21,
                                        computed_on=date(2026, 10, 11), response=resp)
    latest = repo.latest_live_metrics(session)
    assert [(r.horizon_days, r.matured_n, r.computed_on) for r in latest] == [(21, 20, date(2026, 10, 11))]


# ---------------------------------------------------------------------------
# Symbols (FINSEC-04, validator inputs)
# ---------------------------------------------------------------------------

def _user(session, name: str) -> int:
    u = User(username=name, password_hash="x", display_name=name)
    session.add(u)
    session.flush()
    return cast(int, u.id)  # User is a legacy Column-style model


def test_extra_symbols_normalise_and_return_symbols_only(session):
    u1, u2, u3 = _user(session, "u1"), _user(session, "u2"), _user(session, "u3")
    session.add_all([
        Portfolio(user_id=u1, ticker="TCS.NS", company_name="TCS", shares=1, buy_price=100, group_name="holdings"),
        Portfolio(user_id=u2, ticker="RELIANCE.NS", company_name="RIL", shares=0, buy_price=0, group_name="watchlist"),
        Portfolio(user_id=u3, ticker="INFY.BO", company_name="Infosys", shares=2, buy_price=10, group_name="holdings"),
        Portfolio(user_id=u3, ticker="tcs", company_name="TCS", shares=0, buy_price=0, group_name="watchlist"),
        Watchlist(user_id=u2, ticker="TCS.NS"),
        Watchlist(user_id=u1, ticker="bad ticker!"),
    ])
    session.commit()

    symbols = repo.extra_symbols(session)
    assert symbols[0] == "TCS"  # three holders
    assert set(symbols) == {"TCS", "RELIANCE", "INFY"}
    assert all(isinstance(s, str) and not s.isdigit() for s in symbols)
    assert repo.extra_symbols(session, cap=1) == ["TCS"]


def test_known_symbols_and_names_normalise_and_exclude_own(session):
    session.add_all([
        StockUniverse(ticker="TCS.NS", company_name="Tata Consultancy Services"),
        StockUniverse(ticker="TCS.BO", company_name="Tata Consultancy Services Ltd"),
        StockUniverse(ticker="INFY.NS", company_name="Infosys"),
        StockUniverse(ticker="HDFCBANK.BO", company_name="HDFC Bank"),
        StockUniverse(ticker="WIPRO.NS", company_name=None),
    ])
    session.commit()

    symbols, names = repo.known_symbols_and_names(session, exclude_symbol="tcs.ns")
    assert symbols == {"INFY", "HDFCBANK", "WIPRO"}
    assert sorted(names) == ["HDFC Bank", "Infosys"]

    symbols, names = repo.known_symbols_and_names(session, exclude_symbol="INFY")
    assert "TCS" in symbols and "INFY" not in symbols and "Infosys" not in names
