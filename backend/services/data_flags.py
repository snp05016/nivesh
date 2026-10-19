"""Cohort-aware wrapper over core.feature_flags for the data cluster.

A flag that is off can still be on for an env allowlist of user ids
(FEATURE_<KEY>_USERS), so Defer features reach an internal cohort first.
"""
import logging
import os

from fastapi import HTTPException

from core import feature_flags

logger = logging.getLogger(__name__)

# ponytail: env allowlist; move into feature_flags if it gains per-user targeting
_warned: set[tuple[str, str]] = set()  # (key, bad entry) already logged


def enabled(key: str) -> bool:
    return feature_flags.is_enabled(key)


def _allowlist(key: str) -> frozenset[int]:
    """User ids in FEATURE_<KEY>_USERS; bad entries are skipped with one warning each."""
    raw = os.environ.get("FEATURE_" + key.upper() + "_USERS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        entry = part.strip()
        if not entry:
            continue
        try:
            value = int(entry)
        except ValueError:
            value = 0
        if value > 0:
            ids.add(value)
        elif (key, entry) not in _warned:
            _warned.add((key, entry))
            logger.warning("FEATURE_%s_USERS: ignoring %r (not a positive integer)", key.upper(), entry)
    return frozenset(ids)


def enabled_for(key: str, user_id: int | None) -> bool:
    return enabled(key) or (user_id is not None and user_id in _allowlist(key))


def any_enabled(key: str) -> bool:
    """True when the flag is on or a cohort exists; jobs use this so a cohort gets data."""
    return enabled(key) or bool(_allowlist(key))


def require(key: str, user_id: int | None = None) -> None:
    if not enabled_for(key, user_id):
        raise HTTPException(status_code=404, detail={"code": "FEATURE_DISABLED", "feature": key})
