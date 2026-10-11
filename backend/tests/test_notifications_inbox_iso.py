"""IOSCORE-21: inbox timestamps carry an explicit UTC offset so iOS can parse them."""
from datetime import datetime, timedelta, timezone

from services.notifications_inbox import _iso_utc


def test_naive_value_is_treated_as_utc():
    assert _iso_utc(datetime(2026, 10, 8, 12, 34, 56, 789012)) == "2026-10-08T12:34:56.789+00:00"


def test_aware_value_is_converted_to_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    assert _iso_utc(datetime(2026, 10, 8, 18, 4, 56, tzinfo=ist)) == "2026-10-08T12:34:56.000+00:00"


def test_none_passes_through():
    assert _iso_utc(None) is None
