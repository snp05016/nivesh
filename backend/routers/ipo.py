from fastapi import APIRouter, Depends, HTTPException
from database import get_session
from models.db_models import IPOListing
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/ipo", tags=["IPO"])

class IPOResponse(BaseModel):
    id: int
    company_name: str
    symbol: Optional[str] = None
    open_date: Optional[str] = None
    close_date: Optional[str] = None
    listing_date: Optional[str] = None
    issue_price_min: Optional[float] = None
    issue_price_max: Optional[float] = None
    subscription_status: Optional[str] = None

    class Config:
        orm_mode = True
        from_attributes = True

@router.get("/calendar", response_model=List[IPOResponse])
def get_ipo_calendar():
    """Get upcoming and ongoing IPOs (IPO Calendar)"""
    with get_session() as session:
        ipos = session.query(IPOListing).all()
        return ipos

@router.get("/{ipo_id}/subscription-status", response_model=IPOResponse)
def get_subscription_status(ipo_id: int):
    """Get subscription status for a specific IPO"""
    with get_session() as session:
        ipo = session.query(IPOListing).filter(IPOListing.id == ipo_id).first()
        if not ipo:
            raise HTTPException(status_code=404, detail="IPO not found")
        return ipo
