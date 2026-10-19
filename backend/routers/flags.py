"""GET /api/v1/flags: server-side platform flags for the app (public; see services/feature_flags)."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services import feature_flags

router = APIRouter(prefix="/api/v1/flags", tags=["Flags"])


@router.get("")
def get_flags():
    # The body depends on the caller's token once events add per-user fields,
    # so no proxy or URLCache may share it.
    return JSONResponse(
        {"flags": feature_flags.client_flags()},
        headers={"Cache-Control": "no-store, private", "Vary": "Authorization"},
    )
