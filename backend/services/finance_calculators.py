"""
Pure-Python personal finance calculators: EMI, Gratuity, and Income Tax
(new and old regime, FY2024-25 India).

IMPORTANT: These are pure, deterministic functions with NO side effects.
No DB session, no I/O, no network access, no yfinance/LLM calls. They operate
strictly on numeric inputs supplied by the caller so that other services
(e.g. routers or higher-level services) can import and call them directly
without incurring any DB/network dependency.

All monetary figures are plain floats denominated in Indian Rupees (INR).
Callers are responsible for presenting these using Lakhs/Crores formatting
in any user-facing surface.
"""

from __future__ import annotations

from typing import List, TypedDict


class EMIResult(TypedDict):
    emi_amount: float
    total_interest: float
    total_payment: float


class GratuityResult(TypedDict):
    gratuity_amount: float
    is_eligible: bool


class SlabApplied(TypedDict):
    slab_label: str
    rate_pct: float
    taxable_amount_in_slab: float
    tax_in_slab: float


class NewRegimeTaxResult(TypedDict):
    tax_amount: float
    slabs_applied: List[SlabApplied]
    effective_rate_pct: float


class OldRegimeTaxResult(TypedDict):
    tax_amount: float
    taxable_income: float
    effective_rate_pct: float


# Statutory ceiling on gratuity payable under Section 4(3) of the Payment of
# Gratuity Act, 1972 (as amended).
GRATUITY_STATUTORY_CAP = 2_000_000.0  # ₹20,00,000

# Standard deduction available under the old regime (Section 16(ia)).
OLD_REGIME_STANDARD_DEDUCTION = 50_000.0


def calculate_emi(
    principal: float,
    annual_interest_rate_pct: float,
    tenure_months: int,
) -> EMIResult:
    """
    Calculate EMI (Equated Monthly Installment) using the standard
    reducing-balance loan amortization formula:

        r = (annual_interest_rate_pct / 100) / 12   # monthly interest rate
        n = tenure_months
        EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)

    If annual_interest_rate_pct is 0, the loan is amortized in equal
    installments with no interest: EMI = P / n.

    Args:
        principal: Loan principal amount (P), in INR.
        annual_interest_rate_pct: Annual nominal interest rate, in percent
            (e.g. 9.5 for 9.5% p.a.).
        tenure_months: Loan tenure in months (n).

    Returns:
        EMIResult with emi_amount, total_interest, and total_payment.
    """
    if principal < 0:
        raise ValueError("principal must be non-negative")
    if tenure_months <= 0:
        raise ValueError("tenure_months must be a positive integer")
    if annual_interest_rate_pct < 0:
        raise ValueError("annual_interest_rate_pct must be non-negative")

    n = tenure_months

    if annual_interest_rate_pct == 0:
        emi_amount = principal / n
    else:
        r = (annual_interest_rate_pct / 100.0) / 12.0
        factor = (1.0 + r) ** n
        emi_amount = principal * r * factor / (factor - 1.0)

    total_payment = emi_amount * n
    total_interest = total_payment - principal

    return EMIResult(
        emi_amount=round(emi_amount, 2),
        total_interest=round(total_interest, 2),
        total_payment=round(total_payment, 2),
    )


def calculate_gratuity(
    last_drawn_salary: float,
    years_of_service: float,
) -> GratuityResult:
    """
    Calculate gratuity payable under the Payment of Gratuity Act, 1972
    (Section 4(2)), applicable to employees covered under the Act:

        Gratuity = (15 / 26) * last_drawn_salary * years_of_service

    where last_drawn_salary is the last drawn basic salary + dearness
    allowance, and 26 represents the number of working days in a month.

    An employee becomes eligible only after completing at least 5 years of
    continuous service (Section 4(1)). The payable amount is capped at the
    statutory ceiling of ₹20,00,000 (Section 4(3)).

    Args:
        last_drawn_salary: Last drawn monthly salary (basic + DA), in INR.
        years_of_service: Total completed years of continuous service.

    Returns:
        GratuityResult with gratuity_amount (0 if ineligible) and
        is_eligible.
    """
    if last_drawn_salary < 0:
        raise ValueError("last_drawn_salary must be non-negative")
    if years_of_service < 0:
        raise ValueError("years_of_service must be non-negative")

    is_eligible = years_of_service >= 5

    if not is_eligible:
        return GratuityResult(gratuity_amount=0.0, is_eligible=False)

    gratuity_amount = (15.0 / 26.0) * last_drawn_salary * years_of_service
    gratuity_amount = min(gratuity_amount, GRATUITY_STATUTORY_CAP)

    return GratuityResult(
        gratuity_amount=round(gratuity_amount, 2),
        is_eligible=True,
    )


# FY2024-25 New Tax Regime slabs (Finance Act 2023, effective default regime
# from AY 2024-25 onward). Each tuple is (lower_bound, upper_bound, rate_pct).
# upper_bound of None means "and above".
_NEW_REGIME_SLABS = [
    (0.0, 300_000.0, 0.0, "₹0 - ₹3,00,000"),
    (300_000.0, 700_000.0, 5.0, "₹3,00,000 - ₹7,00,000"),
    (700_000.0, 1_000_000.0, 10.0, "₹7,00,000 - ₹10,00,000"),
    (1_000_000.0, 1_200_000.0, 15.0, "₹10,00,000 - ₹12,00,000"),
    (1_200_000.0, 1_500_000.0, 20.0, "₹12,00,000 - ₹15,00,000"),
    (1_500_000.0, None, 30.0, "Above ₹15,00,000"),
]

