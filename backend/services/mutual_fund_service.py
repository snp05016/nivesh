"""Mutual Fund Router service — business logic + repository access for
MutualFund.

Controller-Service-Repository: routers/mutual_funds.py must only validate
HTTP input and call functions here. All session.query() calls for
MutualFund live in this module.
"""
from datetime import date
from typing import Optional

from database import get_session
from models.db_models import MutualFund
from sqlalchemy import or_

VALID_CATEGORIES = {
    "Equity",
    "Debt",
    "Hybrid",
    "Solution Oriented",
    "Other",
}

VALID_RISK_LEVELS = {"Low", "Moderate", "Moderately High", "High", "Very High"}


# ---------------------------------------------------------------------------
# Mock/seed data — no live AMFI/RTA feed is wired in for this pass. This
# mirrors the shape a real AMFI NAV-history harvester would eventually
# populate. Clearly marked MOCK DATA; safe to delete once a real harvester
# exists.
# Seeded only at startup and only when DEMO_MODE=true (main._seed_catalogs);
# migration e0edc81fbf84 purges these rows from existing databases.
# ---------------------------------------------------------------------------
_MOCK_FUNDS = [
    {
        "scheme_code": "INF209K01157",
        "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        "amc_name": "PPFAS Mutual Fund",
        "category": "Equity",
        "sub_category": "Flexi Cap",
        "nav": 82.45,
        "aum_cr": 68500.0,
        "expense_ratio": 0.63,
        "returns_1y": 28.4,
        "returns_3y": 22.1,
        "returns_5y": 24.6,
        "risk_level": "Very High",
        "fund_manager": "Rajeev Thakkar",
        "is_direct_plan": True,
        "is_growth_plan": True,
    },
    {
        "scheme_code": "INF090I01239",
        "scheme_name": "ICICI Prudential Bluechip Fund - Direct Plan - Growth",
        "amc_name": "ICICI Prudential Mutual Fund",
        "category": "Equity",
        "sub_category": "Large Cap",
        "nav": 106.32,
        "aum_cr": 58200.0,
        "expense_ratio": 0.89,
        "returns_1y": 19.7,
        "returns_3y": 17.3,
        "returns_5y": 18.9,
        "risk_level": "High",
        "fund_manager": "Anish Tawakley",
        "is_direct_plan": True,
        "is_growth_plan": True,
    },
    {
        "scheme_code": "INF109K01AA1",
        "scheme_name": "ICICI Prudential Corporate Bond Fund - Direct Plan - Growth",
        "amc_name": "ICICI Prudential Mutual Fund",
        "category": "Debt",
        "sub_category": "Corporate Bond",
        "nav": 27.88,
        "aum_cr": 26800.0,
        "expense_ratio": 0.35,
        "returns_1y": 7.4,
        "returns_3y": 6.5,
        "returns_5y": 7.1,
        "risk_level": "Low",
        "fund_manager": "Manish Banthia",
        "is_direct_plan": True,
        "is_growth_plan": True,
    },
    {
        "scheme_code": "INF204K01LX0",
        "scheme_name": "HDFC Balanced Advantage Fund - Direct Plan - Growth",
        "amc_name": "HDFC Mutual Fund",
        "category": "Hybrid",
        "sub_category": "Dynamic Asset Allocation",
        "nav": 412.19,
        "aum_cr": 94500.0,
        "expense_ratio": 0.75,
        "returns_1y": 21.3,
        "returns_3y": 19.8,
        "returns_5y": 19.2,
        "risk_level": "Moderately High",
        "fund_manager": "Srinivas Rao Ravuri",
        "is_direct_plan": True,
        "is_growth_plan": True,
    },
    {
        "scheme_code": "INF200K01UY1",
        "scheme_name": "SBI Small Cap Fund - Direct Plan - Growth",
        "amc_name": "SBI Mutual Fund",
        "category": "Equity",
        "sub_category": "Small Cap",
        "nav": 178.62,
        "aum_cr": 32100.0,
        "expense_ratio": 0.68,
        "returns_1y": 32.9,
        "returns_3y": 25.4,
        "returns_5y": 29.1,
        "risk_level": "Very High",
        "fund_manager": "R. Srinivasan",
        "is_direct_plan": True,
        "is_growth_plan": True,
    },
    {
        "scheme_code": "INF769K01AJ4",
        "scheme_name": "Mirae Asset Emerging Bluechip Fund - Direct Plan - Growth",
        "amc_name": "Mirae Asset Mutual Fund",
        "category": "Equity",
        "sub_category": "Large & Mid Cap",
        "nav": 145.77,
        "aum_cr": 41200.0,
        "expense_ratio": 0.59,
        "returns_1y": 24.8,
        "returns_3y": 20.6,
        "returns_5y": 22.4,
        "risk_level": "High",
        "fund_manager": "Neelesh Surana",
        "is_direct_plan": True,
        "is_growth_plan": True,
    },
]

