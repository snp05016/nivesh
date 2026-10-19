"""Lab School: curriculum proxy, grading with stored learner state, next lessons.

The learner state is opaque to the backend (the ml-engine school engine owns its
shape: ``{"version", "mastery": {concept: p_known}, "completed", "skipped"}``);
the backend only stores what the grader returns.
"""
from __future__ import annotations

from datetime import datetime, timezone

from database import get_session
from models.db_models import LabLearnerProgress

from . import LabError, client, sessions

MASTERY = 0.95  # same threshold as ml-engine lab/school/engine.py


def _state(user_id: int) -> dict:
    with get_session() as s:
        row = s.get(LabLearnerProgress, user_id)
        return dict(row.state or {}) if row else {}


def grade(user_id: int, lesson_id: str, answers: list[int]) -> dict:
    """Grade on the engine with the stored state, then save the returned state."""
    result = client.grade(lesson_id, answers, _state(user_id))
    new_state = result.get("state")
    if isinstance(new_state, dict):
        with get_session() as s:
            row = s.get(LabLearnerProgress, user_id)
            if row is None:
                s.add(LabLearnerProgress(user_id=user_id, state=new_state))
            else:
                row.state = new_state
                row.updated_at = datetime.now(timezone.utc)
            s.commit()
    return result


def progress(user_id: int) -> dict:
    state = _state(user_id)
    mastery = state.get("mastery") if isinstance(state.get("mastery"), dict) else {}
    mastered = sorted(c for c, p in mastery.items() if isinstance(p, (int, float)) and p >= MASTERY)
    return {"state": state, "mastered": mastered, "completed": list(state.get("completed") or [])}


def weaknesses(user_id: int) -> list[str]:
    """Behaviour flag ids from the autopsy of the user's most recently updated session."""
    session_id = sessions.latest_session_id(user_id)
    if session_id is None:
        return []
    try:
        autopsy = sessions.autopsy(user_id, session_id)
    except LabError as e:
        if e.status_code >= 500:
            raise
        return []  # a session the engine can no longer replay has no usable flags
    return [str(f["id"]) for f in autopsy.get("behaviour") or [] if isinstance(f, dict) and f.get("id")]


def next_lessons(user_id: int, k: int) -> dict:
    return client.next_lessons(_state(user_id), weaknesses(user_id), k)
