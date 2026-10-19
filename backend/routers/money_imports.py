"""CAS import routes (spec 3.5). Flag money_cas_import; identity from the token."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError

from core.feature_flags import require_flag
from core.security import require_auth
from services import money_cas_import as svc
from services.money_cas_import import CasImportError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/me/imports", tags=["Money"], dependencies=[Depends(require_flag("money_cas_import"))]
)


class CASPreviewBody(BaseModel):
    pdf_base64: str
    password: str
    consent_notice_version: str
    attest_own_statement: bool


def _http(exc: CasImportError) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message}, headers=headers)


def _too_large() -> HTTPException:
    return _http(CasImportError("FILE_TOO_LARGE", 413))


def _invalid() -> HTTPException:
    return HTTPException(
        status_code=422, detail={"code": "INVALID_REQUEST", "message": "The upload could not be read."}
    )


@router.post("/cas/preview")
async def cas_preview(request: Request, user_id: int = Depends(require_auth)):
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > svc.MAX_BODY_BYTES:
        raise _too_large()
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > svc.MAX_BODY_BYTES:
            raise _too_large()
    try:
        parsed = CASPreviewBody.model_validate(json.loads(bytes(body)))
    except (ValidationError, ValueError):  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise _invalid() from None
    try:
        return await run_in_threadpool(
            svc.preview, user_id, parsed.pdf_base64, parsed.password,
            parsed.consent_notice_version, parsed.attest_own_statement,
        )
    except CasImportError as exc:
        raise _http(exc) from None


@router.post("/{batch_id}/commit")
def cas_commit(batch_id: int, user_id: int = Depends(require_auth)):
    try:
        return svc.commit(user_id, batch_id)
    except CasImportError as exc:
        raise _http(exc) from None


@router.post("/{batch_id}/cancel", status_code=204)
def cas_cancel(batch_id: int, user_id: int = Depends(require_auth)):
    try:
        svc.cancel(user_id, batch_id)
    except CasImportError as exc:
        raise _http(exc) from None
    return Response(status_code=204)


@router.delete("/{batch_id}")
def cas_undo(batch_id: int, user_id: int = Depends(require_auth)):
    try:
        return svc.undo(user_id, batch_id)
    except CasImportError as exc:
        raise _http(exc) from None


@router.get("")
def cas_list(user_id: int = Depends(require_auth)):
    return svc.list_imports(user_id)
