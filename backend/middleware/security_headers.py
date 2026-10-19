"""Security headers, request-body cap and per-IP rate limit for every response."""
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Module-attribute lookup: core.rate_limiter._check_rate_limit is the single patch point.
from core import rate_limiter as _rate_limiter

_MAX_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(1_048_576)))
# Routes that accept larger bodies enforce their own (streamed) cap; keep in sync with the route.
_PATH_BODY_LIMITS = {"/api/v1/me/imports/cas/preview": 15_000_000}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject security headers and enforce basic rate limits.
    """
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path

        # REL-23: reject oversized bodies before any route parses them.
        # ponytail: Content-Length only; chunked bodies need a proxy limit
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > _PATH_BODY_LIMITS.get(endpoint, _MAX_BODY_BYTES):
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})

        try:
            _rate_limiter._check_rate_limit(client_ip, endpoint, request.method)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # setdefault: the admin dashboard route sets its own, wider policy.
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Fixes #109, GH-695: never cache a response by default. Legacy user-data routes
        # (/portfolio/{id}, /watchlist/{id}, /alerts/{id}, ...) live outside /api/.
        # A route that sets its own Cache-Control (e.g. GET /api/v1/features) keeps it.
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
        return response
