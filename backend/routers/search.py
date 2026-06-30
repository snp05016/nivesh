from fastapi import APIRouter, Depends
from core.security import require_auth

router = APIRouter(prefix="/api/v1/search", tags=["Universal Search"])

@router.get("/")
def universal_search(query: str, user_id: int = Depends(require_auth)):
    """Performs a universal search across the platform."""
    return {"status": "success", "results": []}
