from fastapi import APIRouter, Query
from services.sector_rotation import get_sector_rotation_data

router = APIRouter(prefix="/market", tags=["Market"])

@router.get("/sector-rotation")
def get_sector_rotation(period: str = Query("3m", pattern="^(1m|3m|6m|1y)$")):
    """
    Returns sector rotation data including return over period, momentum, FII/DII flow, and quadrant placement.

    Args:
        period (str): The period.

    Returns:
        Any: The response.
    """
    return get_sector_rotation_data(period)
