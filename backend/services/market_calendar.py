"""NSE market status from the IST clock plus the holiday calendar in data/nse_holidays.json."""
import functools
import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_PATH = Path(__file__).resolve().parent.parent / "data" / "nse_holidays.json"
IST = ZoneInfo("Asia/Kolkata")
_PRE_OPEN, _OPEN, _CLOSE = time(9, 0), time(9, 15), time(15, 30)


@functools.lru_cache(maxsize=1)
def _load_calendar() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("market_calendar: failed to load %s: %s", _PATH, e)
        return {}


def market_status(now: Optional[datetime] = None, calendar: Optional[dict] = None) -> dict:
    """Open/closed for the NSE equity session at `now` (default: current time; naive means IST).

    reason is one of open, pre_open, closed, weekend, holiday, special_session.
    calendar_known is False when the holiday list has no entry for that year.
    """
    cal = _load_calendar() if calendar is None else calendar
    if now is None:
        now = datetime.now(timezone.utc)
    now = now.replace(tzinfo=IST) if now.tzinfo is None else now.astimezone(IST)
    day, t = now.date(), now.time()
    iso = day.isoformat()
    year_holidays = (cal.get("holidays") or {}).get(str(day.year))
    special = next((s for s in cal.get("special_sessions") or [] if s.get("date") == iso), None)

    if special:
        is_open = time.fromisoformat(special["open"]) <= t < time.fromisoformat(special["close"])
        reason = "special_session" if is_open else "closed"
    elif day.weekday() >= 5:
        is_open, reason = False, "weekend"
    elif year_holidays and iso in year_holidays:
        is_open, reason = False, "holiday"
    elif _OPEN <= t < _CLOSE:
        is_open, reason = True, "open"
    else:
        is_open, reason = False, "pre_open" if _PRE_OPEN <= t < _OPEN else "closed"

    return {
        "is_open": is_open,
        "reason": reason,
        "session_date": iso,
        "calendar_known": year_holidays is not None,
        "as_of": now.isoformat(),
    }
