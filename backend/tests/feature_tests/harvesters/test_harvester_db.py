import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.harvester_db import (
    init_harvester_db,
    get_session,
    upsert_card,
    record_source_health,
    HarvestedCard,
    SourceHealth,
    _DB_PATH,
    DATABASE_URL,
    Base
)

@pytest.fixture(scope="function")
def engine():
    return create_engine("sqlite:///:memory:")

@pytest.fixture(scope="function")
def tables(engine):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(engine, tables):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_harvester_db_isolation():
    # Assert that the harvester DB path is exactly 'harvester.db' and is separated
    assert _DB_PATH.name == "harvester.db"
    assert "harvester.db" in DATABASE_URL
    assert "stockapp.db" not in DATABASE_URL

def test_init_harvester_db():
    with patch("services.harvester_db.Base.metadata.create_all") as mock_create:
        init_harvester_db()
        mock_create.assert_called_once()

def test_upsert_card_new_valid(db_session):
    card = {
        "external_id": "test_ext_1",
        "source_type": "EXPERT",
        "source_name": "Test Source",
        "source_url": "http://example.com",
        "credibility_score": 8,
        "title": "Test Title",
        "raw_text": "Test text"
    }
    
    result = upsert_card(db_session, card)
    db_session.commit()
    
    assert result is True
    
    row = db_session.query(HarvestedCard).filter_by(external_id="test_ext_1").first()
    assert row is not None
    assert row.title == "Test Title"
    assert row.credibility_score == 8

def test_upsert_card_low_credibility(db_session):
    card = {
        "external_id": "test_ext_low",
        "source_type": "EXPERT",
        "source_name": "Test Source",
        "source_url": "http://example.com",
        "credibility_score": 3,
        "title": "Test Title",
        "raw_text": "Test text"
    }
    
    result = upsert_card(db_session, card)
    assert result is False

def test_upsert_card_duplicate(db_session):
    card = {
        "external_id": "test_ext_dup",
        "source_type": "EXPERT",
        "source_url": "http://example.com",
        "credibility_score": 8,
    }
    
    # Insert first time
    upsert_card(db_session, card)
    db_session.commit()
    
    # Insert second time
    result = upsert_card(db_session, card)
    assert result is False

def test_record_source_health_success(db_session):
    record_source_health(db_session, "Test Source", success=True, items=5)
    db_session.commit()
    
    row = db_session.query(SourceHealth).filter_by(source_name="Test Source").first()
    assert row is not None
    assert row.is_healthy is True
    assert row.items_scraped == 5
    assert row.last_success is not None
    assert row.error_message is None

def test_record_source_health_failure(db_session):
    record_source_health(db_session, "Test Source Fail", success=False, error="Test Error")
    db_session.commit()
    
    row = db_session.query(SourceHealth).filter_by(source_name="Test Source Fail").first()
    assert row is not None
    assert row.is_healthy is False
    assert row.error_message == "Test Error"
    assert row.last_failure is not None


def test_harvester_engine_pragmas(tmp_path):
    """DB-31: harvester.db gets WAL + busy_timeout like the main SQLite engine."""
    from sqlalchemy import event
    import services.harvester_db as harvester_db

    assert event.contains(harvester_db.ENGINE, "connect", harvester_db._sqlite_pragmas)

    # Exercise the listener on a throwaway file DB (WAL needs a file, not :memory:).
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}")
    event.listen(eng, "connect", harvester_db._sqlite_pragmas)
    try:
        with eng.connect() as c:
            assert c.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"
            assert c.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
            assert c.exec_driver_sql("PRAGMA synchronous").scalar() == 1  # NORMAL
    finally:
        eng.dispose()
