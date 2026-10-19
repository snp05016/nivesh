import logging

from fastapi import APIRouter, Depends, Query
from core.security import require_auth
from services import data_flags, instruments
# ponytail: router->router import; move the NSE index into a service when ARCH-13 relocates market search
from routers.market import search_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Universal Search"])


@router.get("")
@router.get("/", include_in_schema=False)
def universal_search(
    query: str = "",
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(require_auth),
):
    """Universal stock search. Returns the bare [{ticker, company_name, sector, exchange}] list the iOS client decodes."""
    results = list(search_endpoint(q=query, limit=limit))
    if len(results) < limit and data_flags.enabled("data_instruments"):
        # New listings the bundled directory lacks; a DB problem must never fail search.
        try:
            seen = {r["ticker"] for r in results}
            for extra in instruments.search_new_listings(query, limit - len(results)):
                if extra["ticker"] not in seen:
                    results.append(extra)
        except Exception:
            logger.exception("search: new-listing lookup failed")
    return results
