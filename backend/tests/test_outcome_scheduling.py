"""DB-03 / ML-03: outcome labels are actually produced and the jobs that produce
them are scheduled, observable and have no dead duplicates."""
import ast
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import AnalysisHistory, Base

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture()
def Session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _report(signal="BUY", price=100.0) -> str:
    # Shape of a stored, normalised analysis result: the price key is current_price_inr,
    # stamped as a live quote (LLM-04) so report_entry_price accepts it (LLM-14).
    return json.dumps({"ticker": "OUTC", "signal": signal, "confidence_pct": 70,
                       "current_price_inr": price, "current_price_source": "live_quote",
                       "target_prices": {"short_term_3m": 120.0}})


def _row(session, ticker="OUTC", signal="BUY", age_days=40):
    row = AnalysisHistory(ticker=ticker, analysis_date="2026-01-01", signal=signal,
                          full_json=_report(signal),
                          created_at=datetime.now(timezone.utc) - timedelta(days=age_days))
    session.add(row)
    session.commit()
    return row.id


def _history(anchor_close=100.0, exit_close=110.0, age_days=40):
    """Daily closes: anchor_close up to the analysis date, exit_close from 30 days after it."""
    anchor = pd.Timestamp((datetime.now(timezone.utc) - timedelta(days=age_days)).date())
    idx = pd.date_range(anchor - pd.Timedelta(days=5), anchor + pd.Timedelta(days=40), freq="D")
    closes = [anchor_close if d < anchor + pd.Timedelta(days=30) else exit_close for d in idx]
    return pd.DataFrame({"Close": closes}, index=idx)


def _evaluate(session, monkeypatch, hist):
    import services.outcome_labels as labels
    from services.advisor_harvester import evaluate_analysis_outcomes

    monkeypatch.setattr(labels, "fetch_adjusted_history", lambda *a, **k: hist)
    with session() as db:
        n = evaluate_analysis_outcomes(db)
    return n


def _get(Session, row_id):
    with Session() as db:
        return db.get(AnalysisHistory, row_id)


# ── DB-03: AnalysisHistory evaluator ──────────────────────────────────────────

def test_stored_report_gets_labelled(Session, monkeypatch):
    row_id = _row(Session())

    assert _evaluate(Session, monkeypatch, _history(100.0, 110.0)) == 1

    row = _get(Session, row_id)
    assert row.outcome_delta_pct == pytest.approx(10.0)
    assert row.was_correct is True
    assert row.outcome_checked_at is not None


def test_hold_is_checked_but_abstains(Session, monkeypatch):
    row_id = _row(Session(), signal="HOLD")

    _evaluate(Session, monkeypatch, _history(100.0, 90.0))

    row = _get(Session, row_id)
    assert row.was_correct is None
    assert row.outcome_delta_pct == pytest.approx(-10.0)
    assert row.outcome_checked_at is not None


def test_no_data_recent_row_left_for_retry(Session, monkeypatch):
    row_id = _row(Session())

    assert _evaluate(Session, monkeypatch, None) == 0

    assert _get(Session, row_id).outcome_checked_at is None


def test_row_without_ticker_is_not_reselected(Session, monkeypatch):
    row_id = _row(Session(), ticker="")

    _evaluate(Session, monkeypatch, None)

    assert _get(Session, row_id).outcome_checked_at is not None


def test_feedback_block_reads_current_price_inr(Session, monkeypatch):
    """Real DB path: created_at loads naive, the stored price key is current_price_inr."""
    from services.feedback_injector import get_feedback_block

    monkeypatch.setattr("yfinance.download", lambda *a, **k: pd.DataFrame({"Close": [110.0]}))
    _row(Session(), ticker="FDBK")
    with Session() as db:
        block = get_feedback_block("FDBK", db_session=db)

    assert "last analyzed 40 days ago" in block
    assert "Previous price:      ₹100.0" in block
    assert "Stock moved UP 10.0% (₹100 → ₹110)" in block


