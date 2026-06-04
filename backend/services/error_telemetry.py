"""
Unified Diagnostic Error Logger — Nivesh Backend
==================================================
Single entry-point for all subsystem error telemetry.
Writes to market_error_logs (and earnings_error_logs when applicable),
prints the full JSON payload to stdout, and returns an error_uuid
for the caller to relay back to the iOS client.

Also provides CorrelationIDMiddleware which injects a request-scoped
correlation ID visible in both server and client console logs.
"""

import json
import traceback
import uuid
import sys
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


# ---------------------------------------------------------------------------
# log_diagnostic_error — single unified entry-point for ALL error telemetry
# ---------------------------------------------------------------------------

# Third-party traceback noise — these are always stripped from the traceback.
_NOISE_DIRS = (
    "/site-packages/uvicorn/",
    "/site-packages/starlette/",
    "/site-packages/anyio/",
    "/site-packages/fastapi/",
)

# App-resident paths we keep in the cleaned traceback.
_KEEP_DIRS = (
    "/backend/routers/",
    "/backend/services/",
    "/backend/tradingagents-core/",
)


def _clean_traceback(tb_str: str) -> list[str]:
    """Keep only lines from app-resident paths; strip third-party noise."""
    lines = tb_str.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Keep any line that references an app-resident directory
        if any(keep in line for keep in _KEEP_DIRS):
            cleaned.append(stripped)
            continue
        # Drop known third-party noise
        if any(noise in line for noise in _NOISE_DIRS):
            continue
        # Keep lines that look like file references but aren't in the noise list
        if stripped.startswith("File ") and "/" in stripped:
            continue
        cleaned.append(stripped)
    return cleaned


def log_diagnostic_error(
    subsystem: str,
    classification: str,
    context: dict | None = None,
    telemetry: dict | None = None,
    exception: dict | None = None,
    correlation_id: str | None = None,
    automated_recovery: str | None = None,
) -> str:
    """
    Log a diagnostic error to the database and stdout.

    Parameters
    ----------
    subsystem : str
        Logical subsystem name, e.g. "EARNINGS_CALENDAR", "NSE_DATA_PROVIDER",
        "FILINGS_EXTRACTOR".
    classification : str
        Error classification — "CONNECTION_TIMEOUT", "API_RATE_LIMIT",
        "PARSE_FAILURE", "DB_WRITE_FAILURE", etc.
    context : dict | None
        Business context — target_ticker, market_hours_state, active_data_provider.
    telemetry : dict | None
        Request-scoped metadata — http_method, request_route, ios_swift_file,
        failing_node_contract.
    exception : dict | None
        Exception details — type, message.
    correlation_id : str | None
        Optional correlation ID that ties this error to a specific client request.
    automated_recovery : str | None
        Optional description of any automated recovery action taken.

    Returns
    -------
    str
        The generated error_uuid for the caller to send back to the client.
    """
    error_uuid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build the full telemetry payload
    payload = {
        "error_uuid": error_uuid,
        "timestamp": now,
        "subsystem": subsystem,
        "classification": classification,
        "context": context or {},
        "telemetry": telemetry or {},
        "exception": exception or {},
        "automated_recovery": automated_recovery,
        "correlation_id": correlation_id,
    }

    # Clean traceback from exception if present
    if exception and "type" in exception:
        exc_type = exception.get("type", "")
        exc_msg = exception.get("message", "")
        # Build a synthetic traceback from the current frame if none provided
        tb_lines = traceback.format_exc() if sys.exc_info()[0] is not None else ""
        if tb_lines:
            cleaned = _clean_traceback(tb_lines)
        else:
            cleaned = [f"{exc_type}: {exc_msg}"] if exc_type else []
        payload["exception"]["cleaned_traceback"] = cleaned

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Write to market_error_logs (always)
    # ------------------------------------------------------------------
    try:
        from database import get_session, MarketErrorLog

        with get_session() as session:
            entry = MarketErrorLog(
                component=subsystem,
                error_message=payload_json[:2000],
                context_ticker=(
                    context.get("target_ticker")
                    if isinstance(context, dict)
                    else None
                ),
            )
            session.add(entry)
            session.commit()
    except Exception:
        # telemetry itself must never cascade
        pass

    # ------------------------------------------------------------------
    # Write to earnings_error_logs (only when EARNINGS subsystem)
    # ------------------------------------------------------------------
    if subsystem.upper().startswith("EARNINGS"):
        try:
            from database import get_session, EarningsErrorLog

            with get_session() as session:
                entry = EarningsErrorLog(
                    module=subsystem,
                    error_trace=payload_json[:2000],
                    failed_ticker=(
                        context.get("target_ticker")
                        if isinstance(context, dict)
                        else None
                    ),
                )
                session.add(entry)
                session.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Print to stdout for server console
    # ------------------------------------------------------------------
    print(f"[DIAGNOSTIC_ERROR] error_uuid={error_uuid}")
    print(payload_json)

    return error_uuid


# ---------------------------------------------------------------------------
# CorrelationIDMiddleware — inject request-scoped correlation IDs
# ---------------------------------------------------------------------------


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that reads or generates a correlation ID for every
    incoming HTTP request.

    - Reads the ``X-Correlation-ID`` header from the request.
    - If missing, generates ``nivesh_srv_{uuid4()[:8]}``.
    - Stores the value in ``request.state.correlation_id``.
    - Echoes ``X-Correlation-ID`` on the response headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = f"nivesh_srv_{uuid.uuid4().hex[:8]}"

        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
