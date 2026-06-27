"""Preferences service — CRUD for user_preferences table."""
from database import get_session
from models.db_models import UserPreference


def get_preferences(user_id: int) -> dict | None:
    with get_session() as session:
        pref = session.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            return None
        return {
            "user_id": pref.user_id,
            "theme": pref.theme,
            "alerts_enabled": pref.alerts_enabled,
        }


def save_preferences(user_id: int, theme: str = None, alerts_enabled: bool = None) -> dict:
    with get_session() as session:
        pref = session.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            pref = UserPreference(user_id=user_id)
            session.add(pref)
        if theme is not None:
            pref.theme = theme
        if alerts_enabled is not None:
            pref.alerts_enabled = alerts_enabled
        session.commit()
        return {
            "user_id": pref.user_id,
            "theme": pref.theme,
            "alerts_enabled": pref.alerts_enabled,
        }
