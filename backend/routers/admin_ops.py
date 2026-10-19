"""Admin ops API: feature flags, job runs, audit log and usage counts (I46, I08, I47).

Every route requires users.is_admin and is a plain def. Logic lives in services/.
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from core.security import require_admin
from services import audit_service, events_service, feature_flags, job_runs

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class FlagUpdate(BaseModel):
    enabled: bool


@router.get("/flags")
def list_flags(authorization: str = Header(None)):
    require_admin(authorization)
    return {"flags": feature_flags.list_flags()}


@router.put("/flags/{key}")
def set_flag(key: str, body: FlagUpdate, authorization: str = Header(None)):
    admin_id = require_admin(authorization)
    before = next((f for f in feature_flags.list_flags() if f["key"] == key), None)
    try:
        flag = feature_flags.set_flag(key, body.enabled, admin_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown flag")
    audit_service.audit_now(
        admin_id, "admin_flag_changed",
        {"key": key, "from": before["enabled"] if before else False, "to": flag["enabled"]},
    )
    return {"flag": flag}


@router.get("/job-runs")
def list_job_runs(
    job_name: Optional[str] = Query(None, max_length=64),
    status: Optional[str] = Query(None, pattern="^(running|ok|failed)$"),
    limit: int = Query(50, ge=1, le=200),
    before_id: Optional[int] = Query(None, ge=1),
    authorization: str = Header(None),
):
    require_admin(authorization)
    runs = job_runs.list_runs(job_name=job_name, status=status, limit=limit, before_id=before_id)
    return {"runs": runs, "next_before_id": runs[-1]["id"] if len(runs) == limit else None}


@router.get("/job-runs/summary")
def job_runs_summary(days: int = Query(7, ge=1, le=90), authorization: str = Header(None)):
    require_admin(authorization)
    return job_runs.summary(days)


@router.get("/audit")
def list_audit(
    action_prefix: Optional[str] = Query(None, max_length=40),
    limit: int = Query(100, ge=1, le=200),
    before_id: Optional[int] = Query(None, ge=1),
    authorization: str = Header(None),
):
    require_admin(authorization)
    entries = audit_service.list_entries(action_prefix=action_prefix, limit=limit, before_id=before_id)
    return {"entries": entries, "next_before_id": entries[-1]["id"] if len(entries) == limit else None}


@router.get("/analytics/daily")
def analytics_daily(days: int = Query(14, ge=1, le=31), authorization: str = Header(None)):
    require_admin(authorization)
    return events_service.daily_counts(days)
