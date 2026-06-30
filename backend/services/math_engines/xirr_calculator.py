import datetime
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
    for _ in range(max_iter):
        f_val = xnpv(rate, cashflows).value
        # Numerical derivative
        f_deriv = (xnpv(rate + 1e-5, cashflows).value - f_val) / 1e-5
        
        if abs(f_deriv) < 1e-12:
            break
            
        rate_new = rate - f_val / f_deriv
        
        if abs(rate_new - rate) < tol:
            return XIRRResponse(value=rate_new)
            
        rate = rate_new

    raise RuntimeError("XIRR calculation did not converge after {} iterations".format(max_iter))
