"""Mutual Fund Router API — list/search/filter/detail/NAV-history endpoints.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/mutual_fund_service.py (Controller-Service-Repository).
"""
from typing import List, Literal, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, model_validator

from core.security import require_auth
from models.db_models import MutualFund
from services.mutual_fund_service import (
    SAMPLE_SCHEME_CODES,
    fund_extras,
    get_fund_by_scheme_code,
    get_nav_history,
    list_filters,
    list_funds,
    mark_tracked,
)

router = APIRouter(tags=["Mutual Funds"])


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
    # True for the seeded sample catalog (frozen illustrative figures, not a
    # live AMFI feed); clients must label these rows as sample data.
    is_sample: bool = False
    # Data foundation: AMFI provenance and ISINs (detail only for the ISINs and history_start).
    scheme_type: Optional[str] = None
    nav_source: Optional[str] = None
    is_active: Optional[bool] = None
    isin_growth: Optional[str] = None
    isin_reinvest: Optional[str] = None
    history_start: Optional[str] = None

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
            d["is_sample"] = d.get("scheme_code") in SAMPLE_SCHEME_CODES
            return d
        elif isinstance(data, dict):
            if not data.get("scheme_name"):
                data["scheme_name"] = data.get("fund_name", "") or ""
            if not data.get("amc_name"):
                data["amc_name"] = data.get("amc", "") or ""
            if not data.get("category"):
                data["category"] = data.get("category", "") or ""
            data["is_sample"] = data.get("scheme_code") in SAMPLE_SCHEME_CODES
        return data

    class Config:
        orm_mode = True
        from_attributes = True


class NavHistoryPoint(BaseModel):
    date: str
    nav: float


@router.get("/", response_model=List[MutualFundResponse])
def get_mutual_funds(
    response: Response,
    category: Optional[str] = Query(None, description="Filter by category, e.g. Equity, Debt, Hybrid"),
    sub_category: Optional[str] = Query(None, description="Filter by AMFI sub-category"),
    amc_name: Optional[str] = Query(None, description="Filter by AMC name"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    search: Optional[str] = Query(None, description="Scheme name, scheme code or ISIN"),
    plan: Literal["direct", "regular", "all"] = "direct",
    option: Literal["growth", "idcw", "all"] = "growth",
    scheme_type: Literal["open", "close", "interval", "all"] = "open",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=20000),
):
    """One page of funds, sorted by name (no performance ranking). X-Total-Count carries the full count."""
    rows, total = list_funds(
        category=category, sub_category=sub_category, amc_name=amc_name, search=search, risk_level=risk_level,
        plan=plan, option=option, scheme_type=scheme_type, limit=limit, offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/filters")
def get_mutual_fund_filters(user_id: int = Depends(require_auth)):
    """Category -> sub-categories and the AMC list, for the filter pickers."""
    return list_filters()


@router.get("/{scheme_code}", response_model=MutualFundResponse)
def get_mutual_fund_detail(scheme_code: str):
    """Get mutual fund detail by scheme_code."""
    fund = get_fund_by_scheme_code(scheme_code)
    if not fund:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    detail = {c.name: getattr(fund, c.name) for c in MutualFund.__table__.columns}
    detail.update(fund_extras(fund))
    if not fund.track_nav and scheme_code not in SAMPLE_SCHEME_CODES:
        mark_tracked([scheme_code])
    return detail


@router.get("/{scheme_code}/nav-history", response_model=List[NavHistoryPoint])
def get_mutual_fund_nav_history(
    scheme_code: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of NAV history to return"),
):
    """Get NAV history (list of {date, nav}) for a scheme; [] when no real history exists."""
    history = get_nav_history(scheme_code, days=days)
    if history is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return history
