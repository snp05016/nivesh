"""Request logging middleware — records method, path, status, and duration."""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs every non-trivial request to the in-memory dashboard log."""

    _SKIP_PATHS = frozenset({"/", "/dashboard-data", "/ping"})

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        dur_ms = (time.time() - start) * 1000
        if request.url.path not in self._SKIP_PATHS:
            from helpers import _dash_log_request
            _dash_log_request(
                method=request.method,
                path=request.url.path,
                params=dict(request.query_params),
                status=response.status_code,
                duration_ms=dur_ms,
            )
        return response
