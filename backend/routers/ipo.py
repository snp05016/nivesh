"""IPO Hub API — list/detail/subscription-status endpoints.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/ipo_service.py (Controller-Service-Repository).
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.ipo_service import (
    VALID_STATUSES,
    get_ipo_by_id,
    get_ipo_by_symbol,
    get_subscription_status,
    list_ipos,
    seed_mock_ipos_if_empty,
)

router = APIRouter(prefix="/api/ipo", tags=["IPO"])


class IPOResponse(BaseModel):
    id: int
    company_name: str
    symbol: Optional[str] = None
    price_band_low: Optional[float] = None
    price_band_high: Optional[float] = None
    lot_size: Optional[int] = None
    issue_size_cr: Optional[float] = None
    open_date: Optional[str] = None
    close_date: Optional[str] = None
    listing_date: Optional[str] = None
    status: Optional[str] = None
    gmp: Optional[float] = None

    class Config:
        orm_mode = True
        from_attributes = True


class IPOSubscriptionResponse(BaseModel):
    id: int
    company_name: str
    symbol: Optional[str] = None
    status: Optional[str] = None
    subscription_qib: Optional[float] = None
    subscription_nii: Optional[float] = None
    subscription_retail: Optional[float] = None

    class Config:
        orm_mode = True
        from_attributes = True


@router.get("", response_model=List[IPOResponse])
def list_ipo_hub(
    status: Optional[str] = Query(
        None, description="Filter by status: upcoming, open, closed, listed"
    )
):
    """List IPOs, optionally filtered by status."""
    seed_mock_ipos_if_empty()  # mock data bootstrap — no-op once table is populated
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUSES)}",
        )
    return list_ipos(status=status)


@router.get("/calendar", response_model=List[IPOResponse])
def get_ipo_calendar():
    """Get upcoming and ongoing IPOs (IPO Calendar). Kept for backward compatibility."""
    seed_mock_ipos_if_empty()
    return list_ipos()


@router.get("/symbol/{symbol}", response_model=IPOResponse)
def get_ipo_by_symbol_route(symbol: str):
    """Get IPO detail by ticker symbol."""
    ipo = get_ipo_by_symbol(symbol)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")
    return ipo


@router.get("/{ipo_id}", response_model=IPOResponse)
def get_ipo_detail(ipo_id: int):
    """Get IPO detail by id."""
    ipo = get_ipo_by_id(ipo_id)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")
    return ipo


@router.get("/{ipo_id}/subscription-status", response_model=IPOSubscriptionResponse)
def get_ipo_subscription_status(ipo_id: int):
    """Get subscription status (QIB/NII/Retail) for a specific IPO."""
    ipo = get_subscription_status(ipo_id)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")
    return ipo
