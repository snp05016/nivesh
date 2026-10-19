"""Admin dashboard: the static page and its admin-only JSON feeds (moved out of main.py, REL-15).

Markup, CSS and JS live in static/admin (served at /admin-assets by main.py) so the
page CSP can forbid inline script (AUTH-19). Payloads are built in
services/admin_dashboard_service.py.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from core.security import require_admin
from services import admin_dashboard_service as svc

router = APIRouter()
logger = logging.getLogger("nivesh.main")

ADMIN_DIR = Path(__file__).resolve().parent.parent / "static" / "admin"

# ponytail: style-src keeps 'unsafe-inline' for ~100 inline style attributes (CSS-only risk);
# move them into admin.css to drop it.
_ADMIN_CSP = (
    "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)


@router.get("/", response_class=FileResponse)
def dashboard_html():
    """Serve the admin dashboard page with its own CSP (no inline script allowed)."""
    return FileResponse(ADMIN_DIR / "index.html", headers={"Content-Security-Policy": _ADMIN_CSP})


@router.get("/dashboard-data")
def dashboard_data(authorization: str = Header(None)):
    """Telemetry and state for the admin dashboard: uptime, jobs, tokens, caches, DB counts."""
    require_admin(authorization)
    return svc.build_dashboard_data()


@router.get("/dashboard-data/analysis/{analysis_id}")
def dashboard_analysis_detail(analysis_id: int, authorization: str = Header(None)):
    """raw_output/full_json for one archive row, fetched when the admin expands it."""
    require_admin(authorization)
    detail = svc.get_analysis_detail(analysis_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return detail


@router.get("/dashboard-user-data")
def dashboard_user_data(user_id: int, authorization: str = Header(None)):
    """One user's details, holdings, alerts, journal and recent analyses for the admin dashboard."""
    require_admin(authorization)
    try:
        return svc.build_user_data(user_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception:
        logger.exception("[dashboard-user-data] failed for user %s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error")
