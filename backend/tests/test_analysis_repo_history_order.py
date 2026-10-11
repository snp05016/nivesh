"""DB-16: get_all_ticker_history must return the NEWEST `limit` analyses,
oldest first, so the orchestrator's prior[-1] is the latest analysis."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models.db_models import AnalysisHistory, Base, User
from repositories.analysis_repo import get_all_ticker_history


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_get_all_ticker_history_returns_newest_window(db_session):
    user = User(username="history_user", password_hash="hash", display_name="History User")
    db_session.add(user)
    db_session.commit()

    start = datetime(2025, 1, 1, 10, 0, 0)
    for i in range(60):
        created = start + timedelta(days=i)
        db_session.add(AnalysisHistory(
            user_id=user.id, ticker="RELIANCE", analysis_date=created.date().isoformat(),
            signal="HOLD", full_json=json.dumps({"n": i}), created_at=created,
        ))
    db_session.commit()

    res = get_all_ticker_history(db_session, "RELIANCE", int(user.id))  # type: ignore[arg-type]

    assert len(res) == 50
    assert res[0]["n"] == 10
    assert res[-1]["n"] == 59
    assert [r["n"] for r in res] == list(range(10, 60))
