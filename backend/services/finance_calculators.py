"""Loan EMI and APR math for the demo loan marketplace (REG-05).

APR follows the RBI KFS (Annex B) method: the internal rate of return of the
EMI stream against the net amount disbursed (principal minus upfront fees),
expressed as a nominal annual rate (monthly IRR x 12).
"""


def calculate_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    """Equated monthly instalment for a reducing-balance loan."""
    n = max(1, int(tenure_months))
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / n
    growth = (1 + r) ** n
    return principal * r * growth / (growth - 1)


def calculate_apr(principal: float, annual_rate_pct: float, tenure_months: int, fee_pct: float) -> float:
    """Nominal annual APR (%) as the IRR of the EMIs on the net disbursal."""
    n = max(1, int(tenure_months))
    emi = calculate_emi(principal, annual_rate_pct, n)
    net = principal * (1 - fee_pct / 100)

    def present_value(r: float) -> float:
        if r == 0:
            return emi * n
        return emi * (1 - (1 + r) ** -n) / r

    # present_value falls as r rises; bisect for present_value(r) == net.
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if present_value(mid) > net:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2 * 12 * 100, 2)
