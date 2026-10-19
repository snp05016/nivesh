"""Preferences service — CRUD for user_preferences table."""
from database import get_session
from models.db_models import UserPreference


def _to_dict(pref: UserPreference) -> dict:
    return {
        "user_id": pref.user_id,
        "theme": pref.theme,
        "alerts_enabled": pref.alerts_enabled,
        "preferred_language": pref.preferred_language or "en",
    }


def get_preferences(user_id: int) -> dict | None:
    with get_session() as session:
        pref = session.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            return None
        return _to_dict(pref)


def push_allowed(user_id: int) -> bool:
    """False only when the user explicitly switched pushes off (no row = default on)."""
    prefs = get_preferences(user_id)
    return prefs is None or prefs.get("alerts_enabled") is not False


def save_preferences(
    user_id: int,
    theme: str | None = None,
    alerts_enabled: bool | None = None,
    preferred_language: str | None = None,
) -> dict:
    with get_session() as session:
        pref = session.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            pref = UserPreference(user_id=user_id)
            session.add(pref)
        if theme is not None:
            pref.theme = theme  # pyright: ignore[reportAttributeAccessIssue]  (legacy Column)
        if alerts_enabled is not None:
            pref.alerts_enabled = alerts_enabled  # pyright: ignore[reportAttributeAccessIssue]  (legacy Column)
        if preferred_language is not None:
            pref.preferred_language = preferred_language  # pyright: ignore[reportAttributeAccessIssue]  (legacy Column)
        session.commit()
        return _to_dict(pref)
