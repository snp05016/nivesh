"""Legacy analysis cutover (spec 6.6, 9.5; decision D24).

``legacy_gate`` is an HTTP middleware (``app.middleware("http")(legacy_gate)``)
that answers retired legacy routes with ``410 text/plain`` ``LEGACY_GONE_TEXT``
before routing: no auth, no compute, no History writes. Shipped iOS builds show
the body verbatim through ``NetworkError.serverError``.

- ``/analyze/batch*`` is gone in every state (LLM-03).
- With ``RESEARCH_LEGACY_RETIRED=true`` (Stage 3, never unset) every path
  starting ``/analyze``, exact ``POST /batch`` and ``/daily-action/*`` are gone.

``retired_ml_signal`` is the Stage 3 payload of
``GET /api/v1/stocks/{symbol}/ml-signal`` (ML-01): never "NEUTRAL".
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from schemas.ml_signal import MLSignalResponse

from . import config
from .templates import LEGACY_GONE_TEXT

ALWAYS_GONE_PREFIX = "/analyze/batch"
RETIRED_PREFIXES = ("/analyze", "/daily-action/")


def is_gone(method: str, path: str, legacy_retired: bool) -> bool:
    """True when ``method path`` must get the 410."""
    if path.startswith(ALWAYS_GONE_PREFIX):
        return True
    if not legacy_retired:
        return False
    return path.startswith(RETIRED_PREFIXES) or (method == "POST" and path == "/batch")


async def legacy_gate(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """410 retired legacy routes; pass everything else through."""
    # Read the flag per request: tests and /healthz reload config.CONFIG.
    if is_gone(request.method, request.url.path, config.CONFIG.legacy_retired):
        return PlainTextResponse(LEGACY_GONE_TEXT, status_code=410)
    return await call_next(request)


def retired_ml_signal(symbol: str) -> MLSignalResponse:
    """The Stage 3 ml-signal payload; ml-engine is never called."""
    return MLSignalResponse(
        symbol=symbol.strip().upper(),
        direction=0,
        direction_label="UNAVAILABLE",
        confidence=None,
        confidence_pct=None,
        ml_engine_mode="retired",
        lightgbm_loaded=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
        feature_drivers=[],
        status="unavailable",
        warning="Retired",
    )
