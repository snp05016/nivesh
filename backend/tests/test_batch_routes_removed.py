"""LLM-03: the data-free /analyze/batch routes are gone, POST /batch caps its ticker list,
and the purge script selects only rows the batch route wrote."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app


def test_batch_routes_not_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/analyze/batch" not in paths
    assert "/analyze/batch/{batch_id}" not in paths


def test_batch_routes_unreachable(client):
    # 405 rather than 404 because main.py's global OPTIONS route matches every path.
    assert client.post("/analyze/batch", json={"tickers": ["RELIANCE"]}).status_code in (404, 405)
    assert client.get("/analyze/batch/abc").status_code in (404, 405)


def test_batch_history_caps_tickers(client, auth_headers):
    too_many = {"tickers": [f"T{i}" for i in range(21)]}
    assert client.post("/batch", json=too_many, headers=auth_headers).status_code == 422
    assert client.post("/batch", json={"tickers": []}, headers=auth_headers).status_code == 422
    at_cap = {"tickers": [f"T{i}" for i in range(20)]}
    assert client.post("/batch", json=at_cap, headers=auth_headers).status_code != 422


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


def test_select_batch_rows_predicate(db):
    from models.db_models import AnalysisHistory, User
    from scripts.purge_batch_analysis_rows import select_batch_rows

    user = User(username="purge_test_user", password_hash="x", display_name="Purge Test")
    db.add(user)
    db.flush()

    def add_row(full_json, user_id=None, raw_output=None, scan_type="standard"):
        row = AnalysisHistory(user_id=user_id, ticker="RELIANCE", analysis_date="2026-10-01",
                              signal="BULLISH", raw_output=raw_output,
                              full_json=json.dumps(full_json), scan_type=scan_type)
        db.add(row)
        return row

    batch_row = add_row({"signal": "BULLISH", "current_price_inr": 2950.0})
    # Every row below must survive, each because of a different clause.
    add_row({"signal": "BULLISH", "_cache_type": "FULL AI", "confidence_breakdown": {}},
            raw_output="agent transcript")                                  # orchestrator, anonymous
    add_row({"signal": "BULLISH", "_cache_type": "SMART CACHE"})            # pre-fusion smart-cache copy
    add_row({"signal": "BULLISH", "confidence_breakdown": {"llm": 70}})     # fused confidence
    add_row({"signal": "BULLISH"}, user_id=user.id)                         # user-owned
    add_row({"signal": "BULLISH"}, scan_type="deep")                        # not the standard tier
    db.commit()

    assert [row.id for row in select_batch_rows(db)] == [batch_row.id]
