"""GH-610: telemetry log_* helpers live in database.py, never raise, and warn on failure."""
import logging
from contextlib import contextmanager

import database
import models.db_models as db_models
from models.db_models import Base, MarketErrorLog


@contextmanager
def _broken_session():
    raise RuntimeError("simulated DB outage")
    yield  # pragma: no cover


def test_log_helpers_never_raise_and_warn(monkeypatch, caplog):
    monkeypatch.setattr(database, "get_session", _broken_session)
    with caplog.at_level(logging.WARNING, logger="nivesh.telemetry"):
        database.log_market_error("c", "boom")
        database.log_earnings_error("m", "boom")
        database.log_notification_error("p", "boom")
        database.log_ideas_error("m", "boom")
    warnings = [r for r in caplog.records if r.name == "nivesh.telemetry" and r.levelno == logging.WARNING]
    assert len(warnings) == 4
    messages = " ".join(r.getMessage() for r in warnings)
    for table in ("market_error_logs", "earnings_error_logs", "notification_error_logs", "ideas_error_logs"):
        assert table in messages


def test_log_market_error_truncates():
    Base.metadata.create_all(database.ENGINE, tables=[Base.metadata.tables["market_error_logs"]])
    database.log_market_error("gh610_truncation", "X" * 5000, context_ticker="RELIANCE")
    with database.get_session() as session:
        rows = session.query(MarketErrorLog.error_message, MarketErrorLog.context_ticker).filter_by(
            component="gh610_truncation"
        ).all()
        session.query(MarketErrorLog).filter_by(component="gh610_truncation").delete()
        session.commit()
    assert len(rows) == 1
    message, ticker = rows[0]
    assert len(message) == 2000
    assert ticker == "RELIANCE"


def test_helpers_not_in_db_models():
    for name in ("log_market_error", "log_earnings_error", "log_notification_error", "log_ideas_error"):
        assert not hasattr(db_models, name)
