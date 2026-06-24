import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd
from models.db_models import Base, AnalysisPrediction
from services.outcome_tracker import update_prediction_outcomes

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_outcome_tracker_math(session):
    # Create an old prediction (100 days old)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    pred_date = now - timedelta(days=100)
    
    pred = AnalysisPrediction(
        symbol="RELIANCE",
        recommendation="BULLISH",
        confidence_pct=80,
        entry_price=2000.0,
        created_at=pred_date
    )
    session.add(pred)
    session.commit()

    # Create mock history for 2 years
    # It just needs to have valid entries at pred_date + 7, 30, 90 days.
    dates = [
        pred_date,
        pred_date + timedelta(days=7),
        pred_date + timedelta(days=30),
        pred_date + timedelta(days=90)
    ]
    # Price goes up, then down, then up
    prices = [2000.0, 2200.0, 1800.0, 2400.0] 
    
    mock_df = pd.DataFrame({'Close': prices}, index=pd.to_datetime(dates))
    mock_df.index = mock_df.index.tz_localize("UTC") # Yfinance returns UTC by default

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_df

    from contextlib import contextmanager
    @contextmanager
    def mock_get_session():
        yield session
        
    with patch('yfinance.Ticker', return_value=mock_ticker):
        with patch('services.outcome_tracker.get_session', new=mock_get_session):
            update_prediction_outcomes()

    # Re-query the object because the session might have expired it after commit
    pred = session.query(AnalysisPrediction).filter_by(symbol="RELIANCE").first()

    # 7-day outcome (Price went from 2000 to 2200 -> +10%)
    assert pred.actual_return_7d == pytest.approx(0.1)
    assert pred.hit_direction_7d is True  # Bullish prediction
    # conf is 0.8, outcome is 1.0 -> brier_score_7d = (0.8 - 1.0)^2 = 0.04
    assert pred.brier_score_7d == pytest.approx(0.04)

    # 30-day outcome (Price went from 2000 to 1800 -> -10%)
    assert pred.actual_return_30d == pytest.approx(-0.1)
    assert pred.hit_direction_30d is False # Bullish prediction, but price fell
    # conf is 0.8, outcome is 0.0 -> brier_score_30d = (0.8 - 0.0)^2 = 0.64
    assert pred.brier_score_30d == pytest.approx(0.64)

    # 90-day outcome (Price went from 2000 to 2400 -> +20%)
    assert pred.actual_return_90d == pytest.approx(0.2)
    assert pred.hit_direction_90d is True
    # conf is 0.8, outcome is 1.0 -> brier_score_90d = 0.04
    assert pred.brier_score_90d == pytest.approx(0.04)
