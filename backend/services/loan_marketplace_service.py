"""Loan Marketplace service — business logic + repository access for MOCK
NBFC loan offers and loan applications (Controller-Service-Repository).

routers/finance.py must only validate HTTP input and call functions here.
All session.query() calls for LinkedBankAccount / LoanOffer / LoanApplication
live in this module.

MOCK DATA — simulated for demo purposes, not a real integration. No real
NBFC rate-card feed or underwriting engine is called; loan offers below are
hand-seeded demo data, and the approval rule is a simplified stand-in for
real underwriting.
"""
from datetime import datetime, timezone
from typing import Optional

from database import get_session
from models.db_models import LinkedBankAccount, LoanApplication, LoanDisbursement, LoanOffer
from services.credit_bureau_mock_service import get_mock_credit_score
from services.kyc_consent_service import get_active_consents, verify_device_binding

# Consent type that MUST be active before a loan application can be
# auto-approved. Kept in sync with kyc_consent_service.CREDIT_CHECK_CONSENT.
REQUIRED_CONSENT_TYPE = "credit_check"

# Demo underwriting thresholds — clearly not a real NBFC risk model.
MIN_SCORE_FOR_AUTO_APPROVAL_BUFFER = 20  # score must clear offer.min_credit_score by this much to auto-approve
AUTO_REJECT_BELOW_SCORE = 500


# ---------------------------------------------------------------------------
# Mock/seed data — ~5 NBFC loan offers spanning personal/home/car/gold loans.
# Clearly marked MOCK DATA; not a real NBFC product catalog integration.
# ---------------------------------------------------------------------------
_MOCK_LOAN_OFFERS = [
    {
        "nbfc_name": "Bajaj Finserv (mock)",
        "loan_type": "personal",
        "min_amount": 50_000,
        "max_amount": 25_00_000,
        "interest_rate_pct": 11.50,
        "min_tenure_months": 12,
        "max_tenure_months": 60,
        "min_credit_score": 700,
        "processing_fee_pct": 2.5,
    },
    {
        "nbfc_name": "HDB Financial Services (mock)",
        "loan_type": "personal",
        "min_amount": 25_000,
        "max_amount": 15_00_000,
        "interest_rate_pct": 13.75,
        "min_tenure_months": 6,
        "max_tenure_months": 48,
        "min_credit_score": 650,
        "processing_fee_pct": 3.0,
    },
    {
        "nbfc_name": "LIC Housing Finance (mock)",
        "loan_type": "home",
        "min_amount": 5_00_000,
        "max_amount": 5_00_00_000,
        "interest_rate_pct": 8.75,
        "min_tenure_months": 60,
        "max_tenure_months": 240,
        "min_credit_score": 700,
        "processing_fee_pct": 0.5,
    },
    {
        "nbfc_name": "Tata Capital (mock)",
        "loan_type": "car",
        "min_amount": 1_00_000,
        "max_amount": 50_00_000,
        "interest_rate_pct": 9.25,
        "min_tenure_months": 12,
        "max_tenure_months": 84,
        "min_credit_score": 675,
        "processing_fee_pct": 1.0,
    },
    {
        "nbfc_name": "Muthoot Finance (mock)",
        "loan_type": "gold",
        "min_amount": 10_000,
        "max_amount": 20_00_000,
        "interest_rate_pct": 10.50,
        "min_tenure_months": 3,
        "max_tenure_months": 36,
        "min_credit_score": 550,
        "processing_fee_pct": 1.5,
    },
]


def seed_mock_loan_offers_if_empty() -> int:
    """Populate loan_offers with ~5 mock NBFC products when the table is empty.

    MOCK DATA — for development/demo only. Returns number of offers inserted.
    """
    with get_session() as session:
        existing = session.query(LoanOffer).count()
        if existing > 0:
            return 0

        for row in _MOCK_LOAN_OFFERS:
            session.add(LoanOffer(**row, is_active=True))
        session.commit()
        return len(_MOCK_LOAN_OFFERS)


def list_loan_offers(loan_type: Optional[str] = None) -> list[LoanOffer]:
    """List active mock loan offers, optionally filtered by loan_type."""
    with get_session() as session:
        query = session.query(LoanOffer).filter(LoanOffer.is_active.is_(True))
        if loan_type:
            query = query.filter(LoanOffer.loan_type == loan_type)
        return query.order_by(LoanOffer.interest_rate_pct.asc()).all()


def get_loan_offer_by_id(offer_id: int) -> Optional[LoanOffer]:
    with get_session() as session:
        return session.query(LoanOffer).filter(LoanOffer.id == offer_id).first()


