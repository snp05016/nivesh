"""SILENT-18: harvester health reflects real outcomes.

Startup seeding never flips a recorded failure to healthy, SEBI/AMFI emit no boilerplate
card when their fetch fails, every expert source records an outcome, and a dead RSS feed
is logged instead of silently yielding zero articles."""
import asyncio
import logging
import types
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services import harvester_db, harvester_expert
from services.harvester_db import Base, SourceHealth


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        yield session
        session.commit()

    monkeypatch.setattr(harvester_db, "get_session", _get_session)
    yield session
    session.close()
    engine.dispose()


def _row(session, name):
    return session.query(SourceHealth).filter_by(source_name=name).one()


def test_seed_does_not_flip_unhealthy(db_session):
    from services.harvest_worker import _seed_harvester_sources

    db_session.add(SourceHealth(source_name="CRISIL Ratings", is_healthy=False,
                                error_message="x", items_scraped=0))
    db_session.commit()

    _seed_harvester_sources()

    crisil = _row(db_session, "CRISIL Ratings")
    assert crisil.is_healthy is False
    assert crisil.error_message == "x"
    # A source with no row yet is seeded as never run, not healthy.
    sebi = _row(db_session, "SEBI RIA Registry")
    assert sebi.is_healthy is False
    assert sebi.error_message == "never run"
    assert sebi.last_success is None


def test_sebi_and_amfi_no_card_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(harvester_expert, "_fetch", lambda url: None)
    assert harvester_expert._scrape_sebi_ria_registry() == []
    assert harvester_expert._scrape_amfi_nav_data() == []


def test_expert_sources_record_failure(db_session, monkeypatch):
    monkeypatch.setattr(harvester_expert, "_scrape_all_rating_agencies", lambda: [])
    monkeypatch.setattr(harvester_expert, "_scrape_sebi_ria_registry", lambda: [])

    def _amfi_raises():
        raise RuntimeError("amfi exploded")

    monkeypatch.setattr(harvester_expert, "_scrape_amfi_nav_data", _amfi_raises)
    # Telemetry is a side channel; keep it off the test DB.
    import services.error_telemetry as telemetry
    monkeypatch.setattr(telemetry, "log_diagnostic_error", lambda **kw: None)

    assert harvester_expert.scrape_all_expert_sources() == []

    for name in harvester_expert._EXPECTED_SOURCES:
        row = _row(db_session, name)
        assert row.is_healthy is False, name
        assert row.error_message
    assert _row(db_session, "AMFI Mutual Fund Data").error_message == "amfi exploded"


def test_expert_source_success_recorded(db_session, monkeypatch):
    card = {"source_name": "SEBI RIA Registry", "credibility_score": 9}
    monkeypatch.setattr(harvester_expert, "_scrape_all_rating_agencies", lambda: [])
    monkeypatch.setattr(harvester_expert, "_scrape_sebi_ria_registry", lambda: [card])
    monkeypatch.setattr(harvester_expert, "_scrape_amfi_nav_data", lambda: [])

    harvester_expert.scrape_all_expert_sources()

    sebi = _row(db_session, "SEBI RIA Registry")
    assert sebi.is_healthy is True
    assert sebi.items_scraped == 1
    assert _row(db_session, "AMFI Mutual Fund Data").is_healthy is False


def test_rss_bozo_feed_is_logged_and_skipped(monkeypatch, caplog):
    from services import news_harvester

    monkeypatch.setattr(news_harvester, "RSS_FEEDS",
                        [{"source": "deadfeed", "url": "https://feeds.invalid/rss", "category": "market"}])
    resp = types.SimpleNamespace(content=b"<html>not a feed</html>", raise_for_status=lambda: None)
    monkeypatch.setattr(news_harvester.requests, "get", lambda *a, **k: resp)
    monkeypatch.setattr(news_harvester.feedparser, "parse", lambda content: types.SimpleNamespace(
        bozo=1, bozo_exception=ValueError("not well-formed"), entries=[]))

    with caplog.at_level(logging.WARNING, logger=news_harvester.logger.name):
        added = asyncio.run(news_harvester.harvest_news())

    assert added == 0
    assert any("deadfeed" in r.getMessage() and "bozo=1" in r.getMessage() for r in caplog.records)
