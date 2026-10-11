"""Loan Marketplace API — MOCK NBFC loan offers, applications, and a MOCK
credit bureau score lookup.

Controller-only: HTTP validation lives here, all DB access and business
logic live in services/loan_marketplace_service.py and
services/credit_bureau_mock_service.py (Controller-Service-Repository).

MOCK DATA — simulated for demo purposes, not a real integration. No real
NBFC or credit-bureau API is called anywhere behind this router.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from core.demo_mode import require_demo_mode
from core.security import rate_limited_user, require_auth
from services.credit_bureau_mock_service import get_mock_credit_report_summary
from services.finance_tracker_service import (
    create_summary,
    link_demo_account,
    list_accounts,
    list_spend_categories,
)
from services.loan_marketplace_service import (
    BankAccountInUse,
    BankAccountNotFound,
    DisbursementNotFound,
    DisbursementRejected,
    disburse_loan,
    get_application_by_id,
    get_disbursement_for_application,
    link_bank_account,
    list_applications_for_user,
    list_linked_bank_accounts,
    list_loan_offers,
    offer_emi_at_min,
    offer_max_apr,
    set_primary_bank_account,
    submit_loan_application,
    unlink_bank_account,
)
from services.product_bounds import ProductBoundsError

# Demo-only money flows: 404 unless DEMO_MODE=true (FAKE-23).
router = APIRouter(tags=["Loan Marketplace"], dependencies=[Depends(require_demo_mode)])

VALID_LOAN_TYPES = {"personal", "home", "car", "gold", "education"}


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------

class LoanOfferResponse(BaseModel):
    id: int
    nbfc_name: str
    loan_type: str
    min_amount: float
    max_amount: float
    interest_rate_pct: float
    min_tenure_months: int
    max_tenure_months: int
    min_credit_score: int
    processing_fee_pct: float
    # REG-05: APR (IRR on the net disbursal) at the minimum amount and
    # shortest tenure, and the lowest EMI (minimum amount, longest tenure).
    max_apr_pct: float
    emi_at_min: float

    class Config:
        from_attributes = True


class CreditScoreResponse(BaseModel):
    user_id: int
    credit_score: int
    score_band: str
    bureau_name: str
    score_range_min: int
    score_range_max: int


class SubmitLoanApplicationRequest(BaseModel):
    loan_offer_id: int
    # Upper caps keep inputs inside Numeric(14,2); the offer's own range is
    # enforced in the service (check_product_bounds).
    requested_amount: float = Field(..., gt=0, le=1e11)
    requested_tenure_months: int = Field(..., gt=0, le=600)
    # MOCK KYC — device_id of the submitting device, checked against
    # kyc_consent_service.verify_device_binding() before auto-approval.
    # Simulated for demo purposes, not a real device/SIM-binding integration.
    device_id: Optional[str] = None
    # FINSEC-26: the applicant read the KFS for this amount/tenure. Optional
    # so older app builds still submit; their rows keep kfs_acknowledged_at NULL.
    kfs_acknowledged: bool = False


class LoanApplicationResponse(BaseModel):
    id: int
    user_id: int
    loan_offer_id: int
    requested_amount: float
    requested_tenure_months: int
    status: str
    mock_credit_score_at_application: Optional[int] = None
    decision_reason: Optional[str] = None
    submitted_at: Optional[str] = None
    decided_at: Optional[str] = None
    kfs_apr_pct: Optional[float] = None
    kfs_total_fees: Optional[float] = None
    kfs_acknowledged_at: Optional[str] = None

    class Config:
        from_attributes = True


class LoanDisbursementResponse(BaseModel):
    id: int
    loan_application_id: int
    user_id: int
    linked_bank_account_id: Optional[int] = None
    nbfc_name: str
    disbursed_amount: float
    status: str
    disbursed_at: Optional[str] = None
    failure_reason: Optional[str] = None

    class Config:
        from_attributes = True


class LinkedBankAccountResponse(BaseModel):
    id: int
    bank_name: str
    account_type: str
    masked_account_number: str
    ifsc_code: Optional[str] = None
    is_primary: bool
    linked_at: Optional[str] = None

    class Config:
        from_attributes = True


class LinkBankAccountRequest(BaseModel):
    bank_name: str = Field(..., min_length=2, max_length=100)
    # Masked only: 2-16 mask chars then the last 4 digits ("XXXX1234"); full numbers fail with 422.
    masked_account_number: str = Field(..., min_length=6, max_length=20, pattern=r"^[Xx*]{2,16}\d{4}$")
    account_type: str = Field("savings", pattern="^(savings|current)$")
    ifsc_code: Optional[str] = Field(None, pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")


# ---------------------------------------------------------------------------
# Finance Tracker — MOCK linked-account balance/spend-tracking demo.
# Distinct from the Loan Marketplace's LinkedBankAccount models above.
# ---------------------------------------------------------------------------

class FinanceAccountResponse(BaseModel):
    id: int
    bank_name: str
    account_type: str
    masked_account_number: str
    balance: float
    last_synced_at: Optional[str] = None
    is_mock: bool

    class Config:
        from_attributes = True


class FinanceSummaryResponse(BaseModel):
    total_balance: float
    linked_account_count: int
    monthly_income: float
    monthly_spend: float


class SpendCategoryResponse(BaseModel):
    category: str
    amount: float
    percentage: float


class LinkFinanceAccountDemoRequest(BaseModel):
    bank_name: str = Field(..., min_length=2, max_length=100)
    account_type: str = Field(..., pattern="^(savings|current|credit_card|wallet)$")


# ---------------------------------------------------------------------------
# Loan offers
# ---------------------------------------------------------------------------

@router.get("/loan-offers", response_model=List[LoanOfferResponse])
def get_loan_offers(loan_type: Optional[str] = Query(None)):
    """List MOCK NBFC loan offers, optionally filtered by loan_type, ranked by max APR."""
    if loan_type and loan_type not in VALID_LOAN_TYPES:
        raise HTTPException(status_code=400, detail=f"loan_type must be one of {sorted(VALID_LOAN_TYPES)}")
    offers = list_loan_offers(loan_type=loan_type)
    return [
        LoanOfferResponse(
            id=o.id,
            nbfc_name=o.nbfc_name,
            loan_type=o.loan_type,
            min_amount=float(o.min_amount),
            max_amount=float(o.max_amount),
            interest_rate_pct=float(o.interest_rate_pct),
            min_tenure_months=o.min_tenure_months,
            max_tenure_months=o.max_tenure_months,
            min_credit_score=o.min_credit_score,
            processing_fee_pct=float(o.processing_fee_pct),
            max_apr_pct=offer_max_apr(o),
            emi_at_min=offer_emi_at_min(o),
        )
        for o in offers
    ]


# ---------------------------------------------------------------------------
# Mock credit score
# ---------------------------------------------------------------------------

@router.get("/credit-score", response_model=CreditScoreResponse)
def get_my_credit_score(user_id: int = Depends(require_auth)):
    """Return the caller's MOCK credit bureau score.

    MOCK DATA — simulated for demo purposes, not a real credit bureau integration.
    """
    return get_mock_credit_report_summary(user_id)


# ---------------------------------------------------------------------------
# Loan applications
# ---------------------------------------------------------------------------

def _serialize_application(app) -> LoanApplicationResponse:
    return LoanApplicationResponse(
        id=app.id,
        user_id=app.user_id,
        loan_offer_id=app.loan_offer_id,
        requested_amount=float(app.requested_amount),
        requested_tenure_months=app.requested_tenure_months,
        status=app.status,
        mock_credit_score_at_application=app.mock_credit_score_at_application,
        decision_reason=app.decision_reason,
        submitted_at=app.submitted_at.isoformat() if app.submitted_at else None,
        decided_at=app.decided_at.isoformat() if app.decided_at else None,
        kfs_apr_pct=float(app.kfs_apr_pct) if app.kfs_apr_pct is not None else None,
        kfs_total_fees=float(app.kfs_total_fees) if app.kfs_total_fees is not None else None,
        kfs_acknowledged_at=app.kfs_acknowledged_at.isoformat() if app.kfs_acknowledged_at else None,
    )


@router.post("/loan-applications", response_model=LoanApplicationResponse)
def create_loan_application(
    payload: SubmitLoanApplicationRequest,
    user_id: int = Depends(rate_limited_user("money_write")),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", max_length=64),
):
    """Submit a loan application against a MOCK NBFC offer.

    Underwriting is a simplified, clearly-mocked demo rule driven by the
    MOCK credit bureau score — not a real NBFC lending decision.
    """
    try:
        application = submit_loan_application(
            user_id=user_id,
            loan_offer_id=payload.loan_offer_id,
            requested_amount=payload.requested_amount,
            requested_tenure_months=payload.requested_tenure_months,
            device_id=payload.device_id,
            idempotency_key=idempotency_key,
            kfs_acknowledged=payload.kfs_acknowledged,
        )
    except ProductBoundsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _serialize_application(application)


@router.get("/loan-applications", response_model=List[LoanApplicationResponse])
def get_my_loan_applications(user_id: int = Depends(require_auth)):
    """List the caller's loan applications, most recent first."""
    return [_serialize_application(a) for a in list_applications_for_user(user_id)]