def _evaluate_demo_underwriting(score: int, offer: LoanOffer) -> tuple[str, str]:
    """Simplified, clearly-mocked demo underwriting rule — NOT a real NBFC
    credit policy. Returns (status, reason).
    """
    if score < AUTO_REJECT_BELOW_SCORE:
        return "rejected", f"MOCK DECISION: credit score {score} is below the platform-wide minimum of {AUTO_REJECT_BELOW_SCORE}."
    if score < offer.min_credit_score:
        return "rejected", (
            f"MOCK DECISION: credit score {score} is below {offer.nbfc_name}'s minimum "
            f"requirement of {offer.min_credit_score} for this product."
        )
    if score >= offer.min_credit_score + MIN_SCORE_FOR_AUTO_APPROVAL_BUFFER:
        return "approved", (
            f"MOCK DECISION: credit score {score} comfortably clears {offer.nbfc_name}'s "
            f"minimum of {offer.min_credit_score}; auto-approved for demo purposes."
        )
    return "under_review", (
        f"MOCK DECISION: credit score {score} is close to {offer.nbfc_name}'s minimum of "
        f"{offer.min_credit_score}; routed to manual review in this demo."
    )


def _check_kyc_gate(user_id: int, device_id: Optional[str]) -> tuple[bool, str]:
    """Enforce the KYC/Security invariant documented in kyc_consent_service.py:

        A loan application MUST NOT be approved unless BOTH hold:
          1. an active (granted, not revoked) "credit_check" consent exists, AND
          2. verify_device_binding(user_id, device_id)["verified"] is True.

    Returns (passed, reason). MOCK DATA — device_id/consent checks are
    simulated for demo purposes, not a real KYC/SIM-binding integration.
    """
    active_consents = get_active_consents(user_id)
    has_consent = any(c["consent_type"] == REQUIRED_CONSENT_TYPE for c in active_consents)
    if not has_consent:
        return False, "no active 'credit_check' KYC consent on file for this user (mock KYC gate)"

    if not device_id:
        return False, "no device_id supplied with application; device binding could not be verified (mock KYC gate)"

    binding_result = verify_device_binding(user_id, device_id)
    if not binding_result["verified"]:
        return False, f"device binding check failed: {binding_result['reason']} (mock KYC gate)"

    return True, "KYC consent + device binding verified (mock KYC gate)"


def submit_loan_application(
    user_id: int,
    loan_offer_id: int,
    requested_amount: float,
    requested_tenure_months: int,
    device_id: Optional[str] = None,
) -> LoanApplication:
    """Submit a loan application against a mock loan offer.

    Looks up the user's MOCK credit score (credit_bureau_mock_service) and
    applies a simple deterministic demo underwriting rule to auto-approve,
    auto-reject, or route to manual review. NOT a real NBFC underwriting
    decision — for demo purposes only.

    SECURITY/KYC GATE (see services/kyc_consent_service.py INVARIANT): an
    application is never allowed to reach "approved" unless the applicant
    has an active "credit_check" consent AND a verified device binding.
    If either check fails, the application is force-rejected regardless of
    what the demo underwriting rule would otherwise decide — it is never
    silently auto-approved.
    """
    with get_session() as session:
        offer = session.query(LoanOffer).filter(LoanOffer.id == loan_offer_id).first()
        if offer is None:
            raise ValueError(f"Loan offer {loan_offer_id} not found")

        score = get_mock_credit_score(user_id)
        status, reason = _evaluate_demo_underwriting(score, offer)

        if status == "approved":
            kyc_ok, kyc_reason = _check_kyc_gate(user_id, device_id)
            if not kyc_ok:
                status = "rejected"
                reason = f"MOCK DECISION: application rejected — KYC gate failed: {kyc_reason}"

        application = LoanApplication(
            user_id=user_id,
            loan_offer_id=loan_offer_id,
            requested_amount=requested_amount,
            requested_tenure_months=requested_tenure_months,
            status=status,
            mock_credit_score_at_application=score,
            decision_reason=reason,
            decided_at=datetime.now(timezone.utc) if status != "under_review" else None,
        )
        session.add(application)
        session.commit()
        session.refresh(application)
        return application


def list_applications_for_user(user_id: int) -> list[LoanApplication]:
    with get_session() as session:
        return (
            session.query(LoanApplication)
            .filter(LoanApplication.user_id == user_id)
            .order_by(LoanApplication.submitted_at.desc())
            .all()
        )


def get_application_by_id(application_id: int, user_id: int) -> Optional[LoanApplication]:
    with get_session() as session:
        return (
            session.query(LoanApplication)
            .filter(LoanApplication.id == application_id, LoanApplication.user_id == user_id)
            .first()
        )


# ---------------------------------------------------------------------------
# Linked bank accounts — MOCK DATA, user-supplied labels only, no real
# account-aggregator integration.
# ---------------------------------------------------------------------------

