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


# ---------------------------------------------------------------------------
# ML-15: adjusted prices, abstain labels, terminal outcomes, no session held
# across network calls.
# ---------------------------------------------------------------------------

def _run_tracker(session, history_by_symbol, events=None):
    """Run the tracker with yfinance mocked per symbol; optionally log session/fetch order."""
    from contextlib import contextmanager

    @contextmanager
    def tracking_get_session():
        if events is not None:
            events.append("open")
        try:
            yield session
        finally:
            if events is not None:
                events.append("close")

    def fake_ticker(yf_symbol):
        ticker = MagicMock()

        def history(**_kwargs):
            if events is not None:
                events.append(f"fetch:{yf_symbol}")
            return history_by_symbol.get(yf_symbol, pd.DataFrame())

        ticker.history.side_effect = history
        return ticker

    with patch('yfinance.Ticker', side_effect=fake_ticker):
        with patch('services.outcome_tracker.get_session', new=tracking_get_session):
            return update_prediction_outcomes()


def _series(points):
    return pd.DataFrame({'Close': [p for _, p in points]}, index=pd.to_datetime([d for d, _ in points]))


def test_bonus_issue_uses_adjusted_entry_not_raw_price(session):
    asof = (datetime.now(timezone.utc) - timedelta(days=40)).date()
    session.add(AnalysisPrediction(
        symbol="BONUSCO", recommendation="BULLISH", confidence_pct=70,
        entry_price=2000.0,  # raw pre-bonus price logged at analysis time
        input_asof_date=asof, created_at=datetime.combine(asof, datetime.min.time()),
    ))
    session.commit()

    # 1:1 bonus: the adjusted series halves every pre-bonus close.
    hist = _series([(asof, 1000.0), (asof + timedelta(days=7), 1020.0), (asof + timedelta(days=30), 1050.0)])
    _run_tracker(session, {"BONUSCO.NS": hist})

    pred = session.query(AnalysisPrediction).filter_by(symbol="BONUSCO").one()
    assert pred.actual_return_30d == pytest.approx(0.05)
    assert pred.hit_direction_30d is True
    assert pred.outcome_status == "pending"  # 90d not matured yet


def test_hold_call_abstains(session):
    asof = (datetime.now(timezone.utc) - timedelta(days=40)).date()
    session.add(AnalysisPrediction(
        symbol="HOLDCO", recommendation="HOLD", confidence_pct=55,
        input_asof_date=asof, created_at=datetime.combine(asof, datetime.min.time()),
    ))
    session.commit()

    hist = _series([(asof, 100.0), (asof + timedelta(days=7), 108.0), (asof + timedelta(days=30), 110.0)])
    _run_tracker(session, {"HOLDCO.NS": hist})

    pred = session.query(AnalysisPrediction).filter_by(symbol="HOLDCO").one()
    assert pred.actual_return_30d == pytest.approx(0.10)
    assert pred.hit_direction_30d is None
    assert pred.brier_score_30d is None
    assert pred.outcome_status == "abstain"


def test_delisted_symbol_gets_terminal_status(session):
    created = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=130)
    session.add(AnalysisPrediction(
        symbol="GONECO", recommendation="BULLISH", confidence_pct=80, created_at=created,
    ))
    session.commit()

    summary = _run_tracker(session, {})  # every symbol returns empty history

    pred = session.query(AnalysisPrediction).filter_by(symbol="GONECO").one()
    assert pred.outcome_status == "unresolvable"
    assert pred.outcome_attempts == 1
    assert summary["unresolvable"] == 1

    # Terminal rows are not selected again.
    assert _run_tracker(session, {})["eligible_predictions"] == 0


def test_no_session_open_during_price_fetch(session):
    asof = (datetime.now(timezone.utc) - timedelta(days=40)).date()
    session.add(AnalysisPrediction(
        symbol="NETCO", recommendation="BEARISH", confidence_pct=60,
        input_asof_date=asof, created_at=datetime.combine(asof, datetime.min.time()),
    ))
    session.commit()

    events = []
    hist = _series([(asof, 100.0), (asof + timedelta(days=30), 90.0)])
    _run_tracker(session, {"NETCO.NS": hist, "^NSEI": hist}, events=events)

    depth = 0
    fetches = 0
    for e in events:
        if e == "open":
            depth += 1
        elif e == "close":
            depth -= 1
        else:
            fetches += 1
            assert depth == 0, f"{e} ran inside an open session: {events}"
    assert fetches == 2  # benchmark + symbol

    pred = session.query(AnalysisPrediction).filter_by(symbol="NETCO").one()
    assert pred.actual_return_30d == pytest.approx(-0.10)
    assert pred.hit_direction_30d is True
    assert pred.benchmark_return_30d == pytest.approx(-0.10)
