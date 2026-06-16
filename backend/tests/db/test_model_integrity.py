"""Database model integrity tests — relationships, cascades, constraints, indexes."""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(scope="module")
def engine():
    from models.db_models import Base
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(e, "connect")
    def set_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def session(engine):
    from sqlalchemy.orm import Session
    with Session(engine) as s:
        yield s
        s.rollback()


# ---------------------------------------------------------------------------
# Relationship tests
# ---------------------------------------------------------------------------

def test_user_has_all_cascade_relationships():
    """User model must declare cascade for all 8 child models."""
    from models.db_models import User
    rel_names = {r.key for r in User.__mapper__.relationships}
    required = {
        "portfolio", "analysis_history", "price_targets", "trade_journal",
        "device_tokens", "portfolio_valuation_history", "net_worth_ledger",
        "earnings_alerts", "analysis_jobs",
    }
    missing = required - rel_names
    assert not missing, f"User missing relationships: {missing}"


def test_user_cascade_deletes_portfolio(session):
    from models.db_models import User, Portfolio
    u = User(username="cascade_test", password_hash="x", display_name="T")
    session.add(u)
    session.flush()
    p = Portfolio(user_id=u.id, ticker="TCS", company_name="TCS Ltd",
                  shares=10, buy_price=3000, group_name="holdings")
    session.add(p)
    session.flush()
    session.delete(u)
    session.flush()
    count = session.query(Portfolio).filter_by(user_id=u.id).count()
    assert count == 0, "Portfolio rows must cascade-delete with User"


def test_analysis_job_has_user_backpopulates():
    from models.db_models import AnalysisJob
    rel_names = {r.key for r in AnalysisJob.__mapper__.relationships}
    assert "user" in rel_names, "AnalysisJob must have 'user' relationship"


# ---------------------------------------------------------------------------
# Index tests
# ---------------------------------------------------------------------------

def test_analysis_job_ticker_index_in_table_args():
    from models.db_models import AnalysisJob
    from sqlalchemy import Index
    indexes = {
        arg.name for arg in (AnalysisJob.__table_args__ or ())
        if isinstance(arg, Index)
    }
    assert "ix_analysis_jobs_ticker" in indexes


def test_analysis_history_composite_index_exists():
    from models.db_models import AnalysisHistory
    from sqlalchemy import Index
    indexes = {
        arg.name for arg in (AnalysisHistory.__table_args__ or ())
        if isinstance(arg, Index)
    }
    assert "ix_analysis_history_ticker_user" in indexes


# ---------------------------------------------------------------------------
# Nullable / default tests
# ---------------------------------------------------------------------------

def test_calibrated_confidence_is_not_nullable():
    from models.db_models import AnalysisHistory
    col = AnalysisHistory.__table__.c.calibrated_confidence
    assert not col.nullable, "calibrated_confidence must be NOT NULL"
    assert col.server_default is not None, "calibrated_confidence must have server_default"


def test_trade_journal_has_mood_and_company_name_columns():
    from models.db_models import TradeJournal
    col_names = {c.name for c in TradeJournal.__table__.columns}
    assert "mood" in col_names
    assert "company_name" in col_names
    assert "updated_at" in col_names


def test_analysis_history_has_ml_pipeline_columns():
    from models.db_models import AnalysisHistory
    col_names = {c.name for c in AnalysisHistory.__table__.columns}
    for col in ["market_regime", "calibrated_confidence", "quantitative_drivers",
                "tail_risk_flags", "outcome_delta_pct", "was_correct"]:
        assert col in col_names, f"AnalysisHistory missing column: {col}"
