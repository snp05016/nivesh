"""Error-digest delivery and harvester log rotation (OPS-14)."""
import logging.handlers
from unittest.mock import MagicMock

import httpx

from services import advisor_harvester, error_telemetry

_URL = "https://ntfy.example/nivesh-test-topic"


def test_digest_posts_when_webhook_set(monkeypatch):
    monkeypatch.setenv("OPS_ALERT_WEBHOOK_URL", _URL)
    post = MagicMock()
    monkeypatch.setattr(error_telemetry.httpx, "post", post)

    digest = error_telemetry.generate_daily_digest()

    post.assert_called_once()
    args, kwargs = post.call_args
    assert args[0] == _URL
    assert isinstance(kwargs["content"], bytes)
    assert kwargs["content"] == digest[:4000].encode("utf-8")
    assert kwargs["timeout"] == 10


def test_digest_no_post_when_unset(monkeypatch):
    monkeypatch.delenv("OPS_ALERT_WEBHOOK_URL", raising=False)
    post = MagicMock()
    monkeypatch.setattr(error_telemetry.httpx, "post", post)

    assert "NIVESH NIGHTLY DIGEST" in error_telemetry.generate_daily_digest()
    post.assert_not_called()


def test_digest_survives_webhook_failure(monkeypatch):
    monkeypatch.setenv("OPS_ALERT_WEBHOOK_URL", _URL)
    monkeypatch.setattr(error_telemetry.httpx, "post", MagicMock(side_effect=httpx.ConnectError("down")))

    assert "NIVESH NIGHTLY DIGEST" in error_telemetry.generate_daily_digest()


def test_advisor_log_handler_rotating(monkeypatch, tmp_path):
    monkeypatch.setattr(advisor_harvester, "_LOGS_DIR", tmp_path)
    monkeypatch.setattr(advisor_harvester.logger, "handlers", [])

    advisor_harvester._ensure_file_handler()
    advisor_harvester._ensure_file_handler()

    handlers = advisor_harvester.logger.handlers
    try:
        assert len(handlers) == 1
        handler = handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.baseFilename == str(tmp_path / "advisor_harvester.log")
        assert handler.maxBytes > 0 and handler.backupCount > 0
    finally:
        for h in handlers:
            h.close()


def test_production_json_logs_keep_tracebacks(monkeypatch):
    import io

    import pytest

    structlog = pytest.importorskip("structlog")
    from core.logging_config import configure_logging

    monkeypatch.setenv("ENVIRONMENT", "production")
    root = logging.getLogger()
    before, level = list(root.handlers), root.level
    try:
        configure_logging()
        (handler,) = [h for h in root.handlers if h not in before]
        handler.stream = io.StringIO()  # type: ignore[attr-defined]
        try:
            1 / 0
        except ZeroDivisionError:
            logging.getLogger("ops-test").exception("boom")
        out = handler.stream.getvalue()  # type: ignore[attr-defined]
        assert "Traceback" in out and "ZeroDivisionError" in out
        assert "traceback object" not in out
    finally:
        for h in root.handlers[:]:
            if h not in before:
                root.removeHandler(h)
        root.setLevel(level)
        structlog.reset_defaults()
