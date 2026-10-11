"""
ML Signal Endpoint
/api/v1/stocks/{symbol}/ml-signal — ml-engine prediction for one ticker.

Split out of the removed stock_financials router (FAKE-04), whose other handlers
served seeded-random financials and invented governance allegations.
"""

from fastapi import APIRouter, Depends

from helpers import require_auth
from schemas.ml_signal import MLSignalResponse

router = APIRouter()


@router.get(
    "/api/v1/stocks/{symbol}/ml-signal",
    response_model=MLSignalResponse,
    summary="ML Signal for Stock",
    description="Returns the ML engine prediction signal for a given ticker. "
    "Proxies to the LightGBM-based ML engine and enriches with reliability metrics.",
)
async def get_stock_ml_signal(symbol: str, user_id: int = Depends(require_auth)):
    """
    Return ML prediction signal for a given ticker.

    Args:
        symbol (str): The symbol.
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    from services.ml_signal_service import get_ml_signal_cached

    return await get_ml_signal_cached(symbol)
