"""Fixed Deposit Marketplace service — business logic + repository access
for MOCK bank/NBFC fixed-deposit schemes and bookings
(Controller-Service-Repository).

routers/fixed_deposits.py must only validate HTTP input and call functions
here. All session.query() calls for FixedDepositScheme / FixedDepositBooking
live in this module.

MOCK DATA — simulated for demo purposes, not a real integration. No real
bank/NBFC FD issuer rate-card feed is called; schemes below are hand-seeded
demo data. Bookings settle instantly in-process — no real UPI/net-banking
payment gateway is called anywhere in this module.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from database import get_session
from models.db_models import FixedDepositBooking, FixedDepositScheme
from services.kyc_consent_service import get_active_consents, verify_device_binding
from services.product_bounds import check_product_bounds

# Consent type that MUST be active before an FD booking can be confirmed.
# FDs reuse the same KYC consent ledger as the loan marketplace but require
# a "sim_binding" consent instead of "credit_check" — see
# services/kyc_consent_service.py (KYCConsent.consent_type docstring lists
# "sim_binding" as an example type).
REQUIRED_CONSENT_TYPE = "sim_binding"

# Quarterly compounding periods per year — standard Indian FD convention.
COMPOUNDING_PERIODS_PER_YEAR = 4


# ---------------------------------------------------------------------------
# Mock/seed data — ~7 bank/NBFC FD schemes spanning short/medium/long
# tenures and a few mock issuer names. Clearly marked MOCK DATA; not a real
# bank/NBFC product catalog integration.
# ---------------------------------------------------------------------------
_MOCK_FD_SCHEMES = [
    {
        "issuer_name": "HDFC Bank (mock)",
        "min_tenure_months": 6,
        "max_tenure_months": 12,
        "min_amount": 5_000,
        "max_amount": 2_00_00_000,
        "interest_rate_pct": 6.60,
        "senior_citizen_bonus_pct": 0.50,
    },
    {
        "issuer_name": "HDFC Bank (mock)",
        "min_tenure_months": 13,
        "max_tenure_months": 24,
        "min_amount": 5_000,
        "max_amount": 2_00_00_000,
        "interest_rate_pct": 7.10,
        "senior_citizen_bonus_pct": 0.50,
    },
    {
        "issuer_name": "SBI (mock)",
        "min_tenure_months": 12,
        "max_tenure_months": 36,
        "min_amount": 1_000,
        "max_amount": 1_00_00_000,
        "interest_rate_pct": 6.80,
        "senior_citizen_bonus_pct": 0.50,
    },
    {
        "issuer_name": "SBI (mock)",
        "min_tenure_months": 37,
        "max_tenure_months": 120,
        "min_amount": 1_000,
        "max_amount": 1_00_00_000,
        "interest_rate_pct": 7.00,
        "senior_citizen_bonus_pct": 0.60,
    },
    {
        "issuer_name": "Bajaj Finance (mock)",
        "min_tenure_months": 12,
        "max_tenure_months": 60,
        "min_amount": 15_000,
        "max_amount": 5_00_00_000,
        "interest_rate_pct": 8.10,
        "senior_citizen_bonus_pct": 0.35,
    },
    {
        "issuer_name": "ICICI Bank (mock)",
        "min_tenure_months": 6,
        "max_tenure_months": 24,
        "min_amount": 10_000,
        "max_amount": 2_00_00_000,
        "interest_rate_pct": 6.90,
        "senior_citizen_bonus_pct": 0.50,
    },
    {
        "issuer_name": "Shriram Finance (mock)",
        "min_tenure_months": 12,
        "max_tenure_months": 60,
        "min_amount": 5_000,
        "max_amount": 1_00_00_000,
        "interest_rate_pct": 8.40,
        "senior_citizen_bonus_pct": 0.40,
    },
    {
        "issuer_name": "PNB Housing Finance (mock)",
        "min_tenure_months": 24,
        "max_tenure_months": 120,
        "min_amount": 10_000,
        "max_amount": 3_00_00_000,
        "interest_rate_pct": 7.65,
        "senior_citizen_bonus_pct": 0.30,
    },
]


def seed_mock_fd_schemes_if_empty() -> int:
    """Populate fixed_deposit_schemes with ~8 mock bank/NBFC products when
    the table is empty.

    MOCK DATA — for development/demo only. Returns number of schemes inserted.
    """
    with get_session() as session:
        existing = session.query(FixedDepositScheme).count()
        if existing > 0:
            return 0

        for row in _MOCK_FD_SCHEMES:
            session.add(FixedDepositScheme(**row, is_active=True))
        session.commit()
        return len(_MOCK_FD_SCHEMES)


def list_fd_schemes(
    min_tenure: Optional[int] = None,
    max_tenure: Optional[int] = None,
) -> list[FixedDepositScheme]:
    """List active mock FD schemes for discovery/comparison, optionally
    filtered so only schemes whose tenure range overlaps
    [min_tenure, max_tenure] are returned. Client sorts/filters further.
    """
    with get_session() as session:
        query = session.query(FixedDepositScheme).filter(FixedDepositScheme.is_active.is_(True))
        if min_tenure is not None:
            query = query.filter(FixedDepositScheme.max_tenure_months >= min_tenure)
        if max_tenure is not None:
            query = query.filter(FixedDepositScheme.min_tenure_months <= max_tenure)
        return query.order_by(FixedDepositScheme.interest_rate_pct.desc()).all()


def get_fd_scheme_by_id(scheme_id: int) -> Optional[FixedDepositScheme]:
    with get_session() as session:
        return session.query(FixedDepositScheme).filter(FixedDepositScheme.id == scheme_id).first()


def calculate_fd_maturity(
    principal: float,
    tenure_months: int,
    interest_rate_pct: float,
) -> dict:
    """Compute FD maturity value using compound interest with quarterly
    compounding — the standard Indian FD convention:

        A = P * (1 + r / (4 * 100)) ^ (4 * tenure_years)

    where r is interest_rate_pct (annual, in percent) and tenure_years is
    tenure_months / 12.

    This is the pure calculation function backing both the FD calculator
    endpoint and book_fixed_deposit()'s maturity_amount at booking time.

    Args:
        principal: FD principal amount, in INR.
        tenure_months: FD tenure in months.
        interest_rate_pct: Annual nominal interest rate, in percent
            (e.g. 7.25 for 7.25% p.a.).

    Returns:
        dict with maturity_amount and interest_earned, both rounded to 2dp.
    """
    if principal < 0:
        raise ValueError("principal must be non-negative")
    if tenure_months <= 0:
        raise ValueError("tenure_months must be a positive integer")
    if interest_rate_pct < 0:
        raise ValueError("interest_rate_pct must be non-negative")

    tenure_years = tenure_months / 12.0
    n = COMPOUNDING_PERIODS_PER_YEAR
    r = interest_rate_pct / 100.0

    maturity_amount = principal * (1.0 + r / n) ** (n * tenure_years)
    interest_earned = maturity_amount - principal

    return {
        "maturity_amount": round(maturity_amount, 2),
        "interest_earned": round(interest_earned, 2),
    }


def _check_kyc_gate(user_id: int, device_id: Optional[str]) -> tuple[bool, str]:
    """Enforce the MOCK KYC/Security gate for FD bookings, mirroring the
    pattern in services/loan_marketplace_service.py:_check_kyc_gate() but
    using the "sim_binding" consent type instead of "credit_check":

        A fixed-deposit booking MUST NOT be confirmed unless BOTH hold:
          1. an active (granted, not revoked) "sim_binding" consent exists, AND
          2. verify_device_binding(user_id, device_id)["verified"] is True.

    Fails closed — returns (False, reason) if either check fails.

    Returns (passed, reason). MOCK DATA — device_id/consent checks are
    simulated for demo purposes, not a real KYC/SIM-binding integration.
    """
    active_consents = get_active_consents(user_id)
    has_consent = any(c["consent_type"] == REQUIRED_CONSENT_TYPE for c in active_consents)
    if not has_consent:
        return False, "no active 'sim_binding' KYC consent on file for this user (mock KYC gate)"

    if not device_id:
        return False, "no device_id supplied with booking; device binding could not be verified (mock KYC gate)"

    binding_result = verify_device_binding(user_id, device_id)
    if not binding_result["verified"]:
        return False, f"device binding check failed: {binding_result['reason']} (mock KYC gate)"

    return True, "KYC consent + device binding verified (mock KYC gate)"


def book_fixed_deposit(
    user_id: int,
    scheme_id: int,
    principal_amount: float,
    tenure_months: int,
    payment_method: str,
    device_id: Optional[str] = None,
) -> FixedDepositBooking:
    """Book a MOCK fixed deposit against an FD scheme with mock instant
    settlement.

    MOCK DATA — simulated for demo purposes, not a real integration. No
    real UPI/net-banking payment gateway is called; a "confirmed" booking
    here does not move any real money.

    SECURITY/KYC GATE (mirrors services/loan_marketplace_service.py's
    invariant): a booking is never allowed to reach "confirmed" unless the
    booker has an active "sim_binding" consent AND a verified device
    binding ("One-time SIM binding" + "KYC completion"). If either check
    fails, the booking is recorded with status="failed" and a
    decision_reason explaining which KYC step is missing — it fails closed,
    it is never silently confirmed.
    """
    with get_session() as session:
        scheme = session.query(FixedDepositScheme).filter(FixedDepositScheme.id == scheme_id).first()
        if scheme is None:
            raise ValueError(f"Fixed deposit scheme {scheme_id} not found")
        # Also caps tenure, so the matures_at timedelta below cannot overflow.
        check_product_bounds(scheme, principal_amount, tenure_months, "FD scheme")

        kyc_ok, kyc_reason = _check_kyc_gate(user_id, device_id)

        if kyc_ok:
            status = "confirmed"
            decision_reason = f"MOCK DECISION: booking confirmed — {kyc_reason}"
        else:
            status = "failed"
            decision_reason = f"MOCK DECISION: booking failed — KYC gate failed: {kyc_reason}"

        maturity = calculate_fd_maturity(
            principal=principal_amount,
            tenure_months=tenure_months,
            interest_rate_pct=float(scheme.interest_rate_pct),
        )

        booked_at = datetime.now(timezone.utc)
        matures_at = booked_at + timedelta(days=int(tenure_months * 30.44))

        booking = FixedDepositBooking(
            user_id=user_id,
            scheme_id=scheme_id,
            principal_amount=principal_amount,
            tenure_months=tenure_months,
            interest_rate_pct=scheme.interest_rate_pct,
            maturity_amount=maturity["maturity_amount"],
            payment_method=payment_method,
            status=status,
            decision_reason=decision_reason,
            booked_at=booked_at,
            matures_at=matures_at,
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return booking


def list_bookings_for_user(user_id: int) -> list[FixedDepositBooking]:
    with get_session() as session:
        return (
            session.query(FixedDepositBooking)
            .filter(FixedDepositBooking.user_id == user_id)
            .order_by(FixedDepositBooking.booked_at.desc())
            .all()
        )
