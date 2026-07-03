"""Fixed Deposit Marketplace API — MOCK bank/NBFC FD schemes, an FD
calculator, and MOCK-instant-settlement FD bookings.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/fixed_deposit_service.py
(Controller-Service-Repository).

MOCK DATA — simulated for demo purposes, not a real integration. No real
bank/NBFC FD issuer API is called anywhere behind this router, and no real
UPI/net-banking payment gateway processes any money.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.security import require_auth
from services.fixed_deposit_service import (
    book_fixed_deposit,
    calculate_fd_maturity,
    get_fd_scheme_by_id,
    list_bookings_for_user,
    list_fd_schemes,
    seed_mock_fd_schemes_if_empty,
)

router = APIRouter(prefix="/api/fixed-deposits", tags=["Fixed Deposits"])

VALID_PAYMENT_METHODS = {"upi", "net_banking"}


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------

class FDSchemeResponse(BaseModel):
    id: int
    issuer_name: str
    min_tenure_months: int
    max_tenure_months: int
    min_amount: float
    max_amount: float
    interest_rate_pct: float
    senior_citizen_bonus_pct: float

    class Config:
        from_attributes = True


class FDCalculatorRequest(BaseModel):
    principal_amount: float = Field(..., gt=0)
    tenure_months: int = Field(..., gt=0)
    interest_rate_pct: float = Field(..., ge=0)


class FDCalculatorResponse(BaseModel):
    maturity_amount: float
    interest_earned: float


class CreateFDBookingRequest(BaseModel):
    scheme_id: int
    principal_amount: float = Field(..., gt=0)
    tenure_months: int = Field(..., gt=0)
    payment_method: str = Field(..., pattern="^(upi|net_banking)$")
    # MOCK KYC — device_id of the booking device, checked against
    # kyc_consent_service.verify_device_binding() before mock instant
    # settlement. Simulated for demo purposes, not a real device/SIM-binding
    # integration.
    device_id: Optional[str] = None


class FDBookingResponse(BaseModel):
    id: int
    user_id: int
    scheme_id: int
    principal_amount: float
    tenure_months: int
    interest_rate_pct: float
    maturity_amount: float
    payment_method: str
    status: str
    decision_reason: Optional[str] = None
    booked_at: Optional[str] = None
    matures_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# FD schemes — discovery + comparison
# ---------------------------------------------------------------------------

def _serialize_scheme(scheme) -> FDSchemeResponse:
    return FDSchemeResponse(
        id=scheme.id,
        issuer_name=scheme.issuer_name,
        min_tenure_months=scheme.min_tenure_months,
        max_tenure_months=scheme.max_tenure_months,
        min_amount=float(scheme.min_amount),
        max_amount=float(scheme.max_amount),
        interest_rate_pct=float(scheme.interest_rate_pct),
        senior_citizen_bonus_pct=float(scheme.senior_citizen_bonus_pct),
    )


@router.get("/schemes", response_model=List[FDSchemeResponse])
def get_fd_schemes(
    min_tenure_months: Optional[int] = Query(None, gt=0),
    max_tenure_months: Optional[int] = Query(None, gt=0),
):
    """List MOCK bank/NBFC FD schemes for discovery/comparison, optionally
    filtered by tenure range. Client sorts/filters the returned list.
    """
    seed_mock_fd_schemes_if_empty()  # mock data bootstrap — no-op once table is populated
    schemes = list_fd_schemes(min_tenure=min_tenure_months, max_tenure=max_tenure_months)
    return [_serialize_scheme(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=FDSchemeResponse)
def get_fd_scheme(scheme_id: int):
    """Get a single MOCK FD scheme by id."""
    scheme = get_fd_scheme_by_id(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="Fixed deposit scheme not found")
    return _serialize_scheme(scheme)


# ---------------------------------------------------------------------------
# FD calculator
# ---------------------------------------------------------------------------

@router.post("/calculator", response_model=FDCalculatorResponse)
def post_fd_calculator(payload: FDCalculatorRequest):
    """Fixed-deposit calculator — compound interest with quarterly
    compounding (standard Indian FD convention). Pure calculation, no DB
    write.
    """
    try:
        result = calculate_fd_maturity(
            principal=payload.principal_amount,
            tenure_months=payload.tenure_months,
            interest_rate_pct=payload.interest_rate_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return FDCalculatorResponse(**result)


# ---------------------------------------------------------------------------
# FD bookings
# ---------------------------------------------------------------------------

def _serialize_booking(booking) -> FDBookingResponse:
    return FDBookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        scheme_id=booking.scheme_id,
        principal_amount=float(booking.principal_amount),
        tenure_months=booking.tenure_months,
        interest_rate_pct=float(booking.interest_rate_pct),
        maturity_amount=float(booking.maturity_amount),
        payment_method=booking.payment_method,
        status=booking.status,
        decision_reason=booking.decision_reason,
        booked_at=booking.booked_at.isoformat() if booking.booked_at else None,
        matures_at=booking.matures_at.isoformat() if booking.matures_at else None,
    )


@router.post("/bookings", response_model=FDBookingResponse)
def create_fd_booking(payload: CreateFDBookingRequest, user_id: int = Depends(require_auth)):
    """Book a MOCK fixed deposit with mock-instant settlement.

    MOCK DATA — simulated for demo purposes, not a real integration. No
    real UPI/net-banking payment gateway is called; settlement here is
    instant and simulated. A booking only reaches status="confirmed" after
    the MOCK KYC gate (active "sim_binding" consent + verified device
    binding) passes — otherwise it is recorded as "failed".
    """
    try:
        booking = book_fixed_deposit(
            user_id=user_id,
            scheme_id=payload.scheme_id,
            principal_amount=payload.principal_amount,
            tenure_months=payload.tenure_months,
            payment_method=payload.payment_method,
            device_id=payload.device_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _serialize_booking(booking)


@router.get("/bookings", response_model=List[FDBookingResponse])
def get_my_fd_bookings(user_id: int = Depends(require_auth)):
    """List the caller's fixed-deposit bookings, most recent first."""
    return [_serialize_booking(b) for b in list_bookings_for_user(user_id)]
