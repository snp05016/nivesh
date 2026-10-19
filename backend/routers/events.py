"""POST /api/v1/events: consent-gated first-party analytics batch (I47)."""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.security import rate_limited_user
from services import events_service

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    props: dict[str, str] = {}
    ts: Optional[datetime] = None


class EventsBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=50)
    app_version: Optional[str] = Field(default=None, max_length=20)
    platform: Literal["ios"] = "ios"


@router.post("", status_code=202)
def post_events(body: EventsBatch, user_id: int = Depends(rate_limited_user("events"))):
    """Identity comes from the token only; unknown body fields (such as a user_id) are ignored."""
    return events_service.ingest(user_id, body.events, body.app_version, body.platform)
