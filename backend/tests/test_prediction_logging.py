import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.db_models import Base, AnalysisPrediction

@pytest.fixture(scope="module")
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_analysis_prediction_fields(session):
    pred = AnalysisPrediction(
        symbol="TCS",
        recommendation="BULLISH",
        confidence_pct=85,
        llm_confidence=90.0,
        quant_confidence=80.0,
        venn_abers_confidence=85.0,
        signal_agreement=1.0,
        ml_confidence=0.75,
        ml_engine_mode="fallback_technical_heuristic",
        model_version="nivesh-v1.0-heuristic",
        scan_type="extreme",
        regime_id="BULL_HIGH_VOL",
        entry_price=3500.50,
        target_price=3800.00
    )
    session.add(pred)
    session.commit()

    saved_pred = session.query(AnalysisPrediction).filter_by(symbol="TCS").first()
    
    assert saved_pred is not None
    assert saved_pred.symbol == "TCS"
    assert saved_pred.recommendation == "BULLISH"
    assert saved_pred.confidence_pct == 85
    assert saved_pred.scan_type == "extreme"
    assert saved_pred.regime_id == "BULL_HIGH_VOL"
    assert saved_pred.entry_price == 3500.50
    assert saved_pred.ml_engine_mode == "fallback_technical_heuristic"
    assert saved_pred.model_version == "nivesh-v1.0-heuristic"
    
    # Assert missing brier fields are None initially
    assert saved_pred.brier_score_7d is None
    assert saved_pred.brier_score_30d is None
    assert saved_pred.brier_score_90d is None
    assert saved_pred.hit_direction_7d is None
    assert saved_pred.hit_direction_30d is None
    assert saved_pred.hit_direction_90d is None


# ── ML-16: provenance columns, natural key, single write path ─────────────────

import ast
import inspect
import json
import logging
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _patch_get_session(monkeypatch, engine):
    import services.orchestrator as orchestrator

    Session = sessionmaker(bind=engine)

    @contextmanager
    def _fake_get_session():
        s = Session()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(orchestrator, "get_session", _fake_get_session)
    return orchestrator


def _row(**kw):
    base = dict(
        symbol="INFY", recommendation="BULLISH", confidence_pct=70,
        scan_type="standard", model_version="lgbm-v2",
    )
    base.update(kw)
    return AnalysisPrediction(**base)


def test_provenance_columns_persist(engine):
    s = sessionmaker(bind=engine)()
    s.add(_row(
        ml_direction=1, ml_p_up=0.61, input_asof_date=date(2026, 10, 9),
        weights_version="static-v1", ml_fallback_used=False, target_date=date(2026, 11, 6),
    ))
    s.commit()
    got: Any = s.query(AnalysisPrediction).one()
    assert (got.ml_direction, got.ml_p_up, got.weights_version, got.ml_fallback_used) == (1, 0.61, "static-v1", False)
    assert got.input_asof_date == date(2026, 10, 9)
    assert got.target_date == date(2026, 11, 6)
    assert got.horizon_days == 20
    s.close()


def test_natural_key_is_unique_only_with_asof_date(engine):
    s = sessionmaker(bind=engine)()
    s.add_all([_row(), _row()])  # legacy rows without input_asof_date are exempt
    s.commit()

    s.add(_row(input_asof_date=date(2026, 10, 9)))
    s.commit()
    s.add(_row(input_asof_date=date(2026, 10, 9)))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()

    # A different scan type or model version is a different prediction.
    s.add_all([
        _row(input_asof_date=date(2026, 10, 9), scan_type="extreme"),
        _row(input_asof_date=date(2026, 10, 9), model_version="lgbm-v3"),
    ])
    s.commit()
    assert s.query(AnalysisPrediction).count() == 5
    s.close()


def _log(orchestrator, final_state, history_id=None):
    orchestrator._log_prediction(
        {"signal": "BULLISH", "market_regime": "BULL", "current_price_inr": 1500.0,
         "target_prices": {"medium_term_12m": 1800.0}},
        {"ml_engine_mode": "trained_lightgbm_baseline", "model_version": "lgbm-v2",
         "dynamic_weights_active": False},
        final_state, "standard", "infy",
        fused_conf=72, llm_conf=80, quant_conf=0.6, va_conf=0.55, agree=0.7,
        analysis_history_id=history_id,
    )


