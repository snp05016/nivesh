"""Time Machine sessions: the stored (config, actions) log replayed on the ml-engine.

An action is appended only after the engine accepts the replay with it (a 422 is
passed through and nothing is stored). ``client_action_id`` is kept inside the
stored action, stripped before the engine sees it, and makes a retried append a
no-op. Session reads never trust a client date: history uses the stored clock.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from database import get_session
from models.db_models import LabSession

from . import LabError, client

MAX_ACTIONS = 5000
MAX_SESSIONS = 50
_EQUITY_LIMIT = Decimal("1e10")  # Numeric(14, 4) holds |x| < 10^10
_NOT_FOUND = {"code": "SESSION_NOT_FOUND"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owned(s, user_id: int, session_id: int) -> LabSession:
    row = s.get(LabSession, session_id)
    if row is None or row.user_id != user_id:
        raise LabError(404, _NOT_FOUND)  # another user's session reads as missing
    return row


def engine_actions(actions: list[dict]) -> list[dict]:
    """The stored log as the engine expects it (client_action_id removed)."""
    return [{k: v for k, v in a.items() if k != "client_action_id"} for a in actions]


def _clock(state: dict) -> Optional[date]:
    try:
        return date.fromisoformat(str(state["clock"]))
    except (KeyError, TypeError, ValueError):
        return None


def _equity(state: dict) -> Optional[Decimal]:
    try:
        value = Decimal(str(state["equity"])).quantize(Decimal("0.0001"))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    return value if value.is_finite() and abs(value) < _EQUITY_LIMIT else None


def _cache_state(row: LabSession, payload: dict) -> None:
    state = payload.get("state") or {}
    row.clock = _clock(state)
    row.equity = _equity(state)
    row.finished = bool(state.get("finished"))
    row.updated_at = _now()


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _header(row: LabSession) -> dict:
    return {"id": row.id, "title": row.title, "scenario_id": row.scenario_id, "created_at": _iso(row.created_at)}


def summary(row: LabSession) -> dict:
    return {
        "id": row.id, "title": row.title, "scenario_id": row.scenario_id, "clock": _iso(row.clock),
        "equity": float(row.equity) if row.equity is not None else None, "finished": bool(row.finished),
        "updated_at": _iso(row.updated_at),
    }


def load(user_id: int, session_id: int) -> tuple[dict, list[dict], dict]:
    """(config, stored actions, header) of the user's session, or 404."""
    with get_session() as s:
        row = _owned(s, user_id, session_id)
        return dict(row.config or {}), list(row.actions or []), _header(row)


def create(user_id: int, config: dict, title: Optional[str], scenario_id: Optional[str]) -> dict:
    """Validate the config by replaying an empty log, then store the session."""
    with get_session() as s:
        # ponytail: check-then-insert, so concurrent creates can pass the cap by a few rows.
        if s.query(LabSession).filter(LabSession.user_id == user_id).count() >= MAX_SESSIONS:
            raise LabError(409, {"code": "SESSION_LIMIT", "limit": MAX_SESSIONS})
    payload = client.sim_state(config, [])
    with get_session() as s:
        row = LabSession(user_id=user_id, title=(title or "").strip() or "Untitled session",
                         scenario_id=scenario_id, config=config, actions=[])
        _cache_state(row, payload)
        s.add(row)
        s.commit()
        return {**_header(row), **payload}


def list_sessions(user_id: int) -> list[dict]:
    with get_session() as s:
        rows = (s.query(LabSession).filter(LabSession.user_id == user_id)
                .order_by(LabSession.updated_at.desc(), LabSession.id.desc()).all())
        return [summary(r) for r in rows]


def get(user_id: int, session_id: int) -> dict:
    config, actions, header = load(user_id, session_id)
    return {**header, **client.sim_state(config, engine_actions(actions))}


def append_action(user_id: int, session_id: int, action: dict, client_action_id: Optional[str]) -> dict:
    """Append `action` if the engine's replay accepts it; idempotent on client_action_id."""
    config, actions, header = load(user_id, session_id)
    if client_action_id and any(a.get("client_action_id") == client_action_id for a in actions):
        return {**header, **client.sim_state(config, engine_actions(actions)), "duplicate": True}
    if len(actions) >= MAX_ACTIONS:
        raise LabError(409, {"code": "ACTION_LIMIT", "limit": MAX_ACTIONS})
    stored = {**action, "client_action_id": client_action_id} if client_action_id else dict(action)
    candidate = actions + [stored]
    payload = client.sim_state(config, engine_actions(candidate))  # 422 propagates; nothing is stored
    with get_session() as s:
        row = _owned(s, user_id, session_id)
        if list(row.actions or []) != actions:  # another append landed during the replay
            raise LabError(409, {"code": "SESSION_CHANGED", "message": "The session changed. Reload and retry."})
        row.actions = candidate
        _cache_state(row, payload)
        s.commit()
    return {**header, **payload}


def history(user_id: int, session_id: int, symbol: str, bars: int) -> dict:
    with get_session() as s:
        row = _owned(s, user_id, session_id)
        config, clock = dict(row.config or {}), row.clock
    if clock is None:
        raise LabError(409, {"code": "SESSION_CLOCK_UNKNOWN"})
    return client.sim_history(config, clock.isoformat(), symbol, bars)


def autopsy(user_id: int, session_id: int, order_id: Optional[str] = None) -> dict:
    config, actions, _header_ = load(user_id, session_id)
    return client.sim_autopsy(config, engine_actions(actions), order_id)


def latest_session_id(user_id: int) -> Optional[int]:
    """The user's most recently updated session, or None."""
    with get_session() as s:
        row = (s.query(LabSession.id).filter(LabSession.user_id == user_id)
               .order_by(LabSession.updated_at.desc(), LabSession.id.desc()).first())
        return row[0] if row else None


def delete(user_id: int, session_id: int) -> None:
    with get_session() as s:
        s.delete(_owned(s, user_id, session_id))
        s.commit()

