"""Admin error-log routes: /api/v1/admin/{error-logs,earnings-errors,ideas-errors}.

Split out of routers/market.py (ARCH-14); paths, handler names and tags are unchanged.
"""
from helpers import get_session, MarketErrorLog, EarningsErrorLog, IdeasErrorLog
from datetime import timezone
from fastapi import APIRouter, HTTPException, Header
from datetime import datetime as _dt

router = APIRouter(tags=["Market Data"])


# ── /api/v1/admin/error-logs ──────────────────────────────────────────────────

@router.get("/api/v1/admin/error-logs")
def admin_error_logs_endpoint(limit: int = 50, authorization: str = Header(None)):
    """
    Admin diagnostic endpoint — returns recent market_error_logs entries
as a clean JSON stream for iOS console debugging. Requires admin auth.

    Args:
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import require_admin
    require_admin(authorization)
    try:
        with get_session() as session:
            rows = (
                session.query(MarketErrorLog)
                .order_by(MarketErrorLog.timestamp.desc())
                .limit(min(limit, 200))
                .all()
            )
            return {
                "errors": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "component": r.component,
                        "error_message": r.error_message,
                        "context_ticker": r.context_ticker,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error log query failed: {e}")


# ── /api/v1/admin/earnings-errors ──────────────────────────────────────────────

@router.get("/api/v1/admin/earnings-errors")
def admin_earnings_errors_endpoint(limit: int = 50, authorization: str = Header(None)):
    """
    Admin diagnostic endpoint — returns recent earnings_error_logs entries.
Requires admin auth.

    Args:
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import require_admin
    require_admin(authorization)
    try:
        with get_session() as session:
            rows = (
                session.query(EarningsErrorLog)
                .order_by(EarningsErrorLog.timestamp.desc())
                .limit(min(limit, 200))
                .all()
            )
            return {
                "errors": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "module": r.module,
                        "error_trace": r.error_trace,
                        "failed_ticker": r.failed_ticker,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Earnings error log query failed: {e}")


# ── GET /api/v1/admin/ideas-errors ─────────────────────────────────────────

@router.get("/api/v1/admin/ideas-errors")
def admin_ideas_errors_endpoint(limit: int = 50, authorization: str = Header(None)):
    """
    Admin diagnostic endpoint — returns recent IdeasErrorLog entries.
Requires admin auth.
Response: { "errors": [...], "count": N }

    Args:
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    from helpers import require_admin
    require_admin(authorization)
    try:
        with get_session() as session:
            rows = (
                session.query(IdeasErrorLog)
                .order_by(IdeasErrorLog.timestamp.desc())
                .limit(min(limit, 200))
                .all()
            )
            return {
                "errors": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "module": r.module,
                        "error_trace": r.error_trace,
                        "context_ticker": r.context_ticker,
                    }
                    for r in rows
                ],
                "count": len(rows),
                "fetched_at": _dt.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ideas error log query failed: {e}")
