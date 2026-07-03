"""Mutual Fund Router API — list/search/filter/detail/NAV-history endpoints.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/mutual_fund_service.py (Controller-Service-Repository).
"""
from typing import List, Optional, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, model_validator

from services.mutual_fund_service import (
    get_fund_by_scheme_code,
    get_nav_history,
    list_funds,
    seed_mock_funds_if_empty,
)

router = APIRouter(prefix="/api/mutual-funds", tags=["Mutual Funds"])


class MutualFundResponse(BaseModel):
    id: int
    scheme_code: Optional[str] = None
    scheme_name: str
    amc_name: str
    category: str
    sub_category: Optional[str] = None
    nav: Optional[float] = None
    nav_date: Optional[str] = None
    aum_cr: Optional[float] = None
    expense_ratio: Optional[float] = None
    returns_1y: Optional[float] = None
    returns_3y: Optional[float] = None
    returns_5y: Optional[float] = None
    risk_level: Optional[str] = None
    fund_manager: Optional[str] = None
    is_direct_plan: Optional[bool] = None
    is_growth_plan: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def fallback_legacy_fields(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            d = dict(data.__dict__)
            if not d.get("scheme_name"):
                d["scheme_name"] = d.get("fund_name", "") or ""
            if not d.get("amc_name"):
                d["amc_name"] = d.get("amc", "") or ""
            if not d.get("category"):
                d["category"] = d.get("category", "") or ""
            return d
        elif isinstance(data, dict):
            if not data.get("scheme_name"):
                data["scheme_name"] = data.get("fund_name", "") or ""
            if not data.get("amc_name"):
                data["amc_name"] = data.get("amc", "") or ""
            if not data.get("category"):
                data["category"] = data.get("category", "") or ""
        return data

    class Config:
        orm_mode = True
        from_attributes = True


class NavHistoryPoint(BaseModel):
    date: str
    nav: float


@router.get("/", response_model=List[MutualFundResponse])
def get_mutual_funds(
    category: Optional[str] = Query(None, description="Filter by category, e.g. Equity, Debt, Hybrid"),
    amc_name: Optional[str] = Query(None, description="Filter by AMC name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    search: Optional[str] = Query(None, description="Free-text search on scheme name"),
):
    """List/search/filter mutual funds."""
    seed_mock_funds_if_empty()  # mock data bootstrap — no-op once table is populated
    return list_funds(category=category, amc_name=amc_name, search=search, risk_level=risk_level)


@router.get("/{scheme_code}", response_model=MutualFundResponse)
def get_mutual_fund_detail(scheme_code: str):
    """Get mutual fund detail by scheme_code."""
    seed_mock_funds_if_empty()
    fund = get_fund_by_scheme_code(scheme_code)
    if not fund:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return fund


@router.get("/{scheme_code}/nav-history", response_model=List[NavHistoryPoint])
def get_mutual_fund_nav_history(
    scheme_code: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of NAV history to return"),
):
    """Get NAV history (list of {date, nav}) for a scheme."""
    seed_mock_funds_if_empty()
    history = get_nav_history(scheme_code, days=days)
    if history is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return history