@router.get("/loan-applications/{application_id}", response_model=LoanApplicationResponse)
def get_my_loan_application(application_id: int, user_id: int = Depends(require_auth)):
    """Get a single loan application belonging to the caller."""
    application = get_application_by_id(application_id, user_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found")
    return _serialize_application(application)


# ---------------------------------------------------------------------------
# Loan disbursement — MOCK DATA, simulated for demo purposes, not a real
# integration. No real fund transfer, NBFC-to-bank settlement rail, or
# payment gateway is involved; see services/loan_marketplace_service.py.
# ---------------------------------------------------------------------------

def _serialize_disbursement(d) -> LoanDisbursementResponse:
    return LoanDisbursementResponse(
        id=d.id,
        loan_application_id=d.loan_application_id,
        user_id=d.user_id,
        linked_bank_account_id=d.linked_bank_account_id,
        nbfc_name=d.nbfc_name,
        disbursed_amount=float(d.disbursed_amount),
        status=d.status,
        disbursed_at=d.disbursed_at.isoformat() if d.disbursed_at else None,
        failure_reason=d.failure_reason,
    )


@router.post("/loan-applications/{application_id}/disburse", response_model=LoanDisbursementResponse)
def disburse_loan_application(application_id: int, user_id: int = Depends(rate_limited_user("money_write"))):
    """Trigger a MOCK instant disbursement of an approved loan application to
    the caller's primary linked bank account.

    404 if the application is unknown; 409 (detail = reason) if it is not
    approved, already disbursed, or the caller has no primary
    LinkedBankAccount yet. Nothing is persisted on a 409. MOCK DATA — no real
    fund transfer or NBFC settlement rail is involved.
    """
    try:
        disbursement = disburse_loan(application_id, user_id)
    except DisbursementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except DisbursementRejected as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _serialize_disbursement(disbursement)


@router.get("/loan-applications/{application_id}/disbursement", response_model=LoanDisbursementResponse)
def get_loan_application_disbursement(application_id: int, user_id: int = Depends(require_auth)):
    """Fetch the disbursement status/history for a loan application belonging
    to the caller."""
    disbursement = get_disbursement_for_application(application_id, user_id)
    if disbursement is None:
        raise HTTPException(status_code=404, detail="No disbursement found for this loan application")
    return _serialize_disbursement(disbursement)


# ---------------------------------------------------------------------------
# Linked bank accounts (MOCK — user-supplied labels only, no real account
# numbers or account-aggregator integration)
# ---------------------------------------------------------------------------

def _serialize_linked_bank_account(a) -> LinkedBankAccountResponse:
    return LinkedBankAccountResponse(
        id=a.id,
        bank_name=a.bank_name,
        account_type=a.account_type,
        masked_account_number=a.masked_account_number,
        ifsc_code=a.ifsc_code,
        is_primary=a.is_primary,
        linked_at=a.linked_at.isoformat() if a.linked_at else None,
    )


@router.get("/linked-bank-accounts", response_model=List[LinkedBankAccountResponse])
def get_my_linked_bank_accounts(user_id: int = Depends(require_auth)):
    """List the caller's MOCK linked bank accounts."""
    return [_serialize_linked_bank_account(a) for a in list_linked_bank_accounts(user_id)]


@router.post("/linked-bank-accounts", response_model=LinkedBankAccountResponse)
def create_linked_bank_account(payload: LinkBankAccountRequest, user_id: int = Depends(rate_limited_user("money_write"))):
    """Register a MOCK linked bank account for the loan marketplace demo.

    The server only accepts a masked number (2-16 of X/x/* then the last 4
    digits, e.g. "XXXX1234"); a full account number is rejected with 422 and
    never stored. 409 if the same masked number is already linked.
    """
    try:
        account = link_bank_account(
            user_id=user_id,
            bank_name=payload.bank_name,
            masked_account_number=payload.masked_account_number,
            account_type=payload.account_type,
            ifsc_code=payload.ifsc_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _serialize_linked_bank_account(account)


@router.delete("/linked-bank-accounts/{account_id}", status_code=204)
def delete_linked_bank_account(account_id: int, user_id: int = Depends(rate_limited_user("money_write"))):
    """Unlink one of the caller's MOCK bank accounts. Unlinking the primary
    promotes the most recently linked remaining account. 404 if unknown; 409
    if a loan disbursement was paid into it."""
    try:
        unlink_bank_account(user_id, account_id)
    except BankAccountNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BankAccountInUse as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/linked-bank-accounts/{account_id}/primary", response_model=LinkedBankAccountResponse)
def make_linked_bank_account_primary(account_id: int, user_id: int = Depends(rate_limited_user("money_write"))):
    """Make one of the caller's MOCK bank accounts the disbursement (primary)
    account; every other account of the caller stops being primary."""
    try:
        account = set_primary_bank_account(user_id, account_id)
    except BankAccountNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _serialize_linked_bank_account(account)


# ---------------------------------------------------------------------------
# Finance Tracker — MOCK linked-account balance/spend-tracking demo.
#
# MOCK DATA — simulated for demo purposes, not a real integration. No real
# account-aggregator / bank-linking (OAuth/Plaid-style) flow backs any of
# these endpoints. Functionally distinct from /linked-bank-accounts above
# (which backs the Loan Marketplace and has no balance field).
# ---------------------------------------------------------------------------

def _serialize_finance_account(account) -> FinanceAccountResponse:
    return FinanceAccountResponse(
        id=account.id,
        bank_name=account.bank_name,
        account_type=account.account_type,
        masked_account_number=account.masked_account_number,
        balance=float(account.balance),
        last_synced_at=account.last_synced_at.isoformat() if account.last_synced_at else None,
        is_mock=account.is_mock,
    )


@router.get("/accounts", response_model=List[FinanceAccountResponse])
def get_finance_accounts(user_id: int = Depends(require_auth)):
    """List the caller's MOCK Finance Tracker linked accounts."""
    return [_serialize_finance_account(a) for a in list_accounts(user_id)]


@router.get("/summary", response_model=FinanceSummaryResponse)
def get_finance_summary(user_id: int = Depends(require_auth)):
    """Aggregate balance summary across the caller's MOCK linked accounts.

    monthly_income / monthly_spend are MOCK DATA — simulated for demo
    purposes, not a real integration.
    """
    return FinanceSummaryResponse(**create_summary(user_id))


@router.get("/spend-categories", response_model=List[SpendCategoryResponse])
def get_finance_spend_categories(user_id: int = Depends(require_auth)):
    """MOCK proportional spend-by-category breakdown. Not backed by real
    transaction categorization ML — simulated for demo purposes.
    """
    return [SpendCategoryResponse(**c) for c in list_spend_categories(user_id)]


@router.post("/accounts/link-demo", response_model=FinanceAccountResponse)
def post_link_demo_finance_account(payload: LinkFinanceAccountDemoRequest, user_id: int = Depends(rate_limited_user("money_write"))):
    """"Link Account (Demo)" — fabricates a new MOCK linked account.

    MOCK DATA — simulated for demo purposes, not a real integration. No
    real bank OAuth/Plaid flow happens here.
    """
    try:
        account = link_demo_account(user_id, payload.bank_name, payload.account_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _serialize_finance_account(account)
