"""Logs each HTTP request into the admin dashboard state (core.dashboard_state)."""
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.dashboard_state import _dash_log_request


class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log standard HTTP requests to the dashboard state.
    """
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        dur_ms = (time.time() - start) * 1000
        if request.url.path not in ("/", "/dashboard-data", "/ping"):
            _dash_log_request(
                method=request.method,
                path=request.url.path,
                params=dict(request.query_params),
                status=response.status_code,
                duration_ms=dur_ms,
            )
        return response
