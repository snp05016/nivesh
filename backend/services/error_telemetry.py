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
import contextvars
import logging
from datetime import datetime, timezone

import httpx

request_id_context_var = contextvars.ContextVar("request_id", default="-")

class RequestIDLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_context_var.get()
        return True

# Ensure root logger uses this filter and formats request_id
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIDLogFilter())

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
    except Exception as _e:
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
        except Exception as _e:
            pass

    # ------------------------------------------------------------------
    # Print to stdout for server console
    # ------------------------------------------------------------------
    logging.info(f"[DIAGNOSTIC_ERROR] error_uuid={error_uuid}")
    logging.info(payload_json)

    return error_uuid


# ---------------------------------------------------------------------------
# CorrelationIDMiddleware — inject request-scoped correlation IDs
# ---------------------------------------------------------------------------


def generate_daily_digest() -> str:
    """
    Summarize all errors logged in the last 24 hours from market_error_logs.
    Writes a human-readable digest to backend/logs/nightly_digest_<date>.txt.
    Returns the digest text (also logged at INFO level).

    Called at 7:00 AM IST each morning so you wake up to a summary of overnight issues.
    """
    import os
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    from collections import Counter

    digest_lines: list[str] = []
    # Use naive UTC datetime since SQLite drops timezone info, avoiding TypeError
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    try:
        from database import get_session, MarketErrorLog, EarningsErrorLog, NotificationErrorLog, IdeasErrorLog

        with get_session() as session:
            rows_market = (
                session.query(MarketErrorLog)
                .filter(MarketErrorLog.timestamp >= since)
                .all()
            )
            rows_earnings = (
                session.query(EarningsErrorLog)
                .filter(EarningsErrorLog.timestamp >= since)
                .all()
            )
            rows_notif = (
                session.query(NotificationErrorLog)
                .filter(NotificationErrorLog.timestamp >= since)
                .all()
            )
            rows_ideas = (
                session.query(IdeasErrorLog)
                .filter(IdeasErrorLog.timestamp >= since)
                .all()
            )
            
            # Combine into a unified format for digest
            class UnifiedError:
                def __init__(self, timestamp, component, context_ticker, error_message):
                    self.timestamp = timestamp
                    self.component = component
                    self.context_ticker = context_ticker
                    self.error_message = error_message
            
            all_errors = []
            for r in rows_market:
                all_errors.append(UnifiedError(r.timestamp, r.component, r.context_ticker, r.error_message))
            for r in rows_earnings:
                all_errors.append(UnifiedError(r.timestamp, r.module, r.failed_ticker, r.error_trace))
            for r in rows_notif:
                all_errors.append(UnifiedError(r.timestamp, "notification", r.recipient_id, r.error_trace))
            for r in rows_ideas:
                all_errors.append(UnifiedError(r.timestamp, "ideas", r.idea_id, r.error_message))
            
            # Sort descending
            all_errors.sort(key=lambda x: x.timestamp or since, reverse=True)
            rows = all_errors
            
    except Exception as e:
        rows = []
        digest_lines.append(f"[DIGEST] Could not query error logs: {e}")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    digest_lines.append(f"╔══ NIVESH NIGHTLY DIGEST — {now_str} ══╗")
    digest_lines.append(f"  Errors in last 24h: {len(rows)}")

    if rows:
        # Count by component
        component_counts = Counter(r.component for r in rows)
        digest_lines.append("\n  ── Errors by subsystem ──")
        for component, count in component_counts.most_common():
            digest_lines.append(f"    {component}: {count}")

        # Most recent 10 errors
        digest_lines.append("\n  ── Most recent 10 errors ──")
        for r in rows[:10]:
            ts = r.timestamp.strftime("%H:%M") if r.timestamp else "??"
            ticker = f" [{r.context_ticker}]" if r.context_ticker else ""
            msg_preview = (r.error_message or "")[:120].replace("\n", " ")
            digest_lines.append(f"    {ts}  {r.component}{ticker}: {msg_preview}")
    else:
        digest_lines.append("  ✅ No errors logged — clean run!")

    digest_lines.append("╚══════════════════════════════════════════╝")
    digest_text = "\n".join(digest_lines)

    # Write to logs dir
    try:
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        digest_path = logs_dir / f"nightly_digest_{date_str}.txt"
        digest_path.write_text(digest_text, encoding="utf-8")
    except Exception as e:
        digest_lines.append(f"  [WARN] Could not write digest file: {e}")

    logging.info(digest_text)

    # Deliver to the operator (OPS-14): plain-text POST, ntfy.sh compatible.
    webhook_url = os.getenv("OPS_ALERT_WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            httpx.post(
                webhook_url,
                content=digest_text[:4000].encode("utf-8"),
                headers={"Title": "Nivesh daily error digest"},
                timeout=10,
            ).raise_for_status()
        except Exception as e:
            logging.warning("Could not deliver error digest to OPS_ALERT_WEBHOOK_URL: %s", type(e).__name__)
    return digest_text


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
