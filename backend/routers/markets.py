from fastapi import APIRouter, Depends
from core.security import require_auth

router = APIRouter(prefix="/api/v1/markets", tags=["Global Markets"])

@router.get("/overview")
def get_global_markets_overview(user_id: int = Depends(require_auth)):
    """Returns a global markets overview."""
    return {"status": "success", "data": {"indices": [], "commodities": []}}
