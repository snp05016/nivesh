"""SILENT-20: ml-engine failures must leave a (throttled) WARNING, not vanish as None."""
import asyncio
import logging
from unittest.mock import MagicMock, patch

import httpx

from services.qlib_engine import ml_client

_LOGGER = "services.qlib_engine.ml_client"
_ROWS = [{"open": 100, "high": 105, "low": 98, "close": 102, "volume": 1000}]


def _warnings(caplog):
    return [r for r in caplog.records if r.name == _LOGGER and r.levelno == logging.WARNING]


def test_non_200_returns_none_and_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(ml_client, "_last_warned", {})
    response = MagicMock(status_code=500, text="Internal Server Error")
    caplog.set_level(logging.WARNING, logger=_LOGGER)

    with patch("httpx.AsyncClient.post", return_value=response):
        assert asyncio.run(ml_client.predict_cross_section("X", _ROWS)) is None

    records = _warnings(caplog)
    assert len(records) == 1
    assert "500" in records[0].getMessage()


def test_connect_error_logs_once_per_interval(monkeypatch, caplog):
    monkeypatch.setattr(ml_client, "_last_warned", {})
    caplog.set_level(logging.WARNING, logger=_LOGGER)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        for _ in range(3):
            assert asyncio.run(ml_client.predict_cross_section("X", _ROWS)) is None

    records = _warnings(caplog)
    assert len(records) == 1  # throttled: one line per reason per interval
    assert "ConnectError" in records[0].getMessage()