# Scheme codes of the seeded sample catalog above. Rows with these codes carry
# frozen, illustrative figures — the API flags them `is_sample` so clients can
# label them instead of presenting them as live fund data.
SAMPLE_SCHEME_CODES = frozenset(r["scheme_code"] for r in _MOCK_FUNDS)


def seed_mock_funds_if_empty() -> int:
    """Populate mutual_funds with mock data when the table is empty.

    MOCK DATA — for development/demo only, no live AMFI/RTA feed in this
    pass. Returns the number of rows inserted.
    """
    with get_session() as session:
        existing = session.query(MutualFund).count()
        if existing > 0:
            return 0
        inserted = 0
        for row in _MOCK_FUNDS:
            fund = MutualFund(
                scheme_code=row["scheme_code"],
                scheme_name=row["scheme_name"],
                amc_name=row["amc_name"],
                category=row["category"],
                sub_category=row["sub_category"],
                nav=row["nav"],
                nav_date=date.today().isoformat(),
                aum_cr=row["aum_cr"],
                expense_ratio=row["expense_ratio"],
                returns_1y=row["returns_1y"],
                returns_3y=row["returns_3y"],
                returns_5y=row["returns_5y"],
                risk_level=row["risk_level"],
                fund_manager=row["fund_manager"],
                is_direct_plan=row["is_direct_plan"],
                is_growth_plan=row["is_growth_plan"],
                # legacy mirror fields for backward compatibility
                fund_name=row["scheme_name"],
                amc=row["amc_name"],
            )
            session.add(fund)
            inserted += 1
        session.commit()
        return inserted


def list_funds(
    category: Optional[str] = None,
    amc_name: Optional[str] = None,
    search: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> list[MutualFund]:
    """List funds with optional category/AMC/risk filters and free-text search."""
    with get_session() as session:
        query = session.query(MutualFund)
        if category:
            query = query.filter(MutualFund.category == category)
        if amc_name:
            query = query.filter(or_(MutualFund.amc_name == amc_name, MutualFund.amc == amc_name))
        if risk_level:
            query = query.filter(MutualFund.risk_level == risk_level)
        if search:
            like = f"%{search}%"
            query = query.filter(or_(MutualFund.scheme_name.ilike(like), MutualFund.fund_name.ilike(like)))
        return query.order_by(MutualFund.aum_cr.desc().nullslast()).all()


def get_fund_by_scheme_code(scheme_code: str) -> Optional[MutualFund]:
    with get_session() as session:
        return (
            session.query(MutualFund)
            .filter(MutualFund.scheme_code == scheme_code)
            .first()
        )


def get_nav_history(scheme_code: str, days: int = 30) -> Optional[list[dict]]:
    """Return the NAV history series of {date, nav} for a scheme.

    Returns None when the scheme does not exist, otherwise [] until a real
    AMFI historical-NAV feed exists. Never fabricate points: clients render
    whatever this returns as real fund performance.
    """
    if get_fund_by_scheme_code(scheme_code) is None:
        return None
    return []
