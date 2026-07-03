from fastapi import APIRouter, Depends, Query
from core.entitlement_gate import require_entitlement
from services.sector_rotation import get_sector_rotation_data

router = APIRouter(prefix="/market", tags=["Market"])

@router.get("/sector-rotation")
def get_sector_rotation(
    period: str = Query("3m", pattern="^(1m|3m|6m|1y)$"),
    user_id: int = Depends(require_entitlement("sector_rotation")),
):
    """
    Returns sector rotation data including return over period, momentum, FII/DII flow, and quadrant placement.

    Gated behind the "sector_rotation" entitlement (pro tier or higher) —
    see services/entitlement_service.py / core/entitlement_gate.py.

    Args:
        period (str): The period.

    Returns:
        Any: The response.
    """
    return get_sector_rotation_data(period)
