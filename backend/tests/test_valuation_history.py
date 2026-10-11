"""CMON-05 / MATH-09: the purge script selects only rows the old valuation-history
back-fill wrote (no NIFTY close, created more than a day after their snapshot_date)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    """Fresh in-memory SQLite database per test."""
    from models.db_models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_select_synthetic_rows_predicate(db):
    from models.db_models import PortfolioValuationHistory, User
    from scripts.purge_synthetic_valuation_history import select_synthetic_rows

    user = User(username="purge_vh_user", password_hash="x", display_name="Purge VH")
    db.add(user)
    db.flush()
    burst = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)

    def add_row(snapshot_date, created_at, nifty_close=None):
        row = PortfolioValuationHistory(
            user_id=user.id, snapshot_date=snapshot_date, total_value=1000.0,
            total_invested=900.0, total_pnl=100.0, pnl_percent=11.1,
            nifty_close=nifty_close, created_at=created_at,
        )
        db.add(row)
        return row

    synthetic = add_row("2026-09-02", burst)
    # Each row below must survive.
    add_row("2026-09-29", burst)                                         # burst's newest day
    add_row("2026-09-30", datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc))  # nightly, no NIFTY
    add_row("2026-09-03", burst, nifty_close=24000.0)                    # has a NIFTY close
    db.commit()

    assert [r.id for r in select_synthetic_rows(db)] == [synthetic.id]
