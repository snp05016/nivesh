"""Platform feature flags with an admin DB override.

Resolution per key: a feature_flags row (source 'db'), then env FEATURE_<KEY>
(source 'env'), then the FLAG_DEFAULTS default (source 'default'). Unknown keys
resolve to False. The env-only flags of core.feature_flags (money cluster, with
require_flag) are separate; this module reuses its token parsing and is the
registry of flags an admin may switch at runtime.

Rows are cached for 30 s; a DB error falls back to env and defaults and never raises.
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from core.feature_flags import _FALSE, _TRUE
from database import get_session
from models.db_models import FeatureFlag

logger = logging.getLogger(__name__)

FLAG_DEFAULTS: dict[str, dict] = {
    "analytics": {
        "default": False,
        "client": True,
        "description": (
            "Product analytics (I47): store consented usage events; iOS logs them and shows "
            "the one-time ask. Turn on only after the privacy policy names analytics."
        ),
    },
}

_CACHE_TTL_S = 30.0
_lock = threading.Lock()
_cache: Optional[dict[str, dict]] = None
_cache_at = 0.0
_warned: set[str] = set()


def _reset_cache() -> None:
    global _cache, _cache_at
    with _lock:
        _cache = None
        _cache_at = 0.0
        _warned.clear()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


def _rows() -> dict[str, dict]:
    """key -> {enabled, updated_by, updated_at}; one query per 30 s, {} on any DB error."""
    global _cache, _cache_at
    with _lock:
        if _cache is not None and time.monotonic() - _cache_at < _CACHE_TTL_S:
            return _cache
        try:
            with get_session() as session:
                rows = {
                    r.key: {"enabled": bool(r.enabled), "updated_by": r.updated_by, "updated_at": r.updated_at}
                    for r in session.query(FeatureFlag).all()
                }
        except Exception as exc:
            logger.warning("feature_flags: DB read failed, using env and defaults: %s", type(exc).__name__)
            rows = {}
        _cache, _cache_at = rows, time.monotonic()
        return rows


def _env_value(key: str) -> Optional[bool]:
    raw = os.environ.get("FEATURE_" + key.upper())
    if raw is None:
        return None
    token = raw.strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    return None


def _resolve(key: str, rows: dict[str, dict]) -> tuple[bool, str]:
    if key in rows:
        return rows[key]["enabled"], "db"
    env = _env_value(key)
    if env is not None:
        return env, "env"
    if key in FLAG_DEFAULTS:
        return bool(FLAG_DEFAULTS[key]["default"]), "default"
    with _lock:
        first = key not in _warned
        _warned.add(key)
    if first:
        logger.warning("feature_flags: unknown flag %r resolves to False", key)
    return False, "default"


def is_enabled(key: str) -> bool:
    if key not in FLAG_DEFAULTS:
        return _resolve(key, {})[0]
    return _resolve(key, _rows())[0]


def client_flags() -> dict[str, bool]:
    rows = _rows()
    return {k: _resolve(k, rows)[0] for k, meta in FLAG_DEFAULTS.items() if meta["client"]}


def _entry(key: str, rows: dict[str, dict]) -> dict:
    meta = FLAG_DEFAULTS.get(key)
    enabled, source = _resolve(key, rows)
    row = rows.get(key)
    return {
        "key": key,
        "enabled": enabled,
        "default": bool(meta["default"]) if meta else False,
        "source": source,
        "client_visible": bool(meta["client"]) if meta else False,
        "description": meta["description"] if meta else "unregistered",
        "updated_by": row["updated_by"] if row else None,
        "updated_at": _iso(row["updated_at"]) if row else None,
    }


def list_flags() -> list[dict]:
    rows = _rows()
    keys = list(FLAG_DEFAULTS) + sorted(k for k in rows if k not in FLAG_DEFAULTS)
    return [_entry(k, rows) for k in keys]


def set_flag(key: str, enabled: bool, actor_id: Optional[int]) -> dict:
    """Upsert the DB override for a registered key; visible immediately."""
    if key not in FLAG_DEFAULTS:
        raise KeyError(key)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with get_session() as session:
        row = session.get(FeatureFlag, key)
        if row is None:
            session.add(FeatureFlag(key=key, enabled=bool(enabled), updated_by=actor_id, updated_at=now))
        else:
            row.enabled = bool(enabled)
            row.updated_by = actor_id
            row.updated_at = now
        session.commit()
    _reset_cache()
    return _entry(key, _rows())