def test_log_prediction_writes_provenance_and_is_idempotent(engine, monkeypatch):
    from models.db_models import AnalysisHistory

    orchestrator = _patch_get_session(monkeypatch, engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    hist = AnalysisHistory(ticker="INFY", analysis_date="2026-10-10", signal="BULLISH", full_json="{}")
    s.add(hist)
    s.commit()
    hist_id = hist.id
    s.close()

    asof = date(2026, 10, 9)
    final_state = {
        "_ml_input_asof": asof, "_ml_direction": 1, "_ml_p_up": 0.64,
        "_ml_confidence": 0.64, "_ml_fallback_used": False,
    }
    _log(orchestrator, final_state, hist_id)
    _log(orchestrator, final_state, hist_id)  # duplicate: skipped, no exception

    s = Session()
    rows = s.query(AnalysisPrediction).all()
    assert len(rows) == 1
    row: Any = rows[0]
    assert row.symbol == "INFY"
    assert row.analysis_history_id == hist_id
    assert row.ml_direction == 1
    assert row.ml_p_up == 0.64
    assert row.horizon_days == 20
    assert row.input_asof_date == asof
    assert row.target_date == np.busday_offset(asof, 20, roll="forward").item()
    assert row.model_version == "lgbm-v2"
    assert row.weights_version == "static-v1"
    assert row.ml_fallback_used is False
    s.close()


def test_log_prediction_model_version_never_none(engine, monkeypatch):
    orchestrator = _patch_get_session(monkeypatch, engine)
    orchestrator._log_prediction(
        {"signal": "HOLD"},
        {"ml_engine_mode": "fallback_technical_heuristic", "model_version": None},
        None, "standard", "TCS",
        fused_conf=50, llm_conf=None, quant_conf=None, va_conf=None, agree=None,
    )
    row: Any = sessionmaker(bind=engine)().query(AnalysisPrediction).one()
    assert row.model_version == "fallback_technical_heuristic"
    assert row.ml_fallback_used is True
    assert row.input_asof_date is None and row.target_date is None


def test_log_prediction_db_failure_is_a_warning(monkeypatch, caplog):
    import services.orchestrator as orchestrator

    def _broken_get_session():
        raise OperationalError("INSERT", {}, Exception("database is down"))

    monkeypatch.setattr(orchestrator, "get_session", _broken_get_session)
    with caplog.at_level(logging.WARNING):
        _log(orchestrator, {"_ml_input_asof": date(2026, 10, 9)})
    assert any(
        r.levelno == logging.WARNING and "[PREDICTION LOG]" in r.getMessage()
        for r in caplog.records
    )


def test_only_full_path_writes_predictions():
    import services.orchestrator as orchestrator

    src = inspect.getsource(orchestrator)
    # The cache-hit path must not insert rows; the only constructor call is in _log_prediction.
    assert src.count("AnalysisPrediction(") == 1
    assert "AnalysisPrediction(" in inspect.getsource(orchestrator._log_prediction)


def test_save_analysis_returns_history_id_outside_full_json(engine):
    from models.db_models import AnalysisHistory
    from repositories.analysis_repo import save_analysis

    s = sessionmaker(bind=engine)()
    out = save_analysis(s, None, "infy", {"signal": "HOLD", "confidence_pct": 50})
    row: Any = s.query(AnalysisHistory).one()
    assert out["_analysis_history_id"] == row.id
    assert "_analysis_history_id" not in json.loads(row.full_json)
    s.close()


def test_provenance_migration_parses():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "2b3e6056a7c7_prediction_logging_provenance.py"
    tree = ast.parse(path.read_text())
    names = {
        t.id: n.value.value
        for n in tree.body if isinstance(n, ast.AnnAssign) and isinstance(n.value, ast.Constant)
        for t in [n.target] if isinstance(t, ast.Name)
    }
    assert names["revision"] == "2b3e6056a7c7"
    assert names["down_revision"] == "f32cf73ca308"
