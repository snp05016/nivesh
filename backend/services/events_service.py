"""First-party product analytics: the ten allowlisted events (I47).

Every event has a strict prop allowlist of enumerated values, so tickers, holdings, amounts
and free text can never be stored. Identity comes from the token only. Storage needs the
'analytics' flag and an active 'product_analytics' consent, both checked on every batch.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from database import get_session
from models.db_models import UserEvent
from services import feature_flags, kyc_consent_service

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
CONSENT_TYPE = "product_analytics"
MAX_PROPS = 4
MAX_PAST = timedelta(days=7)
MAX_FUTURE = timedelta(minutes=5)

_KIND = {"cas", "csv", "manual"}
EVENT_SCHEMA: dict[str, dict[str, set[str]]] = {
    "app_open": {"launch": {"cold", "warm"}},
    "search": {"results": {"0", "1-5", "6+"}},
    "stock_view": {},
    "report_view": {"state": {"fresh", "stale", "expired", "not_covered", "unavailable"}},
    "report_compute": {"result": {"ok", "quota", "unavailable", "error"}},
    "alert_create": {"direction": {"above", "below"}},
    "import_start": {"kind": _KIND},
    "import_done": {"kind": _KIND, "outcome": {"ok", "partial", "failed"}},
    "paywall_view": {},
    "purchase": {"outcome": {"success", "cancelled", "failed", "pending"}},
}


def validate(name: Any, props: Any) -> bool:
    """True only for an allowlisted event whose props are all allowlisted enumerated values."""
    schema = EVENT_SCHEMA.get(name) if isinstance(name, str) else None
    if schema is None:
        return False
    if props is None:
        props = {}
    if not isinstance(props, dict) or len(props) > MAX_PROPS:
        return False
    return all(
        isinstance(k, str) and isinstance(v, str) and k in schema and v in schema[k]
        for k, v in props.items()
    )


def _clamp_ts(ts: Optional[datetime], now: datetime) -> datetime:
    """Client time as naive UTC, within [now - 7 days, now + 5 minutes], else now."""
    if ts is None:
        return now
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    if ts < now - MAX_PAST or ts > now + MAX_FUTURE:
        return now
    return ts


def _field(event: Any, key: str) -> Any:
    return event.get(key) if isinstance(event, dict) else getattr(event, key, None)


def ingest(user_id: int, events: list, app_version: Optional[str], platform: str = "ios") -> dict:
    """Store the valid events of one batch; returns {'accepted', 'rejected', 'reason'}."""
    if not feature_flags.is_enabled("analytics"):
        return {"accepted": 0, "rejected": len(events), "reason": "disabled"}
    if not kyc_consent_service.has_active_consent(user_id, CONSENT_TYPE):
        return {"accepted": 0, "rejected": len(events), "reason": "no_consent"}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for event in events:
        name, props = _field(event, "name"), _field(event, "props")
        if not validate(name, props):
            continue
        rows.append(UserEvent(
            user_id=user_id,
            event_name=name,
            props=dict(props) if props else None,
            app_version=app_version[:20] if app_version else None,
            platform=platform,
            created_at=_clamp_ts(_field(event, "ts"), now),
        ))
    if rows:
        with get_session() as session:
            session.add_all(rows)
            session.commit()
    return {"accepted": len(rows), "rejected": len(events) - len(rows), "reason": None}


def erase_user_events(user_id: int) -> int:
    """Delete every event of the user (consent withdrawal, DPDP s.6(4)-(6)); returns the count."""
    with get_session() as session:
        deleted = session.execute(delete(UserEvent).where(UserEvent.user_id == user_id)).rowcount or 0
        session.commit()
        return deleted


def daily_counts(days: int = 14) -> dict:
    """Events and distinct users per IST date and event over the last `days` days."""
    days = max(1, min(int(days), 31))
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    with get_session() as session:
        # ponytail: move to SQL date_trunc past ~1M rows a month
        found = (
            session.query(UserEvent.user_id, UserEvent.event_name, UserEvent.created_at)
            .filter(UserEvent.created_at >= since)
            .all()
        )
    users_all: set[int] = set()
    events: dict[tuple[str, str], int] = defaultdict(int)
    users: dict[tuple[str, str], set[int]] = defaultdict(set)
    for user_id, name, created in found:
        local = created.replace(tzinfo=timezone.utc).astimezone(IST).date().isoformat()
        events[(local, name)] += 1
        users[(local, name)].add(user_id)
        users_all.add(user_id)
    rows = [
        {"date": d, "event_name": n, "events": events[(d, n)], "users": len(users[(d, n)])}
        for (d, n) in sorted(events, reverse=True)
    ]
    return {"days": days, "active_users": len(users_all), "rows": rows}
