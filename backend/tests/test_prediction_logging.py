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
