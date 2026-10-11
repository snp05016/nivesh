import datetime
import math
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel

class XNPVResponse(BaseModel):
    value: float

class XIRRResponse(BaseModel):
    value: float

def xnpv(rate: float, cashflows: List[Tuple[datetime.date, float]]) -> XNPVResponse:
    """
    Calculate the Net Present Value for a schedule of cash flows.
    """
    if rate <= -1.0:
        return XNPVResponse(value=float('inf'))
    if not cashflows:
        return XNPVResponse(value=0.0)
    d0 = cashflows[0][0]
    return XNPVResponse(value=sum([cf / (1 + rate)**((d - d0).days / 365.0) for d, cf in cashflows]))

def xirr(cashflows: List[Tuple[datetime.date, float]], guess: float = 0.1, tol: float = 1e-4, max_iter: int = 100) -> XIRRResponse:
    """
    Calculate the Extended Internal Rate of Return for a schedule of cash flows using the Newton-Raphson method.
    cashflows: list of tuples (date, amount)
    """
    if not cashflows:
        return XIRRResponse(value=0.0)

    # Ensure cashflows have both positive and negative values
    positive = any(cf > 0 for _, cf in cashflows)
    negative = any(cf < 0 for _, cf in cashflows)
    if not (positive and negative):
        raise ValueError("Cash flows must contain both positive and negative values to calculate XIRR.")

    # Sort cash flows by date
    cashflows = sorted(cashflows, key=lambda x: x[0])
    
    rate = guess
    try:
        for _ in range(max_iter):
            f_val = xnpv(rate, cashflows).value
            # Numerical derivative
            f_deriv = (xnpv(rate + 1e-5, cashflows).value - f_val) / 1e-5

            if abs(f_deriv) < 1e-12 or not math.isfinite(f_deriv):
                break

            rate_new = rate - f_val / f_deriv

            if rate_new <= -1.0 or not math.isfinite(rate_new):
                break

            if abs(rate_new - rate) < tol:
                return XIRRResponse(value=rate_new)

            rate = rate_new
    except (OverflowError, ZeroDivisionError):
        pass

    # Newton diverged / stalled: bisection on xnpv is slower but always converges
    # once the bracket has a sign change.
    return XIRRResponse(value=_xirr_bisect(cashflows, tol))


def _xirr_bisect(cashflows: List[Tuple[datetime.date, float]], tol: float, lo: float = -0.9999, hi: float = 100.0) -> float:
    def f(r: float) -> float:
        try:
            return xnpv(r, cashflows).value
        except OverflowError:
            return float("inf")

    f_lo, f_hi = f(lo), f(hi)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        raise ValueError("XIRR has no solution in [{}, {}]".format(lo, hi))
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if f_mid == 0 or (hi - lo) / 2 < tol * 1e-2:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2
