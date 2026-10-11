"""IOSCORE-36: NSE market status honours weekends, holidays and special sessions."""
from datetime import datetime, timezone

from services.market_calendar import IST, market_status

CAL = {
    "holidays": {"2026": ["2026-01-26"]},
    "special_sessions": [{"date": "2026-11-08", "open": "18:00", "close": "19:00", "label": "Muhurat"}],
}


def _at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


def test_weekday_in_hours_open():
    s = market_status(_at(2026, 10, 13, 10), CAL)  # Tuesday
    assert s["is_open"] is True
    assert s["reason"] == "open"
    assert s["session_date"] == "2026-10-13"


def test_before_open_closed():
    s = market_status(_at(2026, 10, 13, 9), CAL)
    assert s["is_open"] is False
    assert s["reason"] == "pre_open"


def test_after_close_closed():
    s = market_status(_at(2026, 10, 13, 15, 30), CAL)
    assert s["is_open"] is False
    assert s["reason"] == "closed"


def test_weekend_closed():
    s = market_status(_at(2026, 10, 11, 11), CAL)  # Sunday
    assert s["is_open"] is False
    assert s["reason"] == "weekend"


def test_holiday_closed():
    s = market_status(_at(2026, 1, 26, 10), CAL)  # Monday, Republic Day in the injected calendar
    assert s["is_open"] is False
    assert s["reason"] == "holiday"


def test_special_session_open():
    assert market_status(_at(2026, 11, 8, 18, 30), CAL)["reason"] == "special_session"
    assert market_status(_at(2026, 11, 8, 18, 30), CAL)["is_open"] is True
    assert market_status(_at(2026, 11, 8, 19, 0), CAL)["is_open"] is False


def test_calendar_known_false_for_missing_year():
    assert market_status(_at(2026, 10, 13, 10), CAL)["calendar_known"] is True
    s = market_status(_at(2027, 1, 26, 10), CAL)
    assert s["calendar_known"] is False
    assert s["is_open"] is True  # unknown year falls back to the clock


def test_utc_input_is_converted_to_ist():
    # 04:30 UTC is 10:00 IST on a Tuesday.
    s = market_status(datetime(2026, 10, 13, 4, 30, tzinfo=timezone.utc), CAL)
    assert s["is_open"] is True


def test_route_returns_status(client):
    resp = client.get("/api/v1/market/status")
    assert resp.status_code == 200
    body = resp.json()
    assert {"is_open", "reason", "session_date", "calendar_known", "as_of"} <= body.keys()
