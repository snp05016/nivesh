"""GET /api/v1/features: server-side feature flags for the app (no auth; no user data)."""
from fastapi import APIRouter, Response

from core.feature_flags import client_flags

router = APIRouter(prefix="/api/v1", tags=["Features"])


@router.get("/features")
def get_features(response: Response):
    # SecurityHeadersMiddleware keeps an explicit route Cache-Control.
    response.headers["Cache-Control"] = "private, max-age=300"
    return {"flags": client_flags(), "version": 1}
