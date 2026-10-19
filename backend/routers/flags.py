"""GET /api/v1/flags: server-side platform flags for the app (public; see services/feature_flags)."""
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from core.security import get_current_user_id
from services import feature_flags, kyc_consent_service
from services.retention import USER_EVENTS_RETENTION_DAYS

router = APIRouter(prefix="/api/v1/flags", tags=["Flags"])


@router.get("")
def get_flags(user_id: Optional[int] = Depends(get_current_user_id)):
    flags = feature_flags.client_flags()
    # Per caller: true only with a valid token, the global flag on and an active consent.
    consented = False
    if user_id is not None and flags.get("analytics"):
        try:
            consented = kyc_consent_service.has_active_consent(user_id, "product_analytics")
        except Exception:
            consented = False
    flags["analytics_consented"] = consented
    # The body depends on the caller's token, so no proxy or URLCache may share it.
    return JSONResponse(
        {"flags": flags, "analytics_retention_days": USER_EVENTS_RETENTION_DAYS},
        headers={"Cache-Control": "no-store, private", "Vary": "Authorization"},
    )
