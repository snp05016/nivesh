"""DB-22: Postgres connections carry server-side timeouts, and harvest_news holds
no DB session while it scrapes article bodies or runs FinBERT."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from models.db_models import Base, NewsArticle


def test_pg_connect_args_has_timeouts(monkeypatch):
    monkeypatch.delenv("DB_STATEMENT_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("DB_IDLE_TX_TIMEOUT_MS", raising=False)
    options = database._pg_connect_args()["options"]
    assert "-c statement_timeout=60000" in options
    assert "-c idle_in_transaction_session_timeout=120000" in options

    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "5000")
    monkeypatch.setenv("DB_IDLE_TX_TIMEOUT_MS", "7000")
    options = database._pg_connect_args()["options"]
    assert "-c statement_timeout=5000" in options
    assert "-c idle_in_transaction_session_timeout=7000" in options


class _Entry(dict):
    """feedparser entries support both .get() and attribute access."""
    __getattr__ = dict.get


def test_harvest_news_no_session_during_scrape(monkeypatch):
    import services.news_harvester as nh

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    state = {"open": 0}

    @contextmanager
    def _session():
        s = Session()
        state["open"] += 1
        try:
            yield s
        finally:
            state["open"] -= 1
            s.close()

    def _scrape(url):
        assert state["open"] == 0, "DB session held open across the body scrape"
        return "Nifty stocks rally on FII buying", None

    def _score(headline, summary):
        assert state["open"] == 0, "DB session held open across FinBERT scoring"
        return "Positive", 0.8

    entry = _Entry(
        link="https://example.test/news/1",
        title="Nifty closes higher",
        summary="Markets gained.",
        published_parsed=datetime.now(timezone.utc).timetuple(),
    )
    monkeypatch.setattr(database, "get_session", _session)
    monkeypatch.setattr(nh, "RSS_FEEDS", [{"url": "https://example.test/rss", "source": "Test"}])
    monkeypatch.setattr(nh.requests, "get", lambda *_a, **_k: SimpleNamespace(content=b"", raise_for_status=lambda: None))
    monkeypatch.setattr(nh.feedparser, "parse", lambda _content: SimpleNamespace(entries=[entry]))
    monkeypatch.setattr(nh, "scrape_article_body", _scrape)
    monkeypatch.setattr(nh, "score_article", _score)
    monkeypatch.setattr(nh, "extract_tickers_from_text", lambda _text: ["RELIANCE.NS"])

    try:
        assert asyncio.run(nh.harvest_news()) == 1
        assert asyncio.run(nh.harvest_news()) == 0  # known URL skipped on the next run

        with Session() as s:
            rows = s.query(NewsArticle).all()
            assert len(rows) == 1
            assert (rows[0].ticker, rows[0].sentiment, rows[0].sentiment_score) == ("RELIANCE.NS", "POSITIVE", 0.8)
    finally:
        engine.dispose()
