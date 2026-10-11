"""DB-15: analytics SQL must only use functions PostgreSQL has.

Postgres has round(numeric, int) but no round(double precision, int), and no
substr(timestamp, int, int). Both fail at parse time, so compiling the queries
with the postgresql dialect is enough to catch a regression without a server.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query, sessionmaker
from sqlalchemy.pool import StaticPool

import database
from models.db_models import AnalysisPrediction, Base, NewsArticle
from services import prediction_calibration_service, predictions_performance
from services.sentiment_engine import get_sentiment_trend


def _pg_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_hit_rate_compiles_to_numeric_round():
    sql = _pg_sql(select(predictions_performance._safe_hit_rate(AnalysisPrediction.hit_direction_30d)))
    # round()'s first argument must be the NUMERIC cast, never a FLOAT expression.
    assert "round(CAST(" in sql
    assert "AS NUMERIC(12, 6)), %(round_1)s)" in sql
    assert "AS FLOAT), %(round_1)s)" not in sql


def test_calibration_uses_shared_hit_rate():
    assert prediction_calibration_service._safe_hit_rate is predictions_performance._safe_hit_rate


class _CaptureQuery(Query):
    """Unbound Query that records its Postgres SQL instead of executing."""
    compiled: list = []

    def all(self):
        type(self).compiled.append(_pg_sql(self.statement))
        return []


def test_sentiment_trend_no_substr_on_postgres(monkeypatch):
    @contextmanager
    def _fake_session():
        yield SimpleNamespace(query=lambda *cols: _CaptureQuery(cols))

    monkeypatch.setattr(database, "get_session", _fake_session)
    _CaptureQuery.compiled.clear()

    assert get_sentiment_trend("RELIANCE") == []
    sql = _CaptureQuery.compiled[0]
    assert "substr(" not in sql
    assert "date(news_articles.published_at)" in sql


def test_sentiment_trend_buckets_by_day_on_sqlite(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day = (now - timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    with Session() as s:
        for i, (ticker, published, score) in enumerate([
            ("DBXTREND", day, 0.2),
            ("DBXTREND", day + timedelta(hours=6), 0.4),
            ("DBXTREND", now - timedelta(days=40), -0.9),   # outside the window
            ("OTHER", day, -0.9),                            # other ticker
        ]):
            s.add(NewsArticle(
                source="test", ticker=ticker, headline=f"headline {i}",
                article_url=f"https://example.test/{i}", published_at=published,
                sentiment_score=score,
            ))
        s.commit()

    @contextmanager
    def _session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(database, "get_session", _session)
    try:
        trend = get_sentiment_trend("DBXTREND", days=30)
    finally:
        engine.dispose()

    assert trend == [{
        "date": day.date().isoformat(),
        "avg_score": 0.3,
        "article_count": 2,
        "label": "Positive",
    }]
