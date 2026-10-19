"""Capital-gains working for listed shares (I29): JSON and CSV for one financial year. Flag money_tax_report."""
from fastapi import APIRouter, Depends, HTTPException, Response

from core.feature_flags import require_flag
from core.security import require_auth
from services import money_tax_report

router = APIRouter(
    prefix="/api/v1/me/tax", tags=["Money"], dependencies=[Depends(require_flag("money_tax_report"))]
)


def _report(user_id: int, fy: str) -> dict:
    try:
        return money_tax_report.capital_gains(user_id, fy)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_FY", "message": "Choose a financial year like 2025-26."},
        ) from None


@router.get("/capital-gains")
def capital_gains(fy: str = "", user_id: int = Depends(require_auth)):
    return _report(user_id, fy)


@router.get("/capital-gains.csv")
def capital_gains_csv(fy: str = "", user_id: int = Depends(require_auth)):
    report = _report(user_id, fy)
    return Response(
        content=money_tax_report.capital_gains_csv(report),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=nivesh_capital_gains_FY{fy}.csv",
            "Cache-Control": "no-store",
        },
    )