# ── ML-03: AnalysisPrediction tracker scheduling ──────────────────────────────

def _add_job_first_args(tree):
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_job" and node.args):
            first = node.args[0]
            yield first.id if isinstance(first, ast.Name) else None


def test_prediction_outcomes_registered_once():
    tree = ast.parse((BACKEND / "services" / "harvest_worker.py").read_text(encoding="utf-8"))
    names = list(_add_job_first_args(tree))
    assert names.count("_run_prediction_outcomes") == 1
    assert names.count("_run_evaluate_analysis_outcomes") == 1
    assert names.count("sync_corporate_actions_all_users") == 1


def test_outcome_updater_reachable_and_no_dead_variants():
    callers, dead = [], []
    paths = list(BACKEND.glob("*.py"))
    for d in ("services", "routers", "core", "repositories", "scripts"):
        paths += (BACKEND / d).rglob("*.py")
    for path in paths:
        rel = path.relative_to(BACKEND).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "update_prediction_outcomes(" in text and rel != "services/outcome_tracker.py":
            callers.append(rel)
        for name in ("def check_signal_outcomes", "def run_outcome_tracking_task", "def backfill_outcomes"):
            if name in text:
                dead.append((rel, name))
    assert "services/harvest_worker.py" in callers
    assert dead == []


@pytest.fixture()
def fake_cache(monkeypatch):
    from services import disk_cache

    store = {}
    monkeypatch.setattr(disk_cache, "get", lambda ns, key: store.get((ns, key)))
    monkeypatch.setattr(disk_cache, "set", lambda ns, key, value, ttl=None: store.__setitem__((ns, key), value))
    return store


def test_heartbeat_ok_then_error_keeps_last_success(fake_cache, monkeypatch):
    import services.harvest_worker as hw
    import services.outcome_tracker as ot

    monkeypatch.setattr(ot, "update_prediction_outcomes",
                        lambda: {"eligible_predictions": 2, "processed_symbols": 1, "missing_price_data": 0,
                                 "updates_7d": 2, "updates_30d": 0, "updates_90d": 0})
    ok = hw._run_prediction_outcomes()
    assert ok["status"] == "ok" and ok["last_success_at"] == ok["last_run_at"]

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(ot, "update_prediction_outcomes", _boom)
    with pytest.raises(RuntimeError):  # re-raised so job_runs records the failure
        hw._run_prediction_outcomes()
    err = fake_cache[("job_heartbeat", "prediction_outcomes")]
    assert err["status"] == "error"
    assert err["summary"] == {"error": "RuntimeError"}
    assert err["last_success_at"] == ok["last_success_at"]
    assert fake_cache[("job_heartbeat", "prediction_outcomes")] == err


def test_no_price_data_runs_counted(fake_cache, monkeypatch):
    import services.harvest_worker as hw
    import services.outcome_tracker as ot

    monkeypatch.setattr(ot, "update_prediction_outcomes",
                        lambda: {"eligible_predictions": 5, "processed_symbols": 2, "missing_price_data": 2})
    for _ in range(3):
        beat = hw._run_prediction_outcomes()
    assert beat["no_data_runs"] == 3


def test_calibration_health_reports_last_outcome_run(fake_cache, Session, monkeypatch):
    import services.prediction_calibration_service as pcs

    @contextmanager
    def _get_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(pcs, "get_session", _get_session)

    health = pcs.get_calibration_health()
    assert health["last_outcome_run"] is None
    assert any("has not completed" in w for w in health["warnings"])

    stale = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    fake_cache[("job_heartbeat", "prediction_outcomes")] = {"status": "ok", "last_success_at": stale}
    health = pcs.get_calibration_health()
    assert health["last_outcome_run"]["last_success_at"] == stale
    assert any("over 36h ago" in w for w in health["warnings"])

    from schemas.prediction_calibration import CalibrationHealthResponse
    assert CalibrationHealthResponse(**health).last_outcome_run is not None