# Section 87A rebate threshold and cap under the new regime: full rebate
# (tax reduced to zero) if total income does not exceed ₹7,00,000.
NEW_REGIME_REBATE_INCOME_LIMIT = 700_000.0


def calculate_income_tax_new_regime(annual_income: float) -> NewRegimeTaxResult:
    """
    Calculate income tax under the FY2024-25 (AY 2025-26) Indian New Tax
    Regime (Section 115BAC), using the slabs below:

        ₹0 - ₹3,00,000        : Nil
        ₹3,00,000 - ₹7,00,000 : 5%
        ₹7,00,000 - ₹10,00,000: 10%
        ₹10,00,000 - ₹12,00,000: 15%
        ₹12,00,000 - ₹15,00,000: 20%
        Above ₹15,00,000       : 30%

    A Section 87A rebate makes the tax payable zero if annual_income does
    not exceed ₹7,00,000 (no cess is applied in this simplified calculator).

    Args:
        annual_income: Total annual taxable income, in INR.

    Returns:
        NewRegimeTaxResult with tax_amount, a breakdown of slabs_applied,
        and effective_rate_pct.
    """
    if annual_income < 0:
        raise ValueError("annual_income must be non-negative")

    slabs_applied: List[SlabApplied] = []
    tax_amount = 0.0

    for lower, upper, rate_pct, label in _NEW_REGIME_SLABS:
        if annual_income <= lower:
            break

        slab_top = upper if upper is not None else annual_income
        taxable_in_slab = max(0.0, min(annual_income, slab_top) - lower)

        if taxable_in_slab <= 0:
            continue

        tax_in_slab = taxable_in_slab * (rate_pct / 100.0)
        tax_amount += tax_in_slab

        slabs_applied.append(
            SlabApplied(
                slab_label=label,
                rate_pct=rate_pct,
                taxable_amount_in_slab=round(taxable_in_slab, 2),
                tax_in_slab=round(tax_in_slab, 2),
            )
        )

    # Section 87A rebate: tax becomes nil if income <= ₹7,00,000.
    if annual_income <= NEW_REGIME_REBATE_INCOME_LIMIT:
        tax_amount = 0.0

    effective_rate_pct = (tax_amount / annual_income * 100.0) if annual_income > 0 else 0.0

    return NewRegimeTaxResult(
        tax_amount=round(tax_amount, 2),
        slabs_applied=slabs_applied,
        effective_rate_pct=round(effective_rate_pct, 2),
    )


# Old Tax Regime slabs (for individuals below 60 years), unchanged for
# FY2024-25. Each tuple is (lower_bound, upper_bound, rate_pct).
_OLD_REGIME_SLABS = [
    (0.0, 250_000.0, 0.0),
    (250_000.0, 500_000.0, 5.0),
    (500_000.0, 1_000_000.0, 20.0),
    (1_000_000.0, None, 30.0),
]

# Section 87A rebate threshold under the old regime: full rebate (tax
# reduced to zero) if taxable income does not exceed ₹5,00,000.
OLD_REGIME_REBATE_INCOME_LIMIT = 500_000.0


def calculate_income_tax_old_regime(
    annual_income: float,
    deductions_80c: float = 0.0,
    deductions_other: float = 0.0,
) -> OldRegimeTaxResult:
    """
    Calculate income tax under the Old (existing) Indian Tax Regime for
    FY2024-25 (individuals below 60 years), using the slabs below:

        ₹0 - ₹2,50,000        : Nil
        ₹2,50,000 - ₹5,00,000 : 5%
        ₹5,00,000 - ₹10,00,000: 20%
        Above ₹10,00,000       : 30%

    Taxable income is computed as:

        taxable_income = max(
            0,
            annual_income - standard_deduction(₹50,000)
                          - deductions_80c - deductions_other
        )

    Section 80C deductions are capped at ₹1,50,000 per the Income-tax Act,
    1961. A Section 87A rebate makes the tax payable zero if taxable_income
    does not exceed ₹5,00,000 (no cess is applied in this simplified
    calculator).

    Args:
        annual_income: Gross total annual income, in INR.
        deductions_80c: Deductions claimed under Section 80C (e.g. PPF,
            ELSS, life insurance premium), capped at ₹1,50,000.
        deductions_other: Other eligible deductions (e.g. 80D, 80G, HRA),
            in INR.

    Returns:
        OldRegimeTaxResult with tax_amount, taxable_income, and
        effective_rate_pct.
    """
    if annual_income < 0:
        raise ValueError("annual_income must be non-negative")
    if deductions_80c < 0 or deductions_other < 0:
        raise ValueError("deductions must be non-negative")

    capped_80c = min(deductions_80c, 150_000.0)

    taxable_income = max(
        0.0,
        annual_income
        - OLD_REGIME_STANDARD_DEDUCTION
        - capped_80c
        - deductions_other,
    )

    tax_amount = 0.0
    for lower, upper, rate_pct in _OLD_REGIME_SLABS:
        if taxable_income <= lower:
            break
        slab_top = upper if upper is not None else taxable_income
        taxable_in_slab = max(0.0, min(taxable_income, slab_top) - lower)
        tax_amount += taxable_in_slab * (rate_pct / 100.0)

    # Section 87A rebate: tax becomes nil if taxable income <= ₹5,00,000.
    if taxable_income <= OLD_REGIME_REBATE_INCOME_LIMIT:
        tax_amount = 0.0

    effective_rate_pct = (
        (tax_amount / annual_income * 100.0) if annual_income > 0 else 0.0
    )

    return OldRegimeTaxResult(
        tax_amount=round(tax_amount, 2),
        taxable_income=round(taxable_income, 2),
        effective_rate_pct=round(effective_rate_pct, 2),
    )
