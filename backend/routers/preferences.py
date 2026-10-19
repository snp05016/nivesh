"""Preferences API — GET/PUT /api/v1/preferences."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional

from core.security import require_auth
from services.preferences import get_preferences, save_preferences

router = APIRouter(prefix="/api/v1/preferences", tags=["Preferences"])


class PreferencesResponse(BaseModel):
    user_id: int
    theme: str = "banknote_standard"
    alerts_enabled: bool = True
    preferred_language: Literal["en", "hi"] = "en"


class PreferencesUpdateRequest(BaseModel):
    # Unknown fields (e.g. profiling answers) are rejected with 422, not dropped.
    model_config = ConfigDict(extra="forbid")

    theme: Optional[str] = None
    alerts_enabled: Optional[bool] = None
    preferred_language: Optional[Literal["en", "hi"]] = None


@router.get("", response_model=PreferencesResponse)
def get_prefs(user_id: int = Depends(require_auth)):
    prefs = get_preferences(user_id)
    if not prefs:
        return PreferencesResponse(user_id=user_id)
    return PreferencesResponse(**prefs)


@router.put("", response_model=PreferencesResponse)
def update_prefs(req: PreferencesUpdateRequest, user_id: int = Depends(require_auth)):
    result = save_preferences(
        user_id,
        theme=req.theme,
        alerts_enabled=req.alerts_enabled,
        preferred_language=req.preferred_language,
    )
    return PreferencesResponse(**result)
