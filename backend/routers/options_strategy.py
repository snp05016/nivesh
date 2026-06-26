"""
Options Strategy Builder — Router

AGENTS.md §3.1: Router handles HTTP validation and routing only.
All business logic delegated to services/options_engine.py.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import logging

from services.options_engine import compute_options_payoff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Options Strategy"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OptionLegRequest(BaseModel):
    type: str = Field(..., description="Option type: CALL or PUT")
    position: str = Field(..., description="Position: LONG or SHORT")
    strike: float = Field(..., gt=0, description="Strike price of the option")
    premium: float = Field(default=0.0, ge=0, description="Premium paid/received per share")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v_upper = v.upper().strip()
        if v_upper not in ("CALL", "PUT"):
            raise ValueError(f"type must be CALL or PUT, got: {v}")
        return v_upper

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: str) -> str:
        v_upper = v.upper().strip()
        if v_upper not in ("LONG", "SHORT"):
            raise ValueError(f"position must be LONG or SHORT, got: {v}")
        return v_upper


class OptionsPayoffRequest(BaseModel):
    spot_price: float = Field(..., gt=0, description="Current underlying price (₹)")
    legs: List[OptionLegRequest] = Field(..., min_length=1, description="List of option legs in the strategy")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PayoffPoint(BaseModel):
    underlying_price: float
    pnl: float


class OptionsPayoffResponse(BaseModel):
    spot_price: float
    payoff_vector: List[PayoffPoint]
    max_profit: Optional[float] = None
    max_profit_unlimited: bool = False
    max_profit_formatted: str
    max_loss: Optional[float] = None
    max_loss_unlimited: bool = False
    max_loss_formatted: str
    breakevens: List[float]
    net_premium: float
    net_premium_formatted: str
    num_legs: int
    strategy_type: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/options/payoff", response_model=OptionsPayoffResponse)
def compute_strategy_payoff(req: OptionsPayoffRequest):
    """
    Compute the P&L payoff curve and key metrics for a multi-leg options strategy.

Accepts up to 10 legs. Each leg specifies CALL/PUT, LONG/SHORT, strike, and premium.
Returns the full payoff vector (100 price points ±20% around spot) plus:
- Max profit, max loss (or "Unlimited" if uncapped)
- Breakeven points
- Net premium (credit/debit)
- Strategy classification (e.g. "Iron Condor", "Bull Call Spread")

    Args:
        req (OptionsPayoffRequest): The req.

    Returns:
        Any: The response.
    """
    if len(req.legs) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 legs supported.")

    legs_dict = [leg.model_dump() for leg in req.legs]

    try:
        result = compute_options_payoff(
            spot_price=req.spot_price,
            legs=legs_dict,
        )
        return result
    except ValueError as e:
        logger.warning(f"Options payoff computation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in options payoff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error computing payoff.")
