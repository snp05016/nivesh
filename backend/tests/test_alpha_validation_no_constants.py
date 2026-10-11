"""
Regression tests for FAKE-12 / ML-08 / GH-652: QuantLab regime breakdown and
strategy sweep must be computed from persisted predictions, never from
hard-coded BULL/BEAR tuples or a placeholder trade_count.
"""

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from models.db_models import Base, AnalysisPrediction
from schemas.alpha_validation import BacktestParams
from services import alpha_validation_service as svc


@pytest.fixture()
def TestSession():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture()
def patched_session(TestSession):
    @contextmanager
    def _test_get_session():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with patch("services.alpha_validation_service.get_session", _test_get_session):
        yield TestSession


def _seed(TestSession, regime_id, count, start_day=0):
    session = TestSession()
    base = datetime(2026, 1, 1)
    for i in range(count):
        session.add(AnalysisPrediction(
            symbol=f"SYM{start_day + i}.NS",
            created_at=base + timedelta(days=start_day + i),
            horizon_days=30,
            recommendation="BULLISH",
            confidence_pct=70,
            regime_id=regime_id,
            actual_return_30d=0.02,
        ))
    session.commit()
    session.close()


def _is_old_constant(r):
    return (r.net_cagr, r.sharpe, r.hit_rate) in {(0.15, 1.2, 0.60), (-0.05, -0.5, 0.45)}


def test_regime_breakdown_empty_table_is_insufficient_data(patched_session):
    result = svc.run_regime_breakdown(BacktestParams())

    assert result.regimes == []
    assert result.conclusion.startswith("Insufficient data")
    assert "BULL regimes" not in result.conclusion
    assert not any(_is_old_constant(r) for r in result.regimes)


def test_regime_breakdown_groups_by_persisted_regime(patched_session):
    _seed(patched_session, "TRENDING_UP", 35)
    _seed(patched_session, "CHOPPY", 5, start_day=100)  # below MIN_REGIME_TRADES

    result = svc.run_regime_breakdown(BacktestParams())

    assert [r.regime_name for r in result.regimes] == ["TRENDING_UP"]
    regime = result.regimes[0]
    assert regime.sample_size == 35
    assert regime.hit_rate == 1.0  # +2% gross stays positive after retail costs
    assert not _is_old_constant(regime)
    assert result.conclusion == "Computed from 35 predictions across 1 regimes."


def test_strategy_sweep_empty_table_has_zero_trades(patched_session):
    result = svc.run_strategy_sweep()

    assert result.all_results
    assert all(it.trade_count == 0 for it in result.all_results)


def test_strategy_sweep_trade_count_reflects_selected_trades(patched_session):
    _seed(patched_session, "TRENDING_UP", 35)
    _seed(patched_session, None, 5, start_day=100)

    result = svc.run_strategy_sweep()

    # One prediction per day, all at 70% confidence: every iteration selects all 40.
    assert all(it.trade_count == 40 for it in result.all_results)
