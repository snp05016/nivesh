"""GET /api/v1/stocks/{symbol}/results-digest: the latest results card (I25). Flag data_results_digest."""
import re

from fastapi import APIRouter, Depends, HTTPException

from core.security import require_auth
from services import data_flags, results_digest

router = APIRouter(prefix="/api/v1/stocks", tags=["Results"])

_SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")


@router.get("/{symbol}/results-digest")
def get_results_digest(symbol: str, user_id: int = Depends(require_auth)):
    data_flags.require("data_results_digest", user_id)
    clean = symbol.strip().upper()
    for suffix in (".NS", ".BO"):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
    if not _SYMBOL_RE.match(clean):
        raise HTTPException(status_code=422, detail={"code": "INVALID_SYMBOL"})
    payload = results_digest.latest_digest(clean)
    if payload is None:
        raise HTTPException(status_code=404, detail={"code": "NO_DIGEST"})
    return payload
