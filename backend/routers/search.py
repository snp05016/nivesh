from fastapi import APIRouter, Depends, Query
from core.security import require_auth
# ponytail: router->router import; move the NSE index into a service when ARCH-13 relocates market search
from routers.market import search_endpoint

router = APIRouter(prefix="/api/v1/search", tags=["Universal Search"])


@router.get("")
@router.get("/", include_in_schema=False)
def universal_search(
    query: str = "",
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(require_auth),
):
    """Universal stock search. Returns the bare [{ticker, company_name, sector, exchange}] list the iOS client decodes."""
    return search_endpoint(q=query, limit=limit)
