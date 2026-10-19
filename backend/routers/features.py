"""Server-side feature flags for the app (no auth; no user data).

GET /api/v1/features (money cluster) and GET /api/v1/app-config (iOS cluster:
flags, research mode and minimum build; pre-login screens and a version-blocked
client must still reach it).
"""
from fastapi import APIRouter, Response

from core.feature_flags import app_config_payload, client_flags

router = APIRouter(prefix="/api/v1", tags=["Features"])


@router.get("/features")
def get_features(response: Response):
    # SecurityHeadersMiddleware keeps an explicit route Cache-Control.
    response.headers["Cache-Control"] = "private, max-age=300"
    return {"flags": client_flags(), "version": 1, "ttl_seconds": 300}


@router.get("/app-config")
def get_app_config(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return app_config_payload()
