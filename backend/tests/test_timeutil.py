"""DB-24: date keys, staleness ages and feed timestamps do not depend on the server timezone."""
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from core.timeutil import ist_today, to_utc_naive, utcnow
from services.harvester_db import _parse_dt
from services.staleness import compute_staleness


@pytest.fixture
def server_tz(monkeypatch):
    def _set(name: str) -> None:
        monkeypatch.setenv("TZ", name)
        time.tzset()

    yield _set
    monkeypatch.undo()
    time.tzset()


def _results() -> tuple:
    fresh = compute_staleness(utcnow().replace(tzinfo=None) - timedelta(hours=23), 0.0)
    return (
        ist_today(datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc)),
        ist_today(datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc)),
        _parse_dt("2026-10-10T10:00:00+05:30"),
        _parse_dt("Sat, 10 Oct 2026 10:00:00 +0530"),
        _parse_dt("2026-10-10T04:30:00Z"),
        _parse_dt("2026-10-10 10:00:00"),
        fresh["reason"],
        fresh["score"],
    )


@pytest.mark.parametrize("tz", ["UTC", "Asia/Kolkata", "Asia/Dubai"])
def test_results_independent_of_server_tz(server_tz, tz):
    server_tz(tz)
    (ist_after_midnight, ist_before_midnight, iso_offset, rfc_offset, iso_z,
     naive, fresh_reason, fresh_score) = _results()

    # 19:00 UTC is 00:30 IST next day; 18:00 UTC is 23:30 IST same day.
    assert ist_after_midnight == date(2026, 10, 11)
    assert ist_before_midnight == date(2026, 10, 10)
    # Offsets are converted to UTC, not stripped.
    assert iso_offset == datetime(2026, 10, 10, 4, 30)
    assert rfc_offset == datetime(2026, 10, 10, 4, 30)
    assert iso_z == datetime(2026, 10, 10, 4, 30)
    assert naive == datetime(2026, 10, 10, 10, 0) and naive.tzinfo is None
    # A 23 h old analysis is not aged (no UAE +4 h shift on "now").
    assert "old" not in fresh_reason
    assert fresh_score == 0


def test_same_results_under_utc_and_ist(server_tz):
    server_tz("UTC")
    utc = _results()
    server_tz("Asia/Kolkata")
    assert _results() == utc


def test_staleness_age_days_uses_utc():
    # 3 days minus 1 h: without the old +4 h shift this is 2 days, i.e. not yet aged.
    res = compute_staleness(utcnow().replace(tzinfo=None) - timedelta(days=3) + timedelta(hours=1), 0.0)
    assert res["score"] == 0


def test_to_utc_naive():
    ist = timezone(timedelta(hours=5, minutes=30))
    assert to_utc_naive(datetime(2026, 1, 1, 5, 30, tzinfo=ist)) == datetime(2026, 1, 1, 0, 0)
    assert to_utc_naive(datetime(2026, 1, 1, 5, 30)) == datetime(2026, 1, 1, 5, 30)
