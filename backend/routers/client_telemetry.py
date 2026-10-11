"""Client error reports from the iOS app (SILENT-12) — POST /api/v1/telemetry/client-error.

Logs one WARNING line on the 'nivesh.client' logger. No DB, no PII: the app sends
the endpoint path (no query string), HTTP status, error class and a short message.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core.security import rate_limited_user

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])
client_logger = logging.getLogger("nivesh.client")

_MAX_BODY_BYTES = 4096


class ClientErrorReport(BaseModel):
    endpoint: str = Field(max_length=200)
    status: Optional[int] = None
    error_kind: str = Field(max_length=50)
    message: str = Field("", max_length=500)
    app_version: str = Field("", max_length=20)


# No bucket of its own in core.rate_limiter, so it gets the per-user default window.
@router.post("/client-error", status_code=202)
def report_client_error(
    report: ClientErrorReport,
    request: Request,
    user_id: int = Depends(rate_limited_user("client_telemetry")),
):
    if int(request.headers.get("content-length") or 0) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Report too large")
    client_logger.warning(json.dumps({**report.model_dump(), "user_id": user_id}))
    return {"status": "accepted"}
