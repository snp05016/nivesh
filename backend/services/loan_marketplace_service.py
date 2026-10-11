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
from typing import Optional, cast

from sqlalchemy.exc import IntegrityError

from database import get_session
from models.db_models import LinkedBankAccount, LoanApplication, LoanDisbursement, LoanOffer
from services.audit_service import audit
from services.credit_bureau_mock_service import get_mock_credit_score
from services.finance_calculators import calculate_apr, calculate_emi
from services.kyc_consent_service import check_kyc_gate
from services.product_bounds import check_product_bounds

# Consent type that MUST be active before a loan application can be
# auto-approved. Kept in sync with kyc_consent_service.CREDIT_CHECK_CONSENT.
REQUIRED_CONSENT_TYPE = "credit_check"

# Demo underwriting thresholds — clearly not a real NBFC risk model.
MIN_SCORE_FOR_AUTO_APPROVAL_BUFFER = 20  # score must clear offer.min_credit_score by this much to auto-approve
AUTO_REJECT_BELOW_SCORE = 500


# ---------------------------------------------------------------------------
# Mock/seed data — ~5 NBFC loan offers spanning personal/home/car/gold loans.
# Clearly marked MOCK DATA; not a real NBFC product catalog integration.
# REG-05: lender names are fictional; never seed a real bank/NBFC brand.
# ---------------------------------------------------------------------------
_MOCK_LOAN_OFFERS = [
    {
        "nbfc_name": "Demo Lender A (fictional)",
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
        "nbfc_name": "Demo Lender B (fictional)",
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
        "nbfc_name": "Demo Lender C (fictional)",
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
        "nbfc_name": "Demo Lender D (fictional)",
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
        "nbfc_name": "Demo Lender E (fictional)",
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


def offer_max_apr(offer: LoanOffer) -> float:
    """APR at the offer's minimum amount and shortest tenure. The fee is a
    fixed share of the amount, so the shortest tenure gives the highest APR."""
    return calculate_apr(
        float(offer.min_amount),  # type: ignore[arg-type]
        float(offer.interest_rate_pct),  # type: ignore[arg-type]
        int(offer.min_tenure_months),  # type: ignore[arg-type]
        float(offer.processing_fee_pct),  # type: ignore[arg-type]
    )


def offer_emi_at_min(offer: LoanOffer) -> float:
    """EMI at the offer's minimum amount and longest tenure (lowest EMI)."""
    return round(
        calculate_emi(
            float(offer.min_amount),  # type: ignore[arg-type]
            float(offer.interest_rate_pct),  # type: ignore[arg-type]
            int(offer.max_tenure_months),  # type: ignore[arg-type]
        ),
        2,
    )


def list_loan_offers(loan_type: Optional[str] = None) -> list[LoanOffer]:
    """List active mock loan offers, optionally filtered by loan_type, ranked
    by max APR ascending (REG-05: the all-in cost, not the headline rate)."""
    with get_session() as session:
        query = session.query(LoanOffer).filter(LoanOffer.is_active.is_(True))
        if loan_type:
            query = query.filter(LoanOffer.loan_type == loan_type)
        return sorted(query.all(), key=lambda o: (offer_max_apr(o), o.id))


def get_loan_offer_by_id(offer_id: int) -> Optional[LoanOffer]:
    with get_session() as session:
        return session.query(LoanOffer).filter(LoanOffer.id == offer_id).first()


def _evaluate_demo_underwriting(score: int, offer: LoanOffer) -> tuple[str, str]:
    """Simplified, clearly-mocked demo underwriting rule — NOT a real NBFC
    credit policy. Returns (status, reason).

    REG-05: the score is a hash of the user id, not a bureau score, so the
    reason text never shows it or presents it as a lender's decision.
    """
    min_score = cast(int, offer.min_credit_score)
    if score < AUTO_REJECT_BELOW_SCORE or score < min_score:
        return "rejected", "MOCK DECISION: demo eligibility check not met. No real credit check was run."
    if score >= min_score + MIN_SCORE_FOR_AUTO_APPROVAL_BUFFER:
        return "approved", "MOCK DECISION: demo eligibility check passed; auto-approved for demo purposes."
    return "under_review", "MOCK DECISION: demo eligibility check needs review; routed to manual review in this demo."


def submit_loan_application(
    user_id: int,
    loan_offer_id: int,
    requested_amount: float,
    requested_tenure_months: int,
    device_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> LoanApplication:
    """Submit a loan application against a mock loan offer.

    idempotency_key (the client's Idempotency-Key header) makes retries
    safe: a repeated key for the same user returns the original application.

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
    # Blank keys mean "no key": storing "" would collide on UNIQUE(user_id, key).
    idempotency_key = (idempotency_key or "").strip() or None
    with get_session() as session:
        if idempotency_key:
            existing = _application_for_key(session, user_id, idempotency_key)
            if existing is not None:
                return existing

        offer = session.query(LoanOffer).filter(LoanOffer.id == loan_offer_id).first()
        if offer is None:
            raise ValueError(f"Loan offer {loan_offer_id} not found")
        check_product_bounds(offer, requested_amount, requested_tenure_months, "loan offer")

        score = get_mock_credit_score(user_id)
        status, reason = _evaluate_demo_underwriting(score, offer)

        if status == "approved":
            kyc_ok, kyc_reason = check_kyc_gate(user_id, device_id, REQUIRED_CONSENT_TYPE, "application")
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
            idempotency_key=idempotency_key,
        )
        session.add(application)
        try:
            session.flush()  # assign application.id for the audit row
            audit(session, user_id, "loan_application_submitted", {
                "application_id": application.id, "loan_offer_id": loan_offer_id,
                "requested_amount": requested_amount, "requested_tenure_months": requested_tenure_months,
                "status": status, "decision_reason": reason,
            })
            session.commit()
        except IntegrityError:
            # A concurrent request with the same key won the insert.
            session.rollback()
            existing = _application_for_key(session, user_id, idempotency_key) if idempotency_key else None
            if existing is None:
                raise
            return existing
        session.refresh(application)
        return application


def _application_for_key(session, user_id: int, idempotency_key: str) -> Optional[LoanApplication]:
    return (
        session.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id, LoanApplication.idempotency_key == idempotency_key)
        .first()
    )


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
        try:
            session.flush()  # assign account.id for the audit row
            audit(session, user_id, "bank_account_linked", {
                "account_id": account.id, "bank_name": bank_name,
                "masked_account_number": masked_account_number, "is_primary": account.is_primary,
            })
            session.commit()
        except IntegrityError:
            # unique (user_id, masked_account_number): same mask already linked.
            session.rollback()
            raise ValueError("This masked account number is already linked")
        session.refresh(account)
        return account


class BankAccountNotFound(ValueError):
    """The linked bank account does not exist or belongs to another user."""


class BankAccountInUse(ValueError):
    """A loan disbursement points at this account, so it cannot be unlinked."""


def _owned_account(session, user_id: int, account_id: int) -> LinkedBankAccount:
    account = (
        session.query(LinkedBankAccount)
        .filter(LinkedBankAccount.id == account_id, LinkedBankAccount.user_id == user_id)
        .first()
    )
    if account is None:
        raise BankAccountNotFound(f"Linked bank account {account_id} not found")
    return account


def unlink_bank_account(user_id: int, account_id: int) -> None:
    """Remove one of the caller's MOCK linked bank accounts. If it was the
    primary, the most recently linked remaining account becomes primary, so
    disbursement keeps a destination. Accounts a disbursement already paid
    into stay (BankAccountInUse): the disbursement row references them.
    """
    with get_session() as session:
        account = _owned_account(session, user_id, account_id)
        in_use = (
            session.query(LoanDisbursement.id)
            .filter(LoanDisbursement.linked_bank_account_id == account_id)
            .first()
        )
        if in_use is not None:
            raise BankAccountInUse("This bank account has received a loan disbursement and cannot be unlinked")
        was_primary = bool(account.is_primary)
        session.delete(account)
        promoted = None
        if was_primary:
            promoted = (
                session.query(LinkedBankAccount)
                .filter(LinkedBankAccount.user_id == user_id, LinkedBankAccount.id != account_id)
                .order_by(LinkedBankAccount.linked_at.desc(), LinkedBankAccount.id.desc())
                .first()
            )
            if promoted is not None:
                promoted.is_primary = True  # type: ignore[assignment]
        audit(session, user_id, "bank_account_unlinked", {
            "account_id": account_id, "was_primary": was_primary,
            "promoted_id": promoted.id if promoted is not None else None,
        })
        session.commit()


def set_primary_bank_account(user_id: int, account_id: int) -> LinkedBankAccount:
    """Make one of the caller's MOCK linked bank accounts the only primary."""
    with get_session() as session:
        account = _owned_account(session, user_id, account_id)
        previous = (
            session.query(LinkedBankAccount.id)
            .filter(LinkedBankAccount.user_id == user_id, LinkedBankAccount.is_primary.is_(True))
            .first()
        )
        session.query(LinkedBankAccount).filter(
            LinkedBankAccount.user_id == user_id, LinkedBankAccount.id != account_id
        ).update({LinkedBankAccount.is_primary: False}, synchronize_session=False)
        account.is_primary = True  # type: ignore[assignment]
        audit(session, user_id, "bank_account_primary_changed", {
            "from_id": previous.id if previous is not None else None, "to_id": account_id,
        })
        session.commit()
        session.refresh(account)
        return account


# ---------------------------------------------------------------------------
# Loan disbursement — MOCK DATA, simulated for demo purposes, not a real
# integration. No real fund transfer, NBFC-to-bank settlement rail, or
# payment gateway is involved. Models the real-world requirement that a
# lender cannot disburse funds without a destination account: fails closed
# (DisbursementRejected, nothing persisted) rather than silently no-op'ing
# when the borrower has no primary LinkedBankAccount on file.
# ---------------------------------------------------------------------------

class DisbursementNotFound(ValueError):
    """The loan application does not exist or belongs to another user."""


class DisbursementRejected(ValueError):
    """A business rule blocks disbursement (not approved, already disbursed,
    no primary bank account)."""


def disburse_loan(application_id: int, user_id: int) -> LoanDisbursement:
    """Disburse an approved LoanApplication as a MOCK instant settlement.

    Preconditions enforced (fail closed, not a silent no-op):
      - The LoanApplication must exist and belong to user_id
        (else DisbursementNotFound).
      - The LoanApplication.status must be "approved" (already-disbursed or
        not-yet-approved applications raise DisbursementRejected).
      - The borrower must have at least one LinkedBankAccount (the loan
        marketplace one — NOT FinanceTrackerAccount) with is_primary=True;
        if none exists, DisbursementRejected is raised and no row is written,
        so retries cannot pile up failed rows.

    On success, the LoanApplication.status is advanced to "disbursed" by an
    atomic approved->disbursed UPDATE, so concurrent calls cannot both record
    a completed disbursement (the partial unique index
    uq_loan_disbursement_completed_per_app is the database backstop).
    """
    with get_session() as session:
        application = (
            session.query(LoanApplication)
            .filter(LoanApplication.id == application_id, LoanApplication.user_id == user_id)
            .first()
        )
        if application is None:
            raise DisbursementNotFound(f"Loan application {application_id} not found")
        if application.status == "disbursed":
            raise DisbursementRejected(f"Loan application {application_id} has already been disbursed")
        if application.status != "approved":
            raise DisbursementRejected(
                f"Loan application {application_id} is not approved (status={application.status}); "
                "cannot disburse"
            )

        offer = session.query(LoanOffer).filter(LoanOffer.id == application.loan_offer_id).first()
        nbfc_name = offer.nbfc_name if offer is not None else "Unknown NBFC (mock)"
        # Disbursed net of the processing fee, as the KFS discloses (net_disbursed_amount).
        fee_pct = float(offer.processing_fee_pct or 0) if offer is not None else 0.0  # type: ignore[arg-type]

        primary_account = (
            session.query(LinkedBankAccount)
            .filter(LinkedBankAccount.user_id == user_id, LinkedBankAccount.is_primary.is_(True))
            .first()
        )

        if primary_account is None:
            raise DisbursementRejected("Link a bank account and mark it primary before requesting disbursement.")

        already_disbursed = f"Loan application {application_id} has already been disbursed"
        claimed = (
            session.query(LoanApplication)
            .filter(
                LoanApplication.id == application_id,
                LoanApplication.user_id == user_id,
                LoanApplication.status == "approved",
            )
            .update({"status": "disbursed"}, synchronize_session=False)
        )
        if claimed != 1:
            session.rollback()
            raise DisbursementRejected(already_disbursed)

        disbursement = LoanDisbursement(
            loan_application_id=application.id,
            user_id=user_id,
            linked_bank_account_id=primary_account.id,
            nbfc_name=nbfc_name,
            disbursed_amount=round(float(application.requested_amount) * (1 - fee_pct / 100), 2),  # type: ignore[arg-type]
            status="completed",
            failure_reason=None,
            disbursed_at=datetime.now(timezone.utc),
        )
        session.add(disbursement)
        try:
            session.flush()  # assign disbursement.id for the audit row
            audit(session, user_id, "loan_disbursement_completed", {
                "application_id": application.id, "disbursement_id": disbursement.id,
                "amount": application.requested_amount, "linked_bank_account_id": primary_account.id,
                "previous_status": "approved",
            })
            session.commit()
        except IntegrityError:
            session.rollback()
            raise DisbursementRejected(already_disbursed)
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