def list_linked_bank_accounts(user_id: int) -> list[LinkedBankAccount]:
    with get_session() as session:
        return (
            session.query(LinkedBankAccount)
            .filter(LinkedBankAccount.user_id == user_id)
            .order_by(LinkedBankAccount.linked_at.desc())
            .all()
        )


def link_bank_account(
    user_id: int,
    bank_name: str,
    masked_account_number: str,
    account_type: str = "savings",
    ifsc_code: Optional[str] = None,
) -> LinkedBankAccount:
    """Register a MOCK linked bank account. masked_account_number must already
    be masked by the caller (e.g. "XXXX1234") — this is a demo label, not a
    real account-aggregator/bank integration and never stores full account numbers.
    """
    with get_session() as session:
        has_existing = (
            session.query(LinkedBankAccount).filter(LinkedBankAccount.user_id == user_id).count() > 0
        )
        account = LinkedBankAccount(
            user_id=user_id,
            bank_name=bank_name,
            account_type=account_type,
            masked_account_number=masked_account_number,
            ifsc_code=ifsc_code,
            is_primary=not has_existing,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        return account


# ---------------------------------------------------------------------------
# Loan disbursement — MOCK DATA, simulated for demo purposes, not a real
# integration. No real fund transfer, NBFC-to-bank settlement rail, or
# payment gateway is involved. Models the real-world requirement that a
# lender cannot disburse funds without a destination account: fails closed
# (status="failed" + failure_reason) rather than silently no-op'ing when the
# borrower has no primary LinkedBankAccount on file.
# ---------------------------------------------------------------------------

def disburse_loan(application_id: int, user_id: int) -> LoanDisbursement:
    """Disburse an approved LoanApplication as a MOCK instant settlement.

    Preconditions enforced (fail closed, not a silent no-op):
      - The LoanApplication must exist and belong to user_id.
      - The LoanApplication.status must be "approved" (already-disbursed or
        not-yet-approved applications are rejected with a ValueError).
      - The borrower must have at least one LinkedBankAccount (the loan
        marketplace one — NOT FinanceTrackerAccount) with is_primary=True;
        if none exists, a LoanDisbursement row is still created, but with
        status="failed" and a failure_reason explaining that a bank account
        must be linked first.

    On success, the LoanApplication.status is advanced to "disbursed".
    """
    with get_session() as session:
        application = (
            session.query(LoanApplication)
            .filter(LoanApplication.id == application_id, LoanApplication.user_id == user_id)
            .first()
        )
        if application is None:
            raise ValueError(f"Loan application {application_id} not found")
        if application.status == "disbursed":
            raise ValueError(f"Loan application {application_id} has already been disbursed")
        if application.status != "approved":
            raise ValueError(
                f"Loan application {application_id} is not approved (status={application.status}); "
                "cannot disburse"
            )

        offer = session.query(LoanOffer).filter(LoanOffer.id == application.loan_offer_id).first()
        nbfc_name = offer.nbfc_name if offer is not None else "Unknown NBFC (mock)"

        primary_account = (
            session.query(LinkedBankAccount)
            .filter(LinkedBankAccount.user_id == user_id, LinkedBankAccount.is_primary.is_(True))
            .first()
        )

        if primary_account is None:
            disbursement = LoanDisbursement(
                loan_application_id=application.id,
                user_id=user_id,
                linked_bank_account_id=None,
                nbfc_name=nbfc_name,
                disbursed_amount=application.requested_amount,
                status="failed",
                failure_reason=(
                    "MOCK DECISION: no primary linked bank account on file for this user — "
                    "a bank account must be linked (and marked primary) via "
                    "POST /linked-bank-accounts before funds can be disbursed."
                ),
                disbursed_at=datetime.now(timezone.utc),
            )
            session.add(disbursement)
            session.commit()
            session.refresh(disbursement)
            return disbursement

        disbursement = LoanDisbursement(
            loan_application_id=application.id,
            user_id=user_id,
            linked_bank_account_id=primary_account.id,
            nbfc_name=nbfc_name,
            disbursed_amount=application.requested_amount,
            status="completed",
            failure_reason=None,
            disbursed_at=datetime.now(timezone.utc),
        )
        session.add(disbursement)
        application.status = "disbursed"
        session.commit()
        session.refresh(disbursement)
        return disbursement


def get_disbursement_for_application(application_id: int, user_id: int) -> Optional[LoanDisbursement]:
    """Return the most recent LoanDisbursement for a given application (if any),
    scoped to user_id so a caller cannot fetch another user's disbursement."""
    with get_session() as session:
        return (
            session.query(LoanDisbursement)
            .filter(
                LoanDisbursement.loan_application_id == application_id,
                LoanDisbursement.user_id == user_id,
            )
            .order_by(LoanDisbursement.disbursed_at.desc())
            .first()
        )
