"""Time convention (DB-24): DateTime columns hold naive UTC; trading-date keys use IST.

DB columns are timezone-naive, so anything written must be UTC wall time and anything
read is treated as UTC. Calendar-day keys (analysis_date, cache keys) are the Indian
trading date, never the server's local date.
"""
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def utcnow() -> datetime:
    """Aware UTC now."""
    return datetime.now(timezone.utc)


def ist_today(now: Optional[datetime] = None) -> date:
    """Today's date in IST, independent of the server timezone. Naive `now` is read as UTC."""
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(IST).date()


def to_utc_naive(dt: datetime) -> datetime:
    """Convert an aware datetime to naive UTC (for naive DB columns); naive input is returned as is."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
