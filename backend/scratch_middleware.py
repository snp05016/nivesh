class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that reads or generates a correlation ID for every
    incoming HTTP request.

    - Reads the ``X-Request-ID`` or ``X-Correlation-ID`` header from the request.
    - If missing, generates a UUID.
    - Stores the value in ``request.state.request_id`` and ``request.state.correlation_id``.
    - Echoes ``X-Request-ID`` on the response headers.
    - Threads it into the logging context via contextvars.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        if not req_id:
            req_id = str(uuid.uuid4())

        request.state.request_id = req_id
        request.state.correlation_id = req_id
        
        # Thread through logging
        token = request_id_context_var.set(req_id)

        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Correlation-ID"] = req_id
            return response
        finally:
            request_id_context_var.reset(token)
