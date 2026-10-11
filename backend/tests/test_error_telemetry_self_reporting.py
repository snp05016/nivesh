"""SILENT-17: error telemetry reports its own failures instead of swallowing them."""
import logging
import pathlib
from contextlib import contextmanager

import database
from models.db_models import Base, IdeasErrorLog, NotificationErrorLog
from services import error_telemetry

_TABLES = ("market_error_logs", "earnings_error_logs", "notification_error_logs", "ideas_error_logs")


@contextmanager
def _broken_session():
    raise RuntimeError("simulated DB outage")
    yield  # pragma: no cover


def _telemetry_warnings(caplog):
    return [r for r in caplog.records if r.name == "nivesh.telemetry" and r.levelno == logging.WARNING]


def test_digest_query_failure_not_clean(monkeypatch):
    monkeypatch.delenv("OPS_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(database, "get_session", _broken_session)

    digest = error_telemetry.generate_daily_digest()

    assert "clean run" not in digest
    assert "UNKNOWN - query failed" in digest
    assert "Could not query error logs" in digest


def test_digest_counts_notification_and_ideas_rows(monkeypatch):
    monkeypatch.delenv("OPS_ALERT_WEBHOOK_URL", raising=False)
    Base.metadata.create_all(database.ENGINE, tables=[Base.metadata.tables[t] for t in _TABLES])
    with database.get_session() as session:
        session.add(NotificationErrorLog(failure_point="apns_dispatch", error_trace="silent17 notif", target_device="silent17-device"))
        session.add(IdeasErrorLog(module="ideas_extractor", error_trace="silent17 ideas", context_ticker="SILENT17"))
        session.commit()
    try:
        digest = error_telemetry.generate_daily_digest()
    finally:
        with database.get_session() as session:
            session.query(NotificationErrorLog).filter_by(target_device="silent17-device").delete()
            session.query(IdeasErrorLog).filter_by(context_ticker="SILENT17").delete()
            session.commit()

    assert "Could not query" not in digest
    assert "clean run" not in digest
    assert "notification [silent17-device]: silent17 notif" in digest
    assert "ideas [SILENT17]: silent17 ideas" in digest


def test_digest_keeps_file_write_warning(monkeypatch):
    monkeypatch.delenv("OPS_ALERT_WEBHOOK_URL", raising=False)

    def _fail_write(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pathlib.Path, "write_text", _fail_write)

    assert "[WARN] Could not write digest file: disk full" in error_telemetry.generate_daily_digest()


def test_log_diagnostic_error_reports_db_failure(monkeypatch, caplog):
    monkeypatch.setattr(database, "get_session", _broken_session)

    with caplog.at_level(logging.WARNING, logger="nivesh.telemetry"):
        error_uuid = error_telemetry.log_diagnostic_error(
            "EARNINGS_CALENDAR", "PARSE_FAILURE", context={"target_ticker": "TCS"}
        )

    assert error_uuid
    messages = " ".join(r.getMessage() for r in _telemetry_warnings(caplog))
    assert "market_error_logs" in messages
    assert "earnings_error_logs" in messages
