from fastapi import APIRouter, Depends, HTTPException
from database import get_session
from models.db_models import MutualFund
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/mutual-funds", tags=["Mutual Funds"])

class MutualFundResponse(BaseModel):
    id: int
    fund_name: str
    amc: str
    category: str
    nav: Optional[float] = None

    class Config:
        orm_mode = True
        from_attributes = True

@router.get("/", response_model=List[MutualFundResponse])
def get_mutual_funds():
    """Get all mutual funds"""
    with get_session() as session:
        funds = session.query(MutualFund).all()
        return funds
