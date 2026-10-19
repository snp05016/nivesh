"""GET /api/v1/me/portfolio/xray: stocks and funds across the whole portfolio (I28). Flag money_xray."""
from fastapi import APIRouter, Depends

from core.feature_flags import require_flag
from core.security import require_auth
from services.money_xray import build_xray

router = APIRouter(prefix="/api/v1/me/portfolio", tags=["Money"])


@router.get("/xray", dependencies=[Depends(require_flag("money_xray"))])
def portfolio_xray(user_id: int = Depends(require_auth)):
    return build_xray(user_id)
